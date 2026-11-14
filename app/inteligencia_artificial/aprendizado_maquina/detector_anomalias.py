from datetime import datetime, timezone
import json
import math
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

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import (
    UNIDADES_MODELO,
    VARIAVEIS_MODELO,
    VERSAO_FEATURES,
    VERSAO_PREPROCESSAMENTO,
)
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo, ResultadoAnomalia
from app.inteligencia_artificial.aprendizado_maquina.preparacao import preparar_leituras


class DetectorAnomalias:
    """Pipeline versionado de StandardScaler e Isolation Forest."""

    FORMATO_ARTEFATO = 3

    def __init__(self, numero_estimadores=200, contaminacao=0.05, semente_aleatoria=42,
                 minimo_observacoes=32, versao_modelo="isolation-forest-v3"):
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

    def treinar(self, leituras, *, identificador_dados: str | None = None):
        conjunto = preparar_leituras(leituras, unidades_esperadas=UNIDADES_MODELO)
        if len(conjunto.leituras) < self.minimo_observacoes:
            raise ValueError(
                f"Dados insuficientes: {len(conjunto.leituras)} observações válidas; "
                f"mínimo configurado: {self.minimo_observacoes}."
            )
        if conjunto.matriz.shape[1] != len(VARIAVEIS_MODELO):
            raise ValueError("A matriz de treino não corresponde à ordem e quantidade de features oficiais.")
        if not np.isfinite(conjunto.matriz).all():
            raise ValueError("A matriz de treino contém valores não finitos.")

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
        self._unidades = dict(UNIDADES_MODELO)
        self._metadados = {
            "formato_artefato": self.FORMATO_ARTEFATO,
            "versao_modelo": self.versao_modelo,
            "algoritmo": "IsolationForest",
            "versao_features": VERSAO_FEATURES,
            "features": list(VARIAVEIS_MODELO),
            "variaveis": list(VARIAVEIS_MODELO),
            "quantidade_caracteristicas": len(VARIAVEIS_MODELO),
            "unidades": dict(UNIDADES_MODELO),
            "versao_preprocessamento": VERSAO_PREPROCESSAMENTO,
            "preprocessamento": {
                "algoritmo": "StandardScaler",
                "with_mean": True,
                "with_std": True,
            },
            "versao_scikit_learn": sklearn.__version__,
            "origens_treinamento": origens,
            "identificador_dados_treinamento": identificador_dados,
            "dados_sinteticos": bool(origens) and all(origem == "SIMULADO_TESTE" for origem in origens),
            "quantidade_treinamento": len(conjunto.leituras),
            "quantidade_descartada": len(conjunto.descartadas),
            "treinado_em": datetime.now(timezone.utc).isoformat(),
            "configuracao": self.configuracao(),
        }
        return dict(self._metadados)

    def configuracao(self):
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
        if not math.isfinite(pontuacao):
            raise ValueError("O modelo produziu um score não finito.")
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
        manifesto_path = destino.with_suffix(".manifest.json")
        artefato = {**self._metadados, "pipeline": self._modelo}
        temporarios: list[str] = []
        try:
            with tempfile.NamedTemporaryFile(prefix=destino.stem + ".", suffix=".tmp", dir=destino.parent, delete=False) as arquivo_modelo:
                temporario_modelo = arquivo_modelo.name
                temporarios.append(temporario_modelo)
            with tempfile.NamedTemporaryFile(prefix=manifesto_path.stem + ".", suffix=".tmp", dir=destino.parent, mode="w", encoding="utf-8", delete=False) as arquivo_manifesto:
                temporario_manifesto = arquivo_manifesto.name
                temporarios.append(temporario_manifesto)
                json.dump(self._metadados, arquivo_manifesto, ensure_ascii=False, indent=2)
                arquivo_manifesto.write("\n")
            joblib.dump(artefato, temporario_modelo, compress=3)
            os.replace(temporario_manifesto, manifesto_path)
            temporarios.remove(temporario_manifesto)
            os.replace(temporario_modelo, destino)
            temporarios.remove(temporario_modelo)
        finally:
            for temporario in temporarios:
                if os.path.exists(temporario):
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

        manifesto_path = origem.with_suffix(".manifest.json")
        try:
            manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            raise ValueError("Manifesto do artefato ausente ou inválido.") from erro
        embutido = {chave: valor for chave, valor in artefato.items() if chave != "pipeline"}
        if manifesto != embutido:
            raise ValueError("Manifesto externo e metadados do artefato divergem.")
        if artefato.get("versao_scikit_learn") != sklearn.__version__:
            raise ValueError("A versão do Scikit-learn difere da usada no treinamento; retreine o artefato.")
        if (
            artefato.get("versao_features") != VERSAO_FEATURES
            or artefato.get("features") != list(VARIAVEIS_MODELO)
            or artefato.get("variaveis") != list(VARIAVEIS_MODELO)
            or artefato.get("quantidade_caracteristicas") != len(VARIAVEIS_MODELO)
            or artefato.get("unidades") != UNIDADES_MODELO
            or artefato.get("versao_preprocessamento") != VERSAO_PREPROCESSAMENTO
        ):
            raise ValueError("O artefato não corresponde à versão, ordem ou unidades das features desta API.")

        pipeline = artefato.get("pipeline")
        scaler = pipeline.named_steps.get("padronizador") if isinstance(pipeline, Pipeline) else None
        modelo_if = pipeline.named_steps.get("isolation_forest") if isinstance(pipeline, Pipeline) else None
        if (
            not isinstance(pipeline, Pipeline)
            or list(pipeline.named_steps) != ["padronizador", "isolation_forest"]
            or not isinstance(scaler, StandardScaler)
            or not isinstance(modelo_if, IsolationForest)
            or getattr(scaler, "n_features_in_", None) != len(VARIAVEIS_MODELO)
            or getattr(modelo_if, "n_features_in_", None) != len(VARIAVEIS_MODELO)
            or scaler.with_mean is not True
            or scaler.with_std is not True
            or np.asarray(getattr(scaler, "mean_", [])).shape != (len(VARIAVEIS_MODELO),)
            or np.asarray(getattr(scaler, "scale_", [])).shape != (len(VARIAVEIS_MODELO),)
            or not np.isfinite(getattr(scaler, "mean_", np.array([np.nan]))).all()
            or not np.isfinite(getattr(scaler, "scale_", np.array([np.nan]))).all()
        ):
            raise ValueError("O artefato não contém scaler e Isolation Forest compatíveis com quatro features.")

        configuracao = artefato.get("configuracao")
        versao = artefato.get("versao_modelo")
        if not isinstance(configuracao, dict) or not isinstance(versao, str):
            raise ValueError("O manifesto do artefato está incompleto.")
        if artefato.get("preprocessamento") != {"algoritmo": "StandardScaler", "with_mean": True, "with_std": True}:
            raise ValueError("A configuração de pré-processamento do manifesto é incompatível.")
        origens = artefato.get("origens_treinamento")
        sintetico = artefato.get("dados_sinteticos")
        if (
            not isinstance(artefato.get("treinado_em"), str)
            or not isinstance(origens, list)
            or not origens
            or not isinstance(sintetico, bool)
            or sintetico != all(origem == "SIMULADO_TESTE" for origem in origens)
        ):
            raise ValueError("A origem, flag sintética ou data do treinamento está ausente/inconsistente no manifesto.")
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
        if (
            modelo_if.n_estimators != detector.numero_estimadores
            or modelo_if.contamination != detector.contaminacao
            or modelo_if.random_state != detector.semente_aleatoria
        ):
            raise ValueError("Parâmetros do Isolation Forest não correspondem ao manifesto.")
        detector._modelo = pipeline
        detector._unidades = dict(UNIDADES_MODELO)
        detector._metadados = embutido
        return detector
