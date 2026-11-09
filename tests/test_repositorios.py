import json
from pathlib import Path
from uuid import UUID

import pytest

from app.repositorios.adaptadores import AdaptadorPostgreSQLConfiguravel
from tests.suporte.repositorio_fixture import RepositorioFixture

DIRETORIO_FIXTURAS = Path(__file__).parent / "fixtures"
ID_USUARIO = "usuario-teste-01"
ID_TALHAO = "00000000-0000-4000-8000-000000000001"
ID_DISPOSITIVO = "00000000-0000-4000-8000-000000000002"

def carregar_fixture(nome: str) -> dict:
    return json.loads((DIRETORIO_FIXTURAS / nome).read_text(encoding="utf-8"))

def test_fixture_normal_marcada_como_simulada_e_autorizada():
    repositorio = RepositorioFixture(carregar_fixture("normal.json"))
    assert repositorio.usuario_pode_acessar(ID_USUARIO, ID_TALHAO, ID_DISPOSITIVO)
    assert len(repositorio.consultar_historico(ID_DISPOSITIVO)) == 1
    assert repositorio.consultar_contexto(ID_TALHAO) is not None

def test_fixture_nao_concede_acesso_a_outro_usuario():
    repositorio = RepositorioFixture(carregar_fixture("sem_acesso.json"))
    assert not repositorio.usuario_pode_acessar(ID_USUARIO, ID_TALHAO, ID_DISPOSITIVO)

def test_fixture_sem_historico_permanece_vazia():
    repositorio = RepositorioFixture(carregar_fixture("historico_insuficiente.json"))
    assert repositorio.consultar_historico(ID_DISPOSITIVO) == []

def test_fixture_sem_origem_simulada_e_rejeitada():
    with pytest.raises(ValueError):
        RepositorioFixture({"metadados": {"origem": "REAL"}})

def test_adaptador_nao_executa_sem_mapeamento_confirmado():
    adaptador = AdaptadorPostgreSQLConfiguravel(engine=None, consultas={})  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="mapeamento aprovado"):
        adaptador.consultar("historico", {"id_dispositivo": str(UUID(ID_DISPOSITIVO))})

def test_adaptador_rejeita_sql_que_nao_seja_select():
    adaptador = AdaptadorPostgreSQLConfiguravel(engine=None, consultas={"historico": "DELETE FROM qualquer_coisa"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="SELECT"):
        adaptador.consultar("historico", {})

def test_adaptador_rejeita_multiplos_comandos():
    adaptador = AdaptadorPostgreSQLConfiguravel(engine=None, consultas={"historico": "SELECT 1; SELECT 2"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ponto e vírgula"):
        adaptador.consultar("historico", {})

def test_adaptador_envia_parametros_separados_do_sql():
    class Resultado:
        def mappings(self):
            return [{"valor_canonico": 12.5}]

    class Conexao:
        def __init__(self):
            self.sql = None
            self.parametros = None
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, sql, parametros):
            self.sql = sql
            self.parametros = parametros
            return Resultado()

    class EngineFalso:
        def __init__(self):
            self.conexao = Conexao()
        def connect(self):
            return self.conexao

    engine = EngineFalso()
    adaptador = AdaptadorPostgreSQLConfiguravel(
        engine=engine,  # type: ignore[arg-type]
        consultas={"historico": "SELECT :id_dispositivo AS valor_canonico"},
    )
    resultado = adaptador.consultar("historico", {"id_dispositivo": "id-com-aspas-'"})

    assert resultado == [{"valor_canonico": 12.5}]
    assert ":id_dispositivo" in str(engine.conexao.sql)
    assert engine.conexao.parametros == {"id_dispositivo": "id-com-aspas-'"}
