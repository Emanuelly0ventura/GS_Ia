import pytest
from pydantic import ValidationError

from app.nucleo.configuracoes import Configuracoes


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("api_json_profundidade_maxima", 0),
        ("api_json_profundidade_maxima", 129),
        ("rag_orcamento_contexto_bytes", 2047),
        ("rag_orcamento_contexto_bytes", 2_000_001),
        ("provedor_ia_limite_tokens_resposta", 0),
        ("provedor_ia_limite_tokens_resposta", 32769),
        ("provedor_ia_limite_resposta_bytes", 1023),
        ("provedor_ia_limite_resposta_bytes", 20_000_001),
        ("provedor_ia_campo_limite_tokens", "max_output_tokens"),
    ],
)
def test_limites_novos_rejeitam_valores_fora_do_intervalo(campo, valor):
    with pytest.raises(ValidationError):
        Configuracoes(**{campo: valor})


def test_limites_novos_tem_valores_padrao_documentados():
    configuracoes = Configuracoes()
    assert configuracoes.api_json_profundidade_maxima == 32
    assert configuracoes.rag_orcamento_contexto_bytes == 100_000
    assert configuracoes.provedor_ia_limite_tokens_resposta == 2048
    assert configuracoes.provedor_ia_campo_limite_tokens == "max_completion_tokens"
    assert configuracoes.provedor_ia_limite_resposta_bytes == 1_000_000
