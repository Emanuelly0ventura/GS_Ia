# Única definição de ordem e unidades usada por treino, preparação e inferência.
CARACTERISTICAS_MODELO = (
    ("temperaturaAr", "°C"),
    ("umidadeSolo", "%"),
    ("umidadeAr", "%"),
    ("luminosidade", "ADC"),
)
VARIAVEIS_MODELO = tuple(nome for nome, _ in CARACTERISTICAS_MODELO)
UNIDADES_MODELO = dict(CARACTERISTICAS_MODELO)
VERSAO_FEATURES = "iot-4-indicadores-v1"
VERSAO_PREPROCESSAMENTO = "standard-scaler-ordem-canonica-v1"
