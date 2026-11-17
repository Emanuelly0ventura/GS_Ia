from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compatibilidade.modelos import TipoSemente, TipoSolo

SEMENTES_INICIAIS = (
    ("5a2212bb-aabc-52a3-8fe4-baf6485e7f12", "ALFACE", "Alface"),
    ("8d0ed8f2-9bc5-5fa6-a990-a4f45dd6ae46", "TOMATE", "Tomate"),
    ("9a457e78-16d3-5c11-8912-bc1057356894", "MILHO", "Milho"),
    ("154020c4-14a8-508f-83b3-6cf5d1fb057a", "FEIJAO", "Feijão"),
    ("c9e7d90d-3095-5658-8cab-8d4d53949920", "CENOURA", "Cenoura"),
)

SOLOS_INICIAIS = (
    ("39406008-265c-57b0-a092-006bf86f983c", "ARENOSO", "Arenoso"),
    ("d020eefd-5c33-560c-a940-fdb03869737e", "ARGILOSO", "Argiloso"),
    ("c7aa4255-6e58-5c85-a108-f38d011981e2", "SILTOSO", "Siltoso"),
    ("d2fef8ec-71de-5732-aaf1-a2d7d9cb6575", "HUMOSO", "Humoso"),
    ("57467907-fc4a-509e-b02e-0d0213d2c62c", "FRANCO", "Franco (misto)"),
)


def carregar_catalogos_iniciais(sessao: Session) -> tuple[int, int]:
    """Inclui apenas códigos ausentes; não reativa nem renomeia registros existentes."""
    novas_sementes = 0
    novos_solos = 0
    codigos_semente = set(sessao.scalars(select(TipoSemente.codigo)))
    codigos_solo = set(sessao.scalars(select(TipoSolo.codigo)))
    for identificador, codigo, nome in SEMENTES_INICIAIS:
        if codigo not in codigos_semente:
            sessao.add(TipoSemente(id=identificador, codigo=codigo, nome=nome, ativo=True))
            novas_sementes += 1
    for identificador, codigo, nome in SOLOS_INICIAIS:
        if codigo not in codigos_solo:
            sessao.add(TipoSolo(id=identificador, codigo=codigo, nome=nome, ativo=True))
            novos_solos += 1
    return novas_sementes, novos_solos