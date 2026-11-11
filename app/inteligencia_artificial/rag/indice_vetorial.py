import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from app.inteligencia_artificial.rag.embeddings import CodificadorEmbeddings
from app.inteligencia_artificial.rag.esquemas import TrechoConhecimento


class IndiceIndisponivel(RuntimeError):
    pass


CONFIGURACAO_CODIFICACAO_PADRAO = {
    "prefixo_consulta": "",
    "prefixo_documento": "",
}


class IndiceVetorialLocal:
    """Índice exato FAISS local; carrega somente arquivos locais confiáveis."""

    VERSAO_FORMATO = 2
    NOME_INDICE = "trechos.faiss"
    NOME_TRECHOS = "trechos.jsonl"
    NOME_MANIFESTO = "manifesto.json"
    LIMITE_MANIFESTO_BYTES = 1_000_000

    def __init__(self, diretorio: str | Path) -> None:
        self.diretorio = Path(diretorio).resolve()
        try:
            import faiss
        except ImportError as erro:
            raise IndiceIndisponivel("FAISS não está instalado.") from erro
        self._faiss = faiss
        self._indice: Any | None = None
        self._trechos: list[TrechoConhecimento] = []
        self._identificador_modelo: str | None = None
        self._revisao_modelo: str | None = None
        self._dimensao: int | None = None

    @property
    def disponivel(self) -> bool:
        return self._indice is not None and bool(self._trechos)

    @property
    def quantidade_trechos(self) -> int:
        return len(self._trechos)

    def reconstruir(
        self,
        trechos: list[TrechoConhecimento],
        vetores: np.ndarray,
        identificador_modelo: str,
        revisao_modelo: str,
        fingerprint_modelo: str,
        configuracao_codificacao: dict[str, str] | None = None,
    ) -> None:
        if not trechos:
            raise ValueError("Não é possível construir um índice sem trechos.")
        if not identificador_modelo.strip() or not revisao_modelo.strip():
            raise ValueError("Identificador e revisão do modelo precisam ser informados.")
        if not self._hash_valido(fingerprint_modelo):
            raise ValueError("Fingerprint SHA-256 do modelo inválido.")
        matriz = self._normalizar_matriz(vetores, quantidade=len(trechos))
        self.diretorio.mkdir(parents=True, exist_ok=True)
        indice = self._faiss.IndexFlatIP(matriz.shape[1])
        indice.add(matriz)

        temporarios: list[str] = []
        try:
            indice_tmp = self._gravar_temporario(".faiss", indice)
            temporarios.append(indice_tmp)
            trechos_tmp = self._gravar_jsonl_temporario(trechos)
            temporarios.append(trechos_tmp)
            indice_bytes = Path(indice_tmp).read_bytes()
            trechos_bytes = Path(trechos_tmp).read_bytes()
            manifesto = {
                "versao_formato": self.VERSAO_FORMATO,
                "identificador_modelo": identificador_modelo,
                "revisao_modelo": revisao_modelo,
                "fingerprint_modelo": fingerprint_modelo,
                "configuracao_codificacao": (
                    CONFIGURACAO_CODIFICACAO_PADRAO
                    if configuracao_codificacao is None
                    else configuracao_codificacao
                ),
                "dimensao_embeddings": int(matriz.shape[1]),
                "metrica": "produto_interno_com_vetores_normalizados",
                "quantidade_trechos": len(trechos),
                "sha256_indice": hashlib.sha256(indice_bytes).hexdigest(),
                "sha256_trechos": hashlib.sha256(trechos_bytes).hexdigest(),
            }
            manifesto_tmp = self._escrever_temporario(
                ".json", json.dumps(manifesto, ensure_ascii=False, sort_keys=True).encode("utf-8")
            )
            temporarios.append(manifesto_tmp)
            os.replace(indice_tmp, self.diretorio / self.NOME_INDICE)
            os.replace(trechos_tmp, self.diretorio / self.NOME_TRECHOS)
            os.replace(manifesto_tmp, self.diretorio / self.NOME_MANIFESTO)
        finally:
            for temporario in temporarios:
                if os.path.exists(temporario):
                    os.unlink(temporario)

        self._indice = indice
        self._trechos = list(trechos)
        self._identificador_modelo = identificador_modelo
        self._revisao_modelo = revisao_modelo
        self._dimensao = int(matriz.shape[1])

    def carregar(self, codificador: CodificadorEmbeddings) -> None:
        manifesto_path = self.diretorio / self.NOME_MANIFESTO
        indice_path = self.diretorio / self.NOME_INDICE
        trechos_path = self.diretorio / self.NOME_TRECHOS
        if not all(path.is_file() for path in (manifesto_path, indice_path, trechos_path)):
            raise IndiceIndisponivel("Índice vetorial local ausente ou incompleto.")
        try:
            if manifesto_path.stat().st_size > self.LIMITE_MANIFESTO_BYTES:
                raise ValueError("Manifesto acima do limite permitido.")
            manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as erro:
            raise IndiceIndisponivel("Manifesto do índice ausente ou corrompido.") from erro
        self._validar_manifesto(manifesto)
        if manifesto["identificador_modelo"] != codificador.identificador_modelo:
            raise IndiceIndisponivel("O índice foi criado com outro modelo de embeddings.")
        if manifesto["revisao_modelo"] != codificador.revisao_modelo:
            raise IndiceIndisponivel("A revisão do modelo não corresponde ao índice vetorial.")
        if manifesto["fingerprint_modelo"] != codificador.fingerprint_modelo:
            raise IndiceIndisponivel("Os pesos do modelo não correspondem ao índice vetorial.")
        if manifesto["dimensao_embeddings"] != codificador.dimensao:
            raise IndiceIndisponivel("A dimensão do modelo não corresponde ao índice vetorial.")
        configuracao_codificacao = getattr(
            codificador, "configuracao_codificacao", CONFIGURACAO_CODIFICACAO_PADRAO
        )
        if manifesto["configuracao_codificacao"] != configuracao_codificacao:
            raise IndiceIndisponivel("A configuração de codificação não corresponde ao índice vetorial.")

        try:
            indice_bytes = indice_path.read_bytes()
            trechos_bytes = trechos_path.read_bytes()
        except OSError as erro:
            raise IndiceIndisponivel("Arquivos do índice local não puderam ser lidos.") from erro
        if hashlib.sha256(indice_bytes).hexdigest() != manifesto["sha256_indice"]:
            raise IndiceIndisponivel("O arquivo do índice diverge do manifesto.")
        if hashlib.sha256(trechos_bytes).hexdigest() != manifesto["sha256_trechos"]:
            raise IndiceIndisponivel("O arquivo de trechos diverge do manifesto.")
        try:
            linhas = trechos_bytes.decode("utf-8").splitlines()
            trechos = [TrechoConhecimento.model_validate_json(linha) for linha in linhas]
            indice = self._faiss.read_index(str(indice_path))
        except (UnicodeDecodeError, ValidationError, RuntimeError, OSError, ValueError) as erro:
            raise IndiceIndisponivel("Índice local corrompido ou inválido.") from erro
        if len(trechos) != manifesto["quantidade_trechos"] or indice.ntotal != len(trechos):
            raise IndiceIndisponivel("A contagem do índice não corresponde ao manifesto.")
        if indice.d != manifesto["dimensao_embeddings"] or not isinstance(indice, self._faiss.IndexFlatIP):
            raise IndiceIndisponivel("Tipo ou dimensão do índice FAISS incompatível.")
        self._indice = indice
        self._trechos = trechos
        self._identificador_modelo = codificador.identificador_modelo
        self._revisao_modelo = codificador.revisao_modelo
        self._dimensao = codificador.dimensao

    def buscar(
        self,
        vetor_consulta: np.ndarray,
        limite: int = 5,
        limiar_similaridade: float = 0.55,
    ) -> list[tuple[TrechoConhecimento, float]]:
        if self._indice is None:
            raise IndiceIndisponivel("Índice vetorial ainda não foi carregado.")
        if limite < 1 or not -1.0 <= limiar_similaridade <= 1.0:
            raise ValueError("Limite ou limiar de similaridade inválido.")
        consulta = self._normalizar_matriz(np.asarray(vetor_consulta).reshape(1, -1), 1)
        if consulta.shape[1] != self._indice.d:
            raise ValueError("Dimensão do vetor de consulta incompatível com o índice.")
        pontuacoes, posicoes = self._indice.search(consulta, min(limite, len(self._trechos)))
        encontrados: list[tuple[TrechoConhecimento, float]] = []
        for pontuacao, posicao in zip(pontuacoes[0], posicoes[0], strict=True):
            if posicao >= 0 and float(pontuacao) >= limiar_similaridade:
                encontrados.append((self._trechos[int(posicao)], float(pontuacao)))
        return encontrados

    def _validar_manifesto(self, manifesto: Any) -> None:
        obrigatorios = {
            "versao_formato", "identificador_modelo", "revisao_modelo",
            "fingerprint_modelo", "configuracao_codificacao", "dimensao_embeddings", "metrica", "quantidade_trechos",
            "sha256_indice", "sha256_trechos",
        }
        if not isinstance(manifesto, dict) or set(manifesto) != obrigatorios:
            raise IndiceIndisponivel("Campos obrigatórios do manifesto inválidos.")
        if type(manifesto["versao_formato"]) is not int or manifesto["versao_formato"] != self.VERSAO_FORMATO:
            raise IndiceIndisponivel("Versão do formato do índice incompatível.")
        if any(not isinstance(manifesto[nome], str) or not manifesto[nome].strip() for nome in ("identificador_modelo", "revisao_modelo")):
            raise IndiceIndisponivel("Identificador ou revisão do modelo inválidos no manifesto.")
        if type(manifesto["dimensao_embeddings"]) is not int or manifesto["dimensao_embeddings"] <= 0:
            raise IndiceIndisponivel("Dimensão de embeddings inválida no manifesto.")
        configuracao_codificacao = manifesto["configuracao_codificacao"]
        if (
            not isinstance(configuracao_codificacao, dict)
            or set(configuracao_codificacao) != {"prefixo_consulta", "prefixo_documento"}
            or any(not isinstance(valor, str) for valor in configuracao_codificacao.values())
        ):
            raise IndiceIndisponivel("Configuração de codificação inválida no manifesto.")
        if type(manifesto["quantidade_trechos"]) is not int or manifesto["quantidade_trechos"] <= 0:
            raise IndiceIndisponivel("Quantidade de trechos inválida no manifesto.")
        if manifesto["metrica"] != "produto_interno_com_vetores_normalizados":
            raise IndiceIndisponivel("Métrica do índice incompatível.")
        for nome in ("fingerprint_modelo", "sha256_indice", "sha256_trechos"):
            valor = manifesto[nome]
            if not self._hash_valido(valor):
                raise IndiceIndisponivel("Hash inválido no manifesto.")

    @staticmethod
    def _hash_valido(valor: Any) -> bool:
        return isinstance(valor, str) and len(valor) == 64 and all(
            c in "0123456789abcdef" for c in valor
        )

    @staticmethod
    def _normalizar_matriz(vetores: np.ndarray, quantidade: int) -> np.ndarray:
        matriz = np.asarray(vetores, dtype=np.float32)
        if matriz.ndim != 2 or matriz.shape[0] != quantidade or matriz.shape[1] == 0:
            raise ValueError("Formato de matriz de embeddings incompatível.")
        if not np.isfinite(matriz).all():
            raise ValueError("Embeddings devem conter somente valores finitos.")
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        if np.any(normas == 0):
            raise ValueError("Vetores de embedding nulos não podem ser indexados.")
        return np.ascontiguousarray(matriz / normas, dtype=np.float32)

    def _gravar_temporario(self, extensao: str, indice: Any) -> str:
        arquivo = tempfile.NamedTemporaryFile(suffix=extensao, dir=self.diretorio, delete=False)
        arquivo.close()
        try:
            self._faiss.write_index(indice, arquivo.name)
        except Exception:
            os.unlink(arquivo.name)
            raise
        return arquivo.name

    def _gravar_jsonl_temporario(self, trechos: list[TrechoConhecimento]) -> str:
        conteudo = "\n".join(trecho.model_dump_json() for trecho in trechos).encode("utf-8")
        return self._escrever_temporario(".jsonl", conteudo)

    def _escrever_temporario(self, extensao: str, conteudo: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=extensao, dir=self.diretorio, delete=False) as arquivo:
            arquivo.write(conteudo)
            return arquivo.name
