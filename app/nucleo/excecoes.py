class ErroAplicacao(Exception):
    def __init__(self, codigo: str, mensagem: str, status_code: int = 400) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_code = status_code
