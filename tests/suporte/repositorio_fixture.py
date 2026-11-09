from typing import Any

class RepositorioFixture:
    """Repositório em memória exclusivo de testes; nunca importado pela aplicação."""
    def __init__(self, dados: dict[str, Any]) -> None:
        if dados.get("metadados", {}).get("origem") != "SIMULADO_TESTE":
            raise ValueError("Fixture sem identificação explícita de origem simulada.")
        self._dados = dados

    def usuario_pode_acessar(self, id_usuario: str, id_talhao: str, id_dispositivo: str) -> bool:
        return any(
            acesso.get("idUsuario") == id_usuario
            and acesso.get("idTalhao") == id_talhao
            and acesso.get("idDispositivo") == id_dispositivo
            and acesso.get("permitido") is True
            for acesso in self._dados.get("acessos", [])
        )

    def consultar_historico(self, id_dispositivo: str) -> list[dict[str, Any]]:
        return [linha for linha in self._dados.get("leituras", []) if linha.get("idDispositivo") == id_dispositivo]

    def consultar_contexto(self, id_talhao: str) -> dict[str, Any] | None:
        contexto = self._dados.get("contexto")
        if contexto and contexto.get("talhao", {}).get("idTalhao") == id_talhao:
            return contexto
        return None
