import math


def converter_temperatura_dht22_em_umidade_solo(
    temperatura_c: float,
    *,
    limite_inferior_c: float = 15.0,
    limite_superior_c: float = 35.0,
) -> float:
    """Converte temperatura DHT22 em percentual demonstrativo, limitado a 0–100%."""
    for nome, valor in (("temperatura_c", temperatura_c), ("limite_inferior_c", limite_inferior_c), ("limite_superior_c", limite_superior_c)):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
            raise ValueError(f"{nome} deve ser um número finito.")
    inferior = float(limite_inferior_c)
    superior = float(limite_superior_c)
    if inferior >= superior:
        raise ValueError("O limite inferior deve ser menor que o limite superior.")
    valor = float(temperatura_c)
    if valor <= inferior:
        return 0.0
    if valor >= superior:
        return 100.0
    return ((valor - inferior) / (superior - inferior)) * 100.0
