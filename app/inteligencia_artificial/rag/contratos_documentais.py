from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class DocumentoTecnico:
    titulo: str
    instituicao: str
    fonte_uri: str
    trecho: str
    identificador: str

class RecuperadorDocumental(Protocol):
    """Contrato de recuperação; não carrega índice nem acessa banco nesta fase."""
    def recuperar(self, consulta: str, limite: int = 5) -> list[DocumentoTecnico]:
        ...
