from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo, ResultadoAnomalia
from app.inteligencia_artificial.aprendizado_maquina.preparacao import preparar_leituras

class DetectorAnomalias:
    """Treina e executa um pipeline Isolation Forest; não treina durante inferência."""
    FORMATO_ARTEFATO = 2

    def __init__(
        self,
        numero_estimadores: int = 200,
        contaminacao: float = 0.05,
        semente_aleatoria: int = 42,
        minimo_observacoes: int = 32,
        versao_modelo: str = "isolation-forest-v2",
    ) -> None:
        if numero_estimadores < 10:
            raise ValueError("numero_estimadores deve ser pelo menos 10.")
        if not 0 < contaminacao <= 0.5:
            raise ValueError("contaminacao deve estar no intervalo (0, 0.5].")
        if minimo_observacoes < 2:
            raise ValueError("minimo_observacoes deve ser pelo menos 2.")
        self.numero_estimadores = numero_estimadores
        self.contaminacao = contaminacao
        self.semente_aleatoria = semente_aleatoria
        self.minimo_observacoes = minimo_observacoes
        self.versao_modelo = versao_modelo
        self._modelo: Pipeline | None = None
        self._unidades: dict[str, str] | None = None
        self._metadados: dict[str, Any] = {}

    @property
    def treinado(self) -> bool:
        return self._modelo is not None

    def treinar(self, leituras: list[LeituraParaModelo]) -> dict[str, Any]:
        conjunto = preparar_leituras(leituras)
        if len(conjunto.leituras) < self.minimo_observacoes:
            raise ValueError(
                f"Dados insuficientes: {len(conjunto.leituras)} observações válidas; "
                f"mínimo configurado: {self.minimo_observacoes}."
            )

        modelo = Pipeline(steps=[
            ("padronizador", StandardScaler()),
            ("isolation_forest", IsolationForest(
                n_estimators=self.numero_estimadores,
                contamination=self.contaminacao,
                random_state=self.semente_aleatoria,
                n_jobs=1,
            )),
        ])
        modelo.fit(conjunto.matriz)
        origens = sorted({leitura.origem for leitura in conjunto.leituras})
        self._modelo = modelo
        self._unidades = conjunto.unidades
        self._metadados = {
            "formato_artefato": self.FORMATO_ARTEFATO,
            "versao_modelo": self.versao_modelo,
            "versao_scikit_learn": sklearn.__version__,
            "variaveis": list(VARIAVEIS_MODELO),
            "quantidade_caracteristicas": len(VARIAVEIS_MODELO),
            "unidades": dict(conjunto.unidades),
            "origens_treinamento": origens,
            "dados_sinteticos": bool(origens) and all(origem == "SIMULADO_TESTE" for origem in origens),
            "quantidade_treinamento": len(conjunto.leituras),
            "quantidade_descartada": len(conjunto.descartadas),
            "treinado_em": datetime.now(timezone.utc).isoformat(),
            "configuracao": self.configuracao(),
        }
        return dict(self._metadados)

    def configuracao(self) -> dict[str, object]:
        return {
            "algoritmo": "IsolationForest",
            "numeroEstimadores": self.numero_estimadores,
            "contaminacao": self.contaminacao,
            "sementeAleatoria": self.semente_aleatoria,
            "minimoObservacoes": self.minimo_observacoes,
            "padronizacao": "StandardScaler",
        }

    def predizer(self, leitura: LeituraParaModelo) -> ResultadoAnomalia:
        if self._modelo is None or self._unidades is None:
            raise RuntimeError("O modelo ainda não foi treinado ou carregado.")
        conjunto = preparar_leituras([leitura], unidades_esperadas=self._unidades)
        if len(conjunto.leituras) != 1:
            motivos = "; ".join(item["motivo"] for item in conjunto.descartadas)
            raise ValueError("Dados insuficientes ou inválidos para inferência: " + motivos)

        classificacao_bruta = int(self._modelo.predict(conjunto.matriz)[0])
        pontuacao = float(-self._modelo.score_samples(conjunto.matriz)[0])
        anomalia = classificacao_bruta == -1
        explicacao = (
            "O Isolation Forest classificou a observação como estatisticamente atípica em relação ao conjunto de treinamento."
            if anomalia else
            "O Isolation Forest não classificou a observação como atípica em relação ao conjunto de treinamento."
        )
        explicacao += " A pontuação é um escore do modelo, não uma probabilidade, risco ou diagnóstico agronômico."
        return ResultadoAnomalia(
            id_observacao=leitura.id_observacao,
            classificada_como_anomalia=anomalia,
            classificacao="ANOMALIA_ESTATISTICA" if anomalia else "NAO_ATIPICA_ESTIMADA",
            pontuacao_anomalia=pontuacao,
            variaveis_utilizadas=list(VARIAVEIS_MODELO),
            data_analise=datetime.now(timezone.utc),
            data_leitura=leitura.registrado_em,
            origem_dados=leitura.origem,
            versao_modelo=self.versao_modelo,
            configuracao_modelo=self.configuracao(),
            justificativa=explicacao,
        )

    def classificar_lote(self, leituras: list[LeituraParaModelo]) -> list[bool]:
        if self._modelo is None or self._unidades is None:
            raise RuntimeError("O modelo ainda não foi treinado ou carregado.")
        conjunto = preparar_leituras(leituras, unidades_esperadas=self._unidades)
        if len(conjunto.leituras) != len(leituras):
            raise ValueError("A avaliação contém leituras inválidas ou dados ausentes; não é possível calcular métricas alinhadas.")
        return [int(valor) == -1 for valor in self._modelo.predict(conjunto.matriz)]

    def salvar(self, caminho: str | Path) -> Path:
        if self._modelo is None:
            raise RuntimeError("Não é possível salvar um modelo ainda não treinado.")
        destino = Path(caminho)
        destino.parent.mkdir(parents=True, exist_ok=True)
        artefato = {**self._metadados, "pipeline": self._modelo}
        temporario: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=destino.stem + ".", suffix=".tmp", dir=destino.parent, delete=False) as arquivo:
                temporario = arquivo.name
            joblib.dump(artefato, temporario, compress=3)
            os.replace(temporario, destino)
            temporario = None
        finally:
            if temporario and os.path.exists(temporario):
                os.unlink(temporario)
        return destino

    @classmethod
    def carregar(cls, caminho: str | Path) -> "DetectorAnomalias":
        origem = Path(caminho)
        if not origem.is_file():
            raise FileNotFoundError(f"Artefato do modelo não encontrado: {origem}")
        try:
            artefato = joblib.load(origem)
        except Exception as erro:
            raise ValueError("Não foi possível carregar o artefato local do modelo.") from erro
        if not isinstance(artefato, dict) or artefato.get("formato_artefato") != cls.FORMATO_ARTEFATO:
            raise ValueError("Formato ou versão do artefato incompatível.")
        if artefato.get("versao_scikit_learn") != sklearn.__version__:
            raise ValueError("A versão do Scikit-learn difere da usada no treinamento; retreine o artefato.")
        if artefato.get("variaveis") != list(VARIAVEIS_MODELO) or artefato.get("quantidade_caracteristicas") != len(VARIAVEIS_MODELO):
            raise ValueError("O artefato não corresponde às variáveis desta versão da API.")
        pipeline = artefato.get("pipeline")
        configuracao = artefato.get("configuracao")
        unidades = artefato.get("unidades")
        versao = artefato.get("versao_modelo")
        if not isinstance(pipeline, Pipeline) or set(pipeline.named_steps) != {"padronizador", "isolation_forest"} or getattr(pipeline.named_steps.get("padronizador"), "n_features_in_", None) != len(VARIAVEIS_MODELO):
            raise ValueError("O artefato não contém o pipeline Scikit-learn esperado.")
        if not isinstance(configuracao, dict) or not isinstance(unidades, dict) or not isinstance(versao, str):
            raise ValueError("O manifesto do artefato está incompleto.")
        try:
            detector = cls(
                numero_estimadores=int(configuracao["numeroEstimadores"]),
                contaminacao=float(configuracao["contaminacao"]),
                semente_aleatoria=int(configuracao["sementeAleatoria"]),
                minimo_observacoes=int(configuracao["minimoObservacoes"]),
                versao_modelo=versao,
            )
        except (KeyError, TypeError, ValueError) as erro:
            raise ValueError("A configuração persistida do modelo é inválida.") from erro
        detector._modelo = pipeline
        detector._unidades = {str(chave): str(valor) for chave, valor in unidades.items()}
        detector._metadados = {chave: valor for chave, valor in artefato.items() if chave != "pipeline"}
        return detector
