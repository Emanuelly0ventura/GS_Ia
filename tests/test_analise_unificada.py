from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.compatibilidade import analise_unificada as unificada
from app.compatibilidade.modelos import TipoSemente, TipoSolo
from app.inteligencia_artificial.generativa.cliente_gemini import GeminiExpirou
from app.inteligencia_artificial.recomendacoes.documentos import recuperar_documentos
from app.telemetria.esquemas import UNIDADES_CANONICAS
from app.telemetria.modelos import AnaliseAnomalia, Dispositivo, Leitura


class GeminiTeste:
    def __init__(self, modo="ok"):
        self.modo = modo
        self.contexto = None

    async def gerar(self, *, instrucao, dados, esquema):
        self.contexto = dados
        if self.modo == "timeout":
            raise GeminiExpirou("timeout")
        return esquema(
            mensagem="A textura do solo influencia a retenção de água.",
            orientacoes=["Compare a textura com as condições registradas."],
            ressalvas=[],
            referencias=["inventada"] if self.modo == "invalida" else [],
        )


@pytest.mark.parametrize(
    ("modo", "estado"), [("ok", "CONCLUIDA"), ("timeout", "FALHA_GEMINI"), ("invalida", "RESPOSTA_INVALIDA")]
)
def test_geracao(modo, estado):
    import asyncio

    gerador = GeminiTeste(modo)
    contexto = {"documentos": [], "compatibilidade": {"resultado": "DADOS_INSUFICIENTES"}, "leitura": None}
    obtido, mensagem, _ = asyncio.run(unificada.gerar_mensagem(contexto, gerador))
    assert obtido == estado
    assert (mensagem is not None) == (modo == "ok")
    assert gerador.contexto == contexto


def test_rag_filtra_e_ordena_por_cultura_e_solo():
    docs = recuperar_documentos("MILHO", "ARENOSO", True)
    assert [doc.id for doc in docs] == ["embrapa-milho-textura", "embrapa-agua-solo-arenoso"]
    assert recuperar_documentos("CULTURA_SEM_CADASTRO", "ARGILOSO", False) == []
    assert {doc.id for doc in recuperar_documentos("ALFACE", "ARENOSO", False)} == {
        "incaper-alface-solo", "embrapa-agua-solo-arenoso",
    }


@pytest.mark.parametrize("cultura", ["ALFACE", "TOMATE", "MILHO", "FEIJAO", "CENOURA"])
@pytest.mark.parametrize("solo", ["ARENOSO", "ARGILOSO", "SILTOSO", "HUMOSO", "FRANCO"])
def test_rag_cobre_catalogo_agricola_mesmo_sem_telemetria(cultura, solo):
    fontes = recuperar_documentos(cultura, solo, False)
    assert any(cultura in fonte.culturas for fonte in fontes)


@pytest.mark.integration
def test_fluxo_postgresql_com_fallback_e_anomalia():
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    url = os.getenv("TEST_TELEMETRY_DATABASE_URL")
    if not url:
        pytest.skip("Configure TEST_TELEMETRY_DATABASE_URL.")
    destino = make_url(url)
    assert destino.get_backend_name() == "postgresql" and destino.database.endswith("_test")
    engine = create_engine(url)
    gerador = GeminiTeste()
    app = FastAPI()
    app.include_router(unificada.roteador)
    app.dependency_overrides[unificada.obter_provedor] = lambda: gerador
    agora = datetime.now(UTC)
    origem = unificada.ORIGEM_WOKWI
    valores = {"temperaturaAr": 28.0, "umidadeAr": 72.0, "umidadeSolo": 50.0, "luminosidade": 1234.0}
    metadados = {"origem": "DHT22_TEMPERATURA", "simulado": True,
                 "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA", "temperaturaFonteC": 25.0}

    def leitura(dispositivo, instante, values, units, complements):
        return Leitura(
            device_id=dispositivo.device_id, observation_id=str(uuid4()), measured_at=instante,
            source=origem, quality="VALID", values=values, units=units, complements=complements,
        )

    try:
        with engine.connect() as conexao, Session(bind=conexao, join_transaction_mode="create_savepoint") as sessao:
            conexao.begin()
            app.dependency_overrides[unificada.obter_sessao] = lambda: sessao
            dispositivo = Dispositivo(device_id=str(uuid4()), source=origem)
            sessao.add(dispositivo)
            sessao.flush()
            valida = leitura(dispositivo, agora - timedelta(seconds=2), valores, UNIDADES_CANONICAS,
                            {"umidadeSolo": metadados})
            valida.analysis_status = "CONCLUIDA"
            valida.anomaly = AnaliseAnomalia(
                model_version="isolation-forest-teste", is_anomaly=True, score=-0.3,
                analyzed_at=agora, variables=list(UNIDADES_CANONICAS), explanation="Atipicidade estatística.",
            )
            invalida = leitura(dispositivo, agora, {**valores, "umidadeSolo": 72.0}, UNIDADES_CANONICAS,
                               {"umidadeSolo": metadados})
            antiga = leitura(dispositivo, agora - timedelta(days=2), valores, UNIDADES_CANONICAS,
                            {"umidadeSolo": metadados})
            sessao.add_all([valida, invalida, antiga])
            sessao.flush()
            observacao = valida.observation_id
            semente = sessao.scalar(select(TipoSemente).where(TipoSemente.codigo == "MILHO"))
            solo = sessao.scalar(select(TipoSolo).where(TipoSolo.codigo == "ARENOSO"))
            sementes = {"sementeId": semente.id, "soloId": solo.id}
            with TestClient(app) as cliente:
                resposta = cliente.post("/api/v1/agricultura/analise-unificada", json=sementes)
                assert resposta.status_code == 200
                dados = resposta.json()
                assert dados["leitura"]["observationId"] == observacao
                assert dados["leitura"]["values"]["umidadeAr"] == 72.0
                assert dados["leitura"]["values"]["umidadeSolo"] == 50.0
                assert dados["compatibilidade"]["resultado"] == "INCOMPATIVEL"
                assert dados["anomalia"]["score"] == -0.3
                assert dados["estadoRag"] == "CONCLUIDA"
                assert dados["estadoGemini"] == "CONCLUIDA"
                assert gerador.contexto["anomalia"]["modelVersion"] == "isolation-forest-teste"
                historico = cliente.get("/api/v1/agricultura/analises").json()
                gravada = next(item for item in historico if item["id"] == dados["id"])
                assert gravada["resultado"] == "INCOMPATIVEL"
                assert gravada["estadoExplicacao"] == "CONCLUIDA"
                assert gravada["explicacaoGemini"] == dados["geracao"]["mensagem"]

                gerador.modo = "timeout"
                falha = cliente.post("/api/v1/agricultura/analise-unificada", json=sementes)
                assert falha.status_code == 200
                assert falha.json()["estadoGemini"] == "FALHA_GEMINI"
                historico = cliente.get("/api/v1/agricultura/analises").json()
                gravada = next(item for item in historico if item["id"] == falha.json()["id"])
                assert gravada["resultado"] == "INCOMPATIVEL"
                assert gravada["estadoExplicacao"] == "FALHA"
                assert gravada["codigoErroExplicacao"] == "GEMINI_TIMEOUT"

                assert cliente.post("/api/v1/agricultura/analise-unificada",
                                    json={**sementes, "soloId": str(uuid4())}).status_code == 404
    finally:
        engine.dispose()
