from pathlib import Path
from typing import Protocol
import hashlib

import numpy as np


class EmbeddingsIndisponiveis(RuntimeError):
    pass


class CodificadorEmbeddings(Protocol):
    identificador_modelo: str
    revisao_modelo: str
    fingerprint_modelo: str
    dimensao: int
    configuracao_codificacao: dict[str, str]

    def codificar_documentos(self, textos: list[str]) -> np.ndarray: ...

    def codificar_consulta(self, texto: str) -> np.ndarray: ...


class SentenceTransformerLocal:
    """Codificador Sentence Transformers carregado somente de um diretório local."""

    def __init__(
        self,
        caminho_modelo: str | Path,
        revisao_modelo: str,
        dispositivo: str = "cpu",
        identificador_modelo: str | None = None,
        prefixo_consulta: str = "",
        prefixo_documento: str = "",
    ) -> None:
        self.caminho_modelo = Path(caminho_modelo).resolve()
        self.identificador_modelo = identificador_modelo or self.caminho_modelo.name
        self.revisao_modelo = revisao_modelo
        self.prefixo_consulta = prefixo_consulta
        self.prefixo_documento = prefixo_documento
        self.configuracao_codificacao = {
            "prefixo_consulta": prefixo_consulta,
            "prefixo_documento": prefixo_documento,
        }
        if not revisao_modelo.strip():
            raise ValueError("A revisão do modelo de embeddings precisa ser fixada.")
        if not self.caminho_modelo.is_dir():
            raise EmbeddingsIndisponiveis(
                "O modelo de embeddings local está ausente. Configure e forneça os arquivos do modelo."
            )
        self.fingerprint_modelo = self._calcular_fingerprint()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as erro:
            raise EmbeddingsIndisponiveis("Sentence Transformers não está instalado.") from erro
        try:
            self._modelo = SentenceTransformer(
                str(self.caminho_modelo),
                device=dispositivo,
                local_files_only=True,
                trust_remote_code=False,
            )
            self.dimensao = int(self._modelo.get_embedding_dimension())
        except Exception as erro:
            raise EmbeddingsIndisponiveis(
                "Não foi possível carregar o modelo local de embeddings configurado."
            ) from erro
        if self.dimensao <= 0:
            raise EmbeddingsIndisponiveis("O modelo de embeddings retornou dimensão inválida.")

    def _calcular_fingerprint(self) -> str:
        resumo = hashlib.sha256()
        arquivos = sorted(path for path in self.caminho_modelo.rglob("*") if path.is_file())
        if not arquivos:
            raise EmbeddingsIndisponiveis("O diretório do modelo de embeddings local está vazio.")
        for caminho in arquivos:
            relativo = caminho.relative_to(self.caminho_modelo).as_posix().encode("utf-8")
            resumo.update(len(relativo).to_bytes(4, "big"))
            resumo.update(relativo)
            with caminho.open("rb") as entrada:
                for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
                    resumo.update(bloco)
        return resumo.hexdigest()

    def codificar_documentos(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.empty((0, self.dimensao), dtype=np.float32)
        return self._codificar(textos, self.prefixo_documento)

    def codificar_consulta(self, texto: str) -> np.ndarray:
        if not texto.strip():
            raise ValueError("A consulta de embeddings não pode ficar vazia.")
        return self._codificar([texto], self.prefixo_consulta)[0]

    def _codificar(self, textos: list[str], prefixo: str) -> np.ndarray:
        vetores = np.asarray(
            self._modelo.encode(
                [prefixo + texto for texto in textos],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )
        if vetores.ndim != 2 or vetores.shape != (len(textos), self.dimensao):
            raise EmbeddingsIndisponiveis("O modelo de embeddings retornou formato incompatível.")
        if not np.isfinite(vetores).all():
            raise EmbeddingsIndisponiveis("O modelo de embeddings retornou valores não finitos.")
        normas = np.linalg.norm(vetores, axis=1, keepdims=True)
        if np.any(normas == 0):
            raise EmbeddingsIndisponiveis("O modelo de embeddings retornou vetor nulo.")
        return np.ascontiguousarray(vetores / normas, dtype=np.float32)
