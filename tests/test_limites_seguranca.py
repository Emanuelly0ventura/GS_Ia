import pytest
from pydantic import ValidationError

from app.nucleo.configuracoes import Configuracoes


@pytest.mark.parametrize("valor", [1023, 10_000_001])
def test_limite_global_de_corpo_http_rejeita_valores_invalidos(valor):
    with pytest.raises(ValidationError):
        Configuracoes(api_limite_corpo_http_bytes=valor)


def test_configuracao_gemini_e_centralizada_e_timeout_limitado():
    configuracoes = Configuracoes(gemini_model="modelo-config", gemini_timeout_segundos=15)
    assert configuracoes.gemini_model == "modelo-config"
    assert configuracoes.gemini_timeout_segundos == 15
    with pytest.raises(ValidationError):
        Configuracoes(gemini_timeout_segundos=0)
