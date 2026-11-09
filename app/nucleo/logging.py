import json
import logging
from datetime import datetime, timezone

from app.nucleo.configuracoes import obter_configuracoes

class FormatadorJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        evento = {
            "data_hora": datetime.fromtimestamp(registro.created, timezone.utc).isoformat(),
            "nivel": registro.levelname,
            "registrador": registro.name,
            "mensagem": registro.getMessage(),
        }
        for campo in ("ambiente", "codigo", "caminho"):
            valor = getattr(registro, campo, None)
            if valor is not None:
                evento[campo] = valor
        if registro.exc_info:
            evento["excecao"] = self.formatException(registro.exc_info)
        return json.dumps(evento, ensure_ascii=False)

def configurar_logging() -> None:
    configuracoes = obter_configuracoes()
    manipulador = logging.StreamHandler()
    manipulador.setFormatter(FormatadorJson())
    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.addHandler(manipulador)
    raiz.setLevel(configuracoes.nivel_log)

def obter_logger(nome: str) -> logging.Logger:
    return logging.getLogger(nome)
