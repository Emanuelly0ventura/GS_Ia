from app.inteligencia_artificial.generativa.cliente_gemini import ProvedorGemini
from app.nucleo.configuracoes import Configuracoes, obter_configuracoes


def criar_provedor_gemini(configuracoes: Configuracoes | None = None) -> ProvedorGemini:
    """Cria só o adaptador; não importa nem inicializa o SDK até a primeira chamada."""
    configuracoes = configuracoes or obter_configuracoes()
    chave = configuracoes.gemini_api_key
    return ProvedorGemini(
        api_key=chave.get_secret_value() if chave else None,
        modelo=configuracoes.gemini_model,
        timeout_segundos=configuracoes.gemini_timeout_segundos,
    )
