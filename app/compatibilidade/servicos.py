from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compatibilidade.modelos import AnaliseCompatibilidade, Compatibilidade, TipoSemente, TipoSolo


class RegistroNaoEncontrado(Exception):
    pass


class RegistroInativo(Exception):
    pass


class ServicoCatalogoAgricola:
    def listar_sementes_ativas(self, sessao: Session) -> list[TipoSemente]:
        return list(sessao.scalars(select(TipoSemente).where(TipoSemente.ativo.is_(True)).order_by(TipoSemente.nome)))

    def listar_solos_ativos(self, sessao: Session) -> list[TipoSolo]:
        return list(sessao.scalars(select(TipoSolo).where(TipoSolo.ativo.is_(True)).order_by(TipoSolo.nome)))


class ServicoAnaliseCompatibilidade:
    def analisar(self, sessao: Session, semente_id: str, solo_id: str) -> AnaliseCompatibilidade:
        semente = sessao.get(TipoSemente, str(semente_id))
        solo = sessao.get(TipoSolo, str(solo_id))
        if semente is None:
            raise RegistroNaoEncontrado("Semente não encontrada.")
        if solo is None:
            raise RegistroNaoEncontrado("Tipo de solo não encontrado.")
        if not semente.ativo:
            raise RegistroInativo("Semente inativa.")
        if not solo.ativo:
            raise RegistroInativo("Tipo de solo inativo.")

        regra = sessao.scalar(
            select(Compatibilidade).where(
                Compatibilidade.semente_id == semente.id,
                Compatibilidade.solo_id == solo.id,
                Compatibilidade.ativo.is_(True),
            )
        )
        analise = AnaliseCompatibilidade(
            id=str(uuid4()),
            semente_id=semente.id,
            solo_id=solo.id,
            compatibilidade_id=regra.id if regra else None,
            semente_codigo=semente.codigo,
            semente_nome=semente.nome,
            solo_codigo=solo.codigo,
            solo_nome=solo.nome,
            resultado=regra.resultado if regra else "DADOS_INSUFICIENTES",
            criterios=list(regra.criterios) if regra else [],
            justificativa=regra.justificativa if regra else None,
            referencia_fonte=regra.referencia_fonte if regra else None,
        )
        sessao.add(analise)
        sessao.flush()
        return analise