from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LimiteCorpoHttpMiddleware:
    """Impõe teto de bytes antes da aplicação materializar o corpo da requisição."""

    def __init__(self, app: ASGIApp, limite_bytes: int) -> None:
        if not isinstance(limite_bytes, int) or isinstance(limite_bytes, bool) or limite_bytes < 1:
            raise ValueError("O limite do corpo HTTP precisa ser um inteiro positivo.")
        self.app = app
        self.limite_bytes = limite_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        valores_tamanho = [
            valor for nome, valor in scope.get("headers", [])
            if nome.lower() == b"content-length"
        ]
        if valores_tamanho:
            try:
                tamanhos = {int(valor) for valor in valores_tamanho}
                if len(tamanhos) != 1 or next(iter(tamanhos)) < 0:
                    await self._responder(send, 400, "Cabeçalho Content-Length inválido.")
                    return
                if next(iter(tamanhos)) > self.limite_bytes:
                    await self._responder(send, 413, "O corpo da requisição excede o limite permitido.")
                    return
            except ValueError:
                await self._responder(send, 400, "Cabeçalho Content-Length inválido.")
                return

        partes: list[bytes] = []
        total = 0
        while True:
            mensagem = await receive()
            if mensagem["type"] == "http.disconnect":
                return
            if mensagem["type"] != "http.request":
                continue
            parte = mensagem.get("body", b"")
            total += len(parte)
            if total > self.limite_bytes:
                await self._responder(send, 413, "O corpo da requisição excede o limite permitido.")
                return
            if parte:
                partes.append(parte)
            if not mensagem.get("more_body", False):
                break

        corpo = b"".join(partes)
        replayado = False

        async def receber_corpo_limitado() -> Message:
            nonlocal replayado
            if not replayado:
                replayado = True
                return {"type": "http.request", "body": corpo, "more_body": False}
            return await receive()

        await self.app(scope, receber_corpo_limitado, send)

    @staticmethod
    async def _responder(send: Send, status: int, mensagem: str) -> None:
        corpo = (
            '{"erro":{"codigo":"PAYLOAD_TOO_LARGE","mensagem":"'
            + mensagem
            + '"}}'
        ).encode("utf-8")
        if status == 400:
            corpo = b'{"erro":{"codigo":"HTTP_ERROR","mensagem":"Cabecalho Content-Length invalido."}}'
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(corpo)).encode("ascii"))],
        })
        await send({"type": "http.response.body", "body": corpo})
