from typing import Protocol

class ProvedorGenerativo(Protocol):
    """Interface de troca de provedor; não realiza chamadas nesta fase."""
    async def gerar(self, contexto: dict[str, object]) -> str:
        """Gera texto a partir de contexto validado pela aplicação."""
        ...
