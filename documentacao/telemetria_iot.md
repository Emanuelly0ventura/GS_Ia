# Telemetria Wokwi e dashboard

Para preparar a simulação, siga o [guia do ESP32 no Wokwi](../README.md#esp32-da-estufa-no-wokwi).

O endpoint `POST /api/v1/iot/readings` recebe as quatro leituras do Node-RED. O contrato de entrada e a representação persistida são:

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

Depois que a função de agrupamento reúne os quatro tópicos, o nó de requisição HTTP envia a captura para `/api/v1/iot/readings`. O quadro abaixo descreve a origem e a unidade dos campos.

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

## Importar o fluxo Node-RED

1. No editor do Node-RED, use **Menu → Importar** e selecione [fluxo_agroconnect.json](../iot/node_red/fluxo_agroconnect.json).
2. Edite a conexão compartilhada pelos quatro nós MQTT. Substitua `hivemq.example.com` pelo host do seu cluster HiveMQ Cloud, mantenha TLS e a porta `8883` e preencha as credenciais no Node-RED.
3. No nó HTTP, ajuste o endereço para a API acessível pelo Node-RED. A configuração local usa `POST http://127.0.0.1:8000/api/v1/iot/readings`.
4. Clique em **Deploy** e inicie o ESP32 no Wokwi. A função reúne os sensores e envia a captura ao FastAPI. Use a aba de depuração para conferir a resposta HTTP e compare o identificador ou o horário com o dashboard.

O export usa os nós padrão do Node-RED e inclui a ingestão e a depuração. O dashboard do AgroConnect é servido pelo FastAPI.

## Execução e conferência

1. Aplique as migrations 001 a 008 seguindo o [guia PostgreSQL](postgresql_local.md) e gere o artefato conforme o [guia do Isolation Forest](aprendizado_maquina.md).
2. Inicie a API e abra `/dashboard`.
3. [Importe e configure o fluxo](#importar-o-fluxo-node-red) e inicie o ESP32 no Wokwi.
4. No dashboard, confira o horário e o dispositivo em **Última captura** e a classificação em **Inteligência artificial · anomalias**.
5. Em **Análise agrícola personalizada**, escolha uma cultura e um solo para consultar a regra e o contexto da captura selecionada pela API.

A coluna física dos valores é `iot_readings.sensor_values`, acompanhada por `units` e `complements`. A [validação local](validacao.md) inclui consultas para conferir capturas, classificações e explicações persistidas.

## Acompanhar uma captura no código

1. No [firmware](../iot/wokwi/sketch.ino), `setup()` inicia sensores, I²C, OLED, Wi-Fi e MQTT. `loop()` tenta restabelecer a conexão quando necessário e chama `lerSensoresEEnviar()` a cada cinco segundos. Uma leitura inválida do DHT22 sinaliza erro e interrompe aquele envio.
2. No [fluxo do Node-RED](../iot/node_red/fluxo_agroconnect.json), quatro nós MQTT recebem os valores publicados. A função de agrupamento exige um valor de cada tópico dentro da janela de dois segundos para montar uma observação completa. O nó HTTP envia identificadores, horário, origem, qualidade, valores e unidades.
3. Na [rota de ingestão](../app/telemetria/rotas.py), `receber()` usa o contrato `LeituraIoT` para validar a entrada. `adaptar_para_indicadores()` entrega valores, unidades e complementos canônicos, chamando a [conversão de temperatura em índice de solo](../app/telemetria/conversoes.py). A rota grava a captura antes de chamar o detector.
4. A mesma rota grava a classificação e depois chama `tentar_explicar_anomalia()`. O leitor do dashboard consulta `GET /api/v1/dashboard/readings` para recuperar a captura e o resultado associado. Uma observação repetida para o mesmo dispositivo recebe HTTP 409. Consulte o [fluxo de explicação](integracao_gemini.md) para os estados da geração.
