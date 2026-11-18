import asyncio
import json
import math
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError


class ErroGemini(RuntimeError):
    """Erro sanitizado do provedor Gemini."""

    codigo = "GEMINI_ERROR"


class GeminiNaoConfigurado(ErroGemini):
    codigo = "GEMINI_NOT_CONFIGURED"


class GeminiExpirou(ErroGemini):
    codigo = "GEMINI_TIMEOUT"


class GeminiLimiteRequisicoes(ErroGemini):
    codigo = "GEMINI_RATE_LIMITED"


class GeminiIndisponivel(ErroGemini):
    codigo = "GEMINI_UNAVAILABLE"


class GeminiRespostaInvalida(ErroGemini):
    codigo = "GEMINI_INVALID_RESPONSE"


ModeloSaida = TypeVar("ModeloSaida", bound=BaseModel)


class ClienteGenerativo(Protocol):
    async def gerar(
        self,
        *,
        instrucao: str,
        dados: dict[str, object],
        esquema: type[ModeloSaida],
    ) -> ModeloSaida: ...


class ProvedorGemini:
    """Adaptador exclusivo Gemini; SDK importado só quando há geração solicitada."""

    def __init__(
        self,
        api_key: str | None,
        modelo: str | None,
        timeout_segundos: float = 20,
        cliente: object | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._modelo = (modelo or "").strip()
        self._timeout = timeout_segundos
        self._cliente_injetado = cliente
        if not math.isfinite(timeout_segundos) or timeout_segundos <= 0 or timeout_segundos > 120:
            raise ValueError("Timeout Gemini deve estar entre 0 e 120 segundos.")

    @staticmethod
    def _status_http(erro: Exception) -> int | None:
        for nome in ("code", "status_code"):
            valor = getattr(erro, nome, None)
            if isinstance(valor, int) and not isinstance(valor, bool):
                return valor
        resposta = getattr(erro, "response", None)
        valor = getattr(resposta, "status_code", None)
        return valor if isinstance(valor, int) and not isinstance(valor, bool) else None

    async def gerar(
        self,
        *,
        instrucao: str,
        dados: dict[str, object],
        esquema: type[ModeloSaida],
    ) -> ModeloSaida:
        if not self._api_key or not self._modelo:
            raise GeminiNaoConfigurado("GEMINI_API_KEY e GEMINI_MODEL precisam estar configurados.")
        try:
            conteudo = json.dumps(dados, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise GeminiRespostaInvalida("Os dados para geração não formam JSON válido.") from None

        cliente = self._cliente_injetado
        cliente_proprio = cliente is None
        try:
            if cliente_proprio:
                try:
                    from google import genai
                except ImportError:
                    raise GeminiNaoConfigurado("O SDK google-genai não está instalado.") from None
                # Uma tentativa por chamada: 429 é devolvido ao serviço sem retry automático.
                cliente = genai.Client(
                    api_key=self._api_key,
                    http_options={"retry_options": {"attempts": 1}},
                )

            async with asyncio.timeout(self._timeout):
                resposta = await cliente.aio.models.generate_content(  # type: ignore[union-attr]
                    model=self._modelo,
                    contents=conteudo,
                    config={
                        "system_instruction": instrucao,
                        **({} if self._modelo == "gemini-3.8-flash" else {"temperature": 0}),
                        "response_mime_type": "application/json",
                        "response_json_schema": esquema.model_json_schema(),
                    },
                )
            texto = getattr(resposta, "text", None)
            if not isinstance(texto, str) or not texto.strip():
                raise GeminiRespostaInvalida("O Gemini retornou uma resposta vazia ou sem texto.")
            try:
                return esquema.model_validate_json(texto)
            except (ValidationError, ValueError):
                raise GeminiRespostaInvalida("A resposta do Gemini não corresponde ao contrato esperado.") from None
        except (GeminiNaoConfigurado, GeminiRespostaInvalida):
            raise
        except TimeoutError:
            raise GeminiExpirou("A solicitação ao Gemini excedeu o tempo limite.") from None
        except Exception as erro:
            if self._status_http(erro) == 429:
                raise GeminiLimiteRequisicoes("O Gemini limitou temporariamente as requisições.") from None
            raise GeminiIndisponivel("O serviço Gemini está indisponível no momento.") from None
        finally:
            if cliente_proprio and cliente is not None:
                try:
                    await cliente.aio.aclose()  # type: ignore[union-attr]
                except Exception:
                    pass
                try:
                    cliente.close()
                except Exception:
                    pass
