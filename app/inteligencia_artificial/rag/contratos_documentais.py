from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

@dataclass(frozen=True)
class DocumentoTecnico:
    titulo: str
    instituicao: str
    fonte_uri: str
    trecho: str
    identificador: str
    url: str | None = None
    autor: str | None = None
    data_publicacao: date | None = None
    tipo_documento: str | None = None
    data_ingestao: datetime | None = None
    indice_trecho: int = 0
    inicio_caractere: int = 0
    fim_caractere: int = 0
    similaridade_vetorial: float = 0.0

class RecuperadorDocumental(Protocol):
    """Contrato de recuperação; não carrega índice nem acessa banco nesta fase."""
    def recuperar(
        self,
        consulta: str,
        limite: int = 5,
        limiar_similaridade: float | None = None,
    ) -> list[DocumentoTecnico]:
        ...
