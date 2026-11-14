from dataclasses import dataclass

import numpy as np

from app.inteligencia_artificial.aprendizado_maquina.caracteristicas import UNIDADES_MODELO, VARIAVEIS_MODELO
from app.inteligencia_artificial.aprendizado_maquina.esquemas import LeituraParaModelo

@dataclass(frozen=True)
class ConjuntoPreparado:
    matriz: np.ndarray
    leituras: tuple[LeituraParaModelo, ...]
    unidades: dict[str, str]
    descartadas: tuple[dict[str, str], ...]

def preparar_leituras(
    leituras: list[LeituraParaModelo],
    unidades_esperadas: dict[str, str] | None = None,
) -> ConjuntoPreparado:
    linhas: list[list[float]] = []
    validas: list[LeituraParaModelo] = []
    descartadas: list[dict[str, str]] = []
    unidades_referencia = dict(unidades_esperadas or {})

    for leitura in leituras:
        if leitura.qualidade != "VALIDA":
            descartadas.append({"id_observacao": leitura.id_observacao, "motivo": "qualidade_nao_validada"})
            continue
        faltantes = [nome for nome in VARIAVEIS_MODELO if nome not in leitura.valores or leitura.valores[nome] is None]
        unidades_faltantes = [nome for nome in VARIAVEIS_MODELO if not leitura.unidades.get(nome)]
        if faltantes or unidades_faltantes:
            motivos = []
            if faltantes:
                motivos.append("valores_ausentes:" + ",".join(faltantes))
            if unidades_faltantes:
                motivos.append("unidades_ausentes:" + ",".join(unidades_faltantes))
            descartadas.append({"id_observacao": leitura.id_observacao, "motivo": ";".join(motivos)})
            continue

        incompatíveis = [nome for nome in VARIAVEIS_MODELO if leitura.unidades[nome] != UNIDADES_MODELO[nome]]
        if incompatíveis:
            raise ValueError(
                "Unidades incompatíveis com as features do modelo: " + ", ".join(incompatíveis)
                + ". Não são realizadas conversões automáticas."
            )
        if not unidades_referencia:
            unidades_referencia = dict(UNIDADES_MODELO)
        divergentes = [nome for nome in VARIAVEIS_MODELO if leitura.unidades[nome] != unidades_referencia.get(nome)]
        if divergentes:
            raise ValueError(
                "Unidades incompatíveis para as variáveis: " + ", ".join(divergentes)
                + ". Não são realizadas conversões automáticas."
            )

        linha = [float(leitura.valores[nome]) for nome in VARIAVEIS_MODELO]
        if not np.isfinite(linha).all():
            descartadas.append({"id_observacao": leitura.id_observacao, "motivo": "valor_nao_finito"})
            continue
        linhas.append(linha)
        validas.append(leitura)

    matriz = np.asarray(linhas, dtype=np.float64)
    if not linhas:
        matriz = np.empty((0, len(VARIAVEIS_MODELO)), dtype=np.float64)
    return ConjuntoPreparado(
        matriz=matriz,
        leituras=tuple(validas),
        unidades=unidades_referencia,
        descartadas=tuple(descartadas),
    )
