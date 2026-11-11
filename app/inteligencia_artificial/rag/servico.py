from app.inteligencia_artificial.generativa.provedor_chat_completions import ProvedorNaoConfigurado
from app.inteligencia_artificial.generativa.contrato_provedor import ProvedorGenerativo
from app.inteligencia_artificial.rag.contexto import construir_contexto, serializar_contexto
from app.inteligencia_artificial.rag.embeddings import CodificadorEmbeddings
from app.inteligencia_artificial.rag.indice_vetorial import IndiceVetorialLocal
from app.inteligencia_artificial.rag.recuperacao import RecuperadorSemantico
from app.inteligencia_artificial.rag.respostas import (
    FonteRecuperada,
    RespostaAnaliseAgronomica,
    validar_resposta_gerada,
)
from app.inteligencia_artificial.rag.esquemas import TrechoConhecimento


class ServicoRAG:
    def __init__(
        self,
        codificador: CodificadorEmbeddings,
        indice: IndiceVetorialLocal,
        limiar_similaridade: float = 0.55,
        limite_trechos: int = 5,
        limite_contexto_bytes: int = 100_000,
    ) -> None:
        if not -1.0 <= limiar_similaridade <= 1.0:
            raise ValueError("Limiar de similaridade vetorial deve estar entre -1 e 1.")
        if limite_trechos < 1 or limite_trechos > 20:
            raise ValueError("Limite de trechos deve estar entre 1 e 20.")
        if not isinstance(limite_contexto_bytes, int) or isinstance(limite_contexto_bytes, bool) or not 2048 <= limite_contexto_bytes <= 2_000_000:
            raise ValueError("Orçamento de contexto deve estar entre 2048 e 2000000 bytes.")
        self.codificador = codificador
        self.indice = indice
        self.limiar_similaridade = limiar_similaridade
        self.limite_trechos = limite_trechos
        self.limite_contexto_bytes = limite_contexto_bytes
        self.recuperador = RecuperadorSemantico(
            codificador, indice, limiar_similaridade, limite_trechos
        )

    def buscar(self, pergunta: str) -> list[tuple[TrechoConhecimento, float]]:
        return self.recuperador.recuperar_com_scores(pergunta)

    async def analisar(
        self,
        pergunta: str,
        dados_agricolas: dict[str, object],
        provedor: ProvedorGenerativo | None,
        resultado_anomalia: dict[str, object] | None = None,
    ) -> RespostaAnaliseAgronomica:
        trechos = self.buscar(pergunta)
        if not trechos:
            return RespostaAnaliseAgronomica(
                status="EVIDENCIA_INSUFICIENTE",
                resposta=("Não encontrei trechos acima do limiar de busca configurado. "
                          "Isso não demonstra ausência de conhecimento técnico; forneça fontes pertinentes "
                          "ou consulte um profissional agrônomo."),
                fatos_documentados=[],
                interpretacoes=[],
                fontes_utilizadas=[],
                trechos_recuperados=[],
                evidencias_suficientes=False,
                limitacoes=[
                    "A base local pode estar vazia ou não cobrir esta pergunta.",
                    "Similaridade vetorial não comprova relevância científica.",
                ],
                consultar_agronomo=True,
            )
        if provedor is None:
            raise ProvedorNaoConfigurado("Nenhum provedor generativo está configurado.")
        contexto = construir_contexto(pergunta, dados_agricolas, trechos, resultado_anomalia)
        serializar_contexto(contexto, self.limite_contexto_bytes)
        bruto = await provedor.gerar(contexto)
        resposta = validar_resposta_gerada(bruto, trechos)
        return RespostaAnaliseAgronomica(
            status="ANALISE_GERADA" if resposta.evidencias_suficientes else "EVIDENCIA_INSUFICIENTE",
            resposta=resposta.resposta,
            fatos_documentados=resposta.fatos_documentados,
            interpretacoes=resposta.interpretacoes,
            fontes_utilizadas=resposta.fontes_utilizadas,
            trechos_recuperados=[
                FonteRecuperada(trecho=trecho, similaridade_vetorial=score)
                for trecho, score in trechos
            ],
            evidencias_suficientes=resposta.evidencias_suficientes,
            limitacoes=resposta.limitacoes,
            consultar_agronomo=resposta.consultar_agronomo,
        )

    def contexto_serializado(
        self,
        pergunta: str,
        dados_agricolas: dict[str, object],
        trechos: list[tuple[TrechoConhecimento, float]],
        resultado_anomalia: dict[str, object] | None = None,
    ) -> str:
        return serializar_contexto(
            construir_contexto(pergunta, dados_agricolas, trechos, resultado_anomalia),
            self.limite_contexto_bytes,
        )
