from app.inteligencia_artificial.rag.contratos_documentais import DocumentoTecnico, RecuperadorDocumental
from app.inteligencia_artificial.rag.embeddings import CodificadorEmbeddings
from app.inteligencia_artificial.rag.indice_vetorial import IndiceVetorialLocal
from app.inteligencia_artificial.rag.esquemas import TrechoConhecimento


class RecuperadorSemantico(RecuperadorDocumental):
    def __init__(
        self,
        codificador: CodificadorEmbeddings,
        indice: IndiceVetorialLocal,
        limiar_similaridade: float,
        limite_trechos: int,
    ) -> None:
        if not isinstance(limite_trechos, int) or isinstance(limite_trechos, bool) or not 1 <= limite_trechos <= 20:
            raise ValueError("Limite configurado de trechos deve ser um inteiro entre 1 e 20.")
        self.codificador = codificador
        self.indice = indice
        self.limiar_similaridade = limiar_similaridade
        self.limite_trechos = limite_trechos

    def recuperar_com_scores(
        self,
        consulta: str,
        limite: int | None = None,
        limiar_similaridade: float | None = None,
    ) -> list[tuple[TrechoConhecimento, float]]:
        if not consulta.strip():
            raise ValueError("A consulta não pode ficar vazia.")
        limite_efetivo = self.limite_trechos if limite is None else limite
        if not isinstance(limite_efetivo, int) or isinstance(limite_efetivo, bool):
            raise ValueError("Limite de trechos deve ser um inteiro entre 1 e 20.")
        if not 1 <= limite_efetivo <= 20:
            raise ValueError("Limite de trechos deve estar entre 1 e 20.")
        if limite_efetivo > self.limite_trechos:
            raise ValueError("Limite solicitado excede o máximo configurado de trechos.")
        encontrados = self.indice.buscar(
            self.codificador.codificar_consulta(consulta),
            limite=limite_efetivo,
            limiar_similaridade=(
                self.limiar_similaridade if limiar_similaridade is None else limiar_similaridade
            ),
        )
        return encontrados

    def recuperar(
        self,
        consulta: str,
        limite: int | None = None,
        limiar_similaridade: float | None = None,
    ) -> list[DocumentoTecnico]:
        return [
            DocumentoTecnico(
                titulo=trecho.titulo,
                instituicao=trecho.instituicao,
                fonte_uri=trecho.referencia_origem,
                trecho=trecho.texto,
                identificador=trecho.identificador_documento,
                url=str(trecho.url) if trecho.url else None,
                autor=trecho.autor,
                data_publicacao=trecho.data_publicacao,
                tipo_documento=trecho.tipo_documento,
                data_ingestao=trecho.data_ingestao,
                indice_trecho=trecho.indice_trecho,
                inicio_caractere=trecho.inicio_caractere,
                fim_caractere=trecho.fim_caractere,
                similaridade_vetorial=score,
            )
            for trecho, score in self.recuperar_com_scores(
                consulta, limite, limiar_similaridade
            )
        ]
