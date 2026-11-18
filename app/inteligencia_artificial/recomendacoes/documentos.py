from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, TypeAdapter

CAMINHO = Path(__file__).resolve().parents[3] / "base_conhecimento" / "documentos_agricolas.json"


class DocumentoTecnico(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    titulo: str
    instituicao: str
    localizador: HttpUrl
    publicacao: date | None = None
    trecho: str
    curadoria: Literal["FONTE_CONFERIDA", "PENDENTE"]
    culturas: list[str]
    solos: list[str]
    assunto: Literal["SOLO", "AMBIENTE"]


def recuperar_documentos(cultura: str, solo: str, tem_leitura: bool, caminho: Path = CAMINHO):
    documentos = TypeAdapter(list[DocumentoTecnico]).validate_json(caminho.read_bytes())
    ids = {doc.id for doc in documentos}
    if len(ids) != len(documentos):
        raise ValueError("Documentos técnicos com identificadores duplicados.")
    pertinentes = [
        doc for doc in documentos
        if (not doc.culturas or cultura in doc.culturas)
        and (not doc.solos or solo in doc.solos)
        and (doc.assunto != "AMBIENTE" or tem_leitura)
    ]
    pertinentes.sort(key=lambda doc: (-bool(doc.culturas) - bool(doc.solos), doc.id))
    return pertinentes[:4]
