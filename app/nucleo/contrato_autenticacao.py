from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class IdentidadeAutenticada:
    """Identidade normalizada após validação do token pelo emissor oficial."""
    identificador: str
    claims: dict[str, object]

class ValidadorToken(Protocol):
    """Contrato futuro. Não valida tokens nesta fase."""
    def validar(self, token: str) -> IdentidadeAutenticada:
        """Valida assinatura e claims conforme contrato confirmado pelo Backend C#."""
        ...
