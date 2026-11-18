# Telemetria Wokwi e dashboard

O endpoint `POST /api/v1/iot/readings` recebe as quatro leituras do Node-RED. O contrato oficial é:

| Sensor | Campo recebido em `values` | Unidade de entrada | Indicador persistido | Unidade persistida |
|---|---|---:|---|---:|
| BMP180 | `temperaturaAr` | °C | `temperaturaAr` | °C |
| DHT22 temperatura | `umidadeSolo` | °C | `umidadeSolo` (demonstrativo) | % |
| DHT22 umidade | `umidadeAr` | % | `umidadeAr` | % |
| LDR | `luminosidade` | ADC | `luminosidade` | ADC |

Exemplo do contrato de entrada:

```json
{
  "deviceId": "esp32-estufa-01",
  "observationId": "captura-2026-11-11T10:20:00-03:00-42",
  "source": "WOKWI_HIVEMQ_NODE_RED",
  "measuredAt": "2026-11-11T10:20:00-03:00",
  "quality": "VALID",
  "values": {
    "temperaturaAr": 25.1,
    "umidadeSolo": 25.0,
    "umidadeAr": 62.0,
    "luminosidade": 1870.0
  },
  "units": {
    "temperaturaAr": "°C",
    "umidadeSolo": "°C",
    "umidadeAr": "%",
    "luminosidade": "ADC"
  }
}
```

`temperaturaAr` recebe diretamente BMP180. `umidadeSolo` recebe a temperatura bruta DHT22 em °C; o backend converte esse campo para percentual. O Node-RED envia a captura quando os quatro indicadores do mesmo agrupamento estão disponíveis. O contrato exige valores numéricos finitos e suas unidades correspondentes.

A conversão isolada `converter_temperatura_dht22_em_umidade_solo` aplica `clamp((temperatura - limite inferior) / (limite superior - limite inferior) × 100, 0, 100)`. Os padrões são 15 °C → 0%, 25 °C → 50% e 35 °C → 100%. Configure `TELEMETRY_SOIL_MOISTURE_TEMP_MIN_C` e `TELEMETRY_SOIL_MOISTURE_TEMP_MAX_C` para ajustar os limites. O percentual representa um índice demonstrativo. O backend preserva a temperatura DHT22 original em `complements.umidadeSolo.temperaturaFonteC`, com origem `DHT22_TEMPERATURA`, método `CONVERSAO_LINEAR_DEMONSTRATIVA` e `simulado=true`.

Registro persistido (para o exemplo acima):

```json
{
  "values": {
    "temperaturaAr": 25.1,
    "umidadeSolo": 50.0,
    "umidadeAr": 62.0,
    "luminosidade": 1870.0
  },
  "units": {
    "temperaturaAr": "°C",
    "umidadeSolo": "%",
    "umidadeAr": "%",
    "luminosidade": "ADC"
  },
  "complements": {
    "umidadeSolo": {
      "origem": "DHT22_TEMPERATURA",
      "metodo": "CONVERSAO_LINEAR_DEMONSTRATIVA",
      "simulado": true,
      "temperaturaFonteC": 25.0
    }
  }
}
```

Após persistir a captura, a API relê os quatro indicadores no PostgreSQL, executa o Isolation Forest v3 e grava classificação, score e justificativa em `iot_anomaly_analyses`. Em seguida, o Gemini recebe esse contexto para elaborar a explicação, registrada em campos próprios de texto, estado e código. A chave dispositivo + observação identifica cada captura. Consulte as classificações em `GET /api/v1/dashboard/readings`.

### Agrupamento Node-RED

O fluxo agrupa os tópicos `estufa/bmp180/temperatura`, `estufa/dht22/temperatura`, `estufa/dht22/umidade` e `estufa/ldr/luminosidade`. BMP180 também permanece conectado ao nó de exibição já existente. O agrupador guarda no máximo uma leitura pendente por tópico, descarta o conjunto quando um sensor se repete antes de completar a captura ou quando a diferença temporal ultrapassa 2 segundos, e limpa o estado antes de emitir o POST. Cada captura reúne mensagens distintas recebidas dentro dessa janela.

A Function de ingestão espera os quatro tópicos. Após completar a captura, envia este contrato para `/api/v1/iot/readings`:

```json
{
  "values": {
    "temperaturaAr": "BMP180 em °C",
    "umidadeSolo": "temperatura bruta do DHT22 em °C",
    "umidadeAr": "DHT22 em %",
    "luminosidade": "LDR em ADC"
  },
  "units": {
    "temperaturaAr": "°C",
    "umidadeSolo": "°C",
    "umidadeAr": "%",
    "luminosidade": "ADC"
  }
}
```

O quadro identifica a origem de cada campo. No payload HTTP, `values` contém os quatro valores numéricos, como no exemplo de entrada.

## Execução e conferência

1. Aplique as migrations 001 a 008 seguindo o [guia PostgreSQL](postgresql_local.md) e gere o artefato conforme o [guia do Isolation Forest](aprendizado_maquina.md).
2. Inicie a API e abra `/dashboard`.
3. Use o ESP32 no Wokwi conectado ao HiveMQ. No Node-RED, conecte os quatro nós MQTT de sensor à função de agrupamento e ligue sua saída ao nó HTTP. Configure o POST com a URL da API alcançável pelo processo do Node-RED.
4. No dashboard, confira o horário e o dispositivo em **Última captura** e a classificação em **Inteligência artificial · anomalias**.
5. Em **Análise agrícola personalizada**, escolha uma cultura e um solo para consultar a regra e o contexto da captura selecionada pela API.

A coluna física dos valores é `iot_readings.sensor_values`, acompanhada por `units` e `complements`. A [validação local](validacao.md) inclui consultas para conferir capturas, classificações e explicações persistidas.
