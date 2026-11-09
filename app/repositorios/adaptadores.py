import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

class AdaptadorPostgreSQLConfiguravel:
    """Executa consultas SELECT definidas por mapeamento externo aprovado.

    Não inclui nomes de schemas/tabelas/colunas nem consultas padrão. O Engine
    deve vir de criar_engine_leitura() e o SQL deve usar parâmetros nomeados.
    """
    def __init__(self, engine: Engine, consultas: dict[str, str]) -> None:
        self._engine = engine
        self._consultas = dict(consultas)

    def consultar(self, operacao: str, parametros: dict[str, object]) -> list[dict[str, Any]]:
        sql = self._consultas.get(operacao)
        if not sql:
            raise NotImplementedError(f"Consulta '{operacao}' depende do mapeamento aprovado pelo Backend C#.")
        self._validar_select(sql)
        with self._engine.connect() as conexao:
            resultado = conexao.execute(text(sql), parametros)
            return [dict(linha) for linha in resultado.mappings()]

    @staticmethod
    def _validar_select(sql: str) -> None:
        consulta = sql.strip()
        if not re.match(r"(?is)^select\b", consulta) or ";" in consulta:
            raise ValueError("Cada mapeamento deve conter uma única consulta SELECT, sem ponto e vírgula.")

    def _consultar_unico(self, operacao: str, parametros: dict[str, object]) -> dict[str, Any] | None:
        linhas = self.consultar(operacao, parametros)
        if len(linhas) > 1:
            raise ValueError(f"A consulta '{operacao}' retornou mais de um registro para uma chave lógica.")
        return linhas[0] if linhas else None

    def usuario_pode_acessar(self, id_usuario: str, id_talhao: UUID, id_dispositivo: UUID) -> bool:
        linha = self._consultar_unico("autorizacao", {"id_usuario": id_usuario, "id_talhao": str(id_talhao), "id_dispositivo": str(id_dispositivo)})
        if linha is None:
            return False
        if "acesso_permitido" not in linha or not isinstance(linha["acesso_permitido"], bool):
            raise ValueError("A consulta de autorização deve retornar o alias canônico booleano 'acesso_permitido'.")
        return linha["acesso_permitido"]

    def consultar_propriedade(self, id_talhao: UUID) -> dict[str, Any] | None:
        return self._consultar_unico("propriedade", {"id_talhao": str(id_talhao)})

    def consultar_talhao(self, id_talhao: UUID) -> dict[str, Any] | None:
        return self._consultar_unico("talhao", {"id_talhao": str(id_talhao)})

    def consultar_plantio(self, id_talhao: UUID) -> dict[str, Any] | None:
        return self._consultar_unico("plantio", {"id_talhao": str(id_talhao)})

    def consultar_cultura(self, id_plantio: str) -> dict[str, Any] | None:
        return self._consultar_unico("cultura", {"id_plantio": id_plantio})

    def consultar_semente(self, id_plantio: str) -> dict[str, Any] | None:
        return self._consultar_unico("semente", {"id_plantio": id_plantio})

    def consultar_solo(self, id_talhao: UUID) -> dict[str, Any] | None:
        return self._consultar_unico("solo", {"id_talhao": str(id_talhao)})

    def consultar_parametros_agronomicos(self, id_plantio: str) -> list[dict[str, Any]]:
        return self.consultar("parametros_agronomicos", {"id_plantio": id_plantio})

    def consultar_dispositivo(self, id_dispositivo: UUID) -> dict[str, Any] | None:
        return self._consultar_unico("dispositivo", {"id_dispositivo": str(id_dispositivo)})

    def consultar_sensores(self, id_dispositivo: UUID) -> list[dict[str, Any]]:
        return self.consultar("sensores", {"id_dispositivo": str(id_dispositivo)})

    def consultar_eventos_e_qualidade(self, id_dispositivo: UUID, inicio: datetime, fim: datetime) -> list[dict[str, Any]]:
        return self.consultar("eventos_qualidade", {"id_dispositivo": str(id_dispositivo), "inicio": inicio, "fim": fim})

    def consultar_historico(self, id_dispositivo: UUID, inicio: datetime, fim: datetime) -> list[dict[str, Any]]:
        return self.consultar("historico", {"id_dispositivo": str(id_dispositivo), "inicio": inicio, "fim": fim})
