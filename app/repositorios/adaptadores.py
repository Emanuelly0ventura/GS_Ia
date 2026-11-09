from typing import Any

class AdaptadorConsultaProvisorio:
    """Ponto de extensão até o Backend C# confirmar schema, nomes e relacionamentos.

    Não executa SQL nem presume tabelas/colunas. A implementação concreta será
    fornecida na Fase 2 após aprovação do contrato de integração.
    """
    def __init__(self, mapeamento: dict[str, Any] | None = None) -> None:
        self.mapeamento = mapeamento or {}

    def validar_mapeamento(self) -> None:
        if not self.mapeamento:
            raise NotImplementedError("Mapeamento do PostgreSQL depende do contrato do Backend C#.")
