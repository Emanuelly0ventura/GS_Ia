from collections import OrderedDict
from threading import Lock
from time import monotonic


class LimitadorTaxaMemoria:
    """Janela fixa por chave/cliente; estado local ao processo, com cardinalidade limitada."""

    def __init__(self, maximo_clientes: int = 10000) -> None:
        self.maximo_clientes = maximo_clientes
        self._janelas: OrderedDict[tuple[str, int], tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    def permitir(
        self,
        cliente: str,
        maximo_requisicoes: int,
        janela_segundos: int,
        agora: float | None = None,
    ) -> tuple[bool, int]:
        instante = monotonic() if agora is None else agora
        chave = (cliente, janela_segundos)
        inicio_janela = instante - instante % janela_segundos
        with self._lock:
            expiradas = [
                k for k, (inicio, _) in self._janelas.items()
                if inicio + k[1] <= instante
            ]
            for k in expiradas:
                self._janelas.pop(k, None)

            inicio, quantidade = self._janelas.get(chave, (inicio_janela, 0))
            if inicio != inicio_janela:
                inicio, quantidade = inicio_janela, 0
            if quantidade >= maximo_requisicoes:
                if chave in self._janelas:
                    self._janelas.move_to_end(chave, last=True)
                return False, max(1, int(inicio + janela_segundos - instante + 0.999))
            self._janelas[chave] = (inicio, quantidade + 1)
            self._janelas.move_to_end(chave)
            while len(self._janelas) > self.maximo_clientes:
                self._janelas.popitem(last=False)
            return True, 0

    def limpar(self) -> None:
        with self._lock:
            self._janelas.clear()
