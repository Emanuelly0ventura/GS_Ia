from datetime import date, datetime, timezone

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class DocumentoConhecimento(BaseModel):
    """Documento local de origem rastreável; não implica validação científica."""

    model_config = ConfigDict(extra="forbid", frozen=True, alias_generator=to_camel, populate_by_name=True)

    identificador: str = Field(min_length=1, max_length=200)
    titulo: str = Field(min_length=1, max_length=500)
    instituicao: str = Field(min_length=1, max_length=300)
    referencia_origem: str = Field(min_length=1, max_length=2000)
    conteudo: str = Field(min_length=1)
    url: AnyHttpUrl | None = None
    autor: str | None = Field(default=None, max_length=500)
    data_publicacao: date | None = None
    tipo_documento: str | None = Field(default=None, max_length=120)
    data_ingestao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("identificador", "titulo", "instituicao", "referencia_origem", "conteudo")
    @classmethod
    def validar_texto_obrigatorio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo obrigatório não pode ficar vazio.")
        return valor

    @field_validator("autor", "tipo_documento")
    @classmethod
    def normalizar_texto_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        normalizado = valor.strip()
        return normalizado or None


class TrechoConhecimento(BaseModel):
    """Trecho indexável com origem e posição suficientes para auditoria."""

    model_config = ConfigDict(extra="forbid", frozen=True, alias_generator=to_camel, populate_by_name=True)

    identificador_documento: str
    titulo: str
    instituicao: str
    referencia_origem: str
    url: AnyHttpUrl | None = None
    autor: str | None = None
    data_publicacao: date | None = None
    tipo_documento: str | None = None
    data_ingestao: datetime
    indice_trecho: int = Field(ge=0)
    inicio_caractere: int = Field(ge=0)
    fim_caractere: int = Field(gt=0)
    texto: str = Field(min_length=1)

    @classmethod
    def a_partir_do_documento(
        cls,
        documento: DocumentoConhecimento,
        indice_trecho: int,
        inicio: int,
        fim: int,
        texto: str,
    ) -> "TrechoConhecimento":
        return cls(
            identificador_documento=documento.identificador,
            titulo=documento.titulo,
            instituicao=documento.instituicao,
            referencia_origem=documento.referencia_origem,
            url=documento.url,
            autor=documento.autor,
            data_publicacao=documento.data_publicacao,
            tipo_documento=documento.tipo_documento,
            data_ingestao=documento.data_ingestao,
            indice_trecho=indice_trecho,
            inicio_caractere=inicio,
            fim_caractere=fim,
            texto=texto,
        )
