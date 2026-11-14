# Telemetria da demonstração e dashboard

O endpoint `POST /api/v1/iot/readings` recebe as quatro leituras do Node-RED. O contrato oficial é:

| Sensor | Campo recebido em `values` | Unidade de entrada | Indicador persistido | Unidade persistida |
|---|---|---:|---|---:|
| BMP180 | `temperaturaAr` | °C | `temperaturaAr` | °C |
| DHT22 temperatura | `umidadeSolo` | °C | `umidadeSolo` (demonstrativo) | % |
| DHT22 umidade | `umidadeAr` | % | `umidadeAr` | % |
| LDR | `luminosidade` | ADC | `luminosidade` | ADC |

Exemplo de entrada (números ilustrativos; não representam uma captura real):

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

`temperaturaAr` recebe diretamente BMP180. `umidadeSolo` recebe a temperatura bruta DHT22 em °C; o backend converte esse campo para percentual. Leituras ausentes, nulas, não finitas, unidades incorretas ou campos desconhecidos são rejeitados com HTTP 422. O Node-RED só deve enviar a captura quando as quatro leituras do mesmo agrupamento estiverem disponíveis.

A conversão isolada `converter_temperatura_dht22_em_umidade_solo` aplica `clamp((temperatura - limite inferior) / (limite superior - limite inferior) × 100, 0, 100)`. Os padrões são 15 °C → 0%, 25 °C → 50% e 35 °C → 100%. Configure `TELEMETRY_SOIL_MOISTURE_TEMP_MIN_C` e `TELEMETRY_SOIL_MOISTURE_TEMP_MAX_C` para ajustar os limites. O percentual é simulado, não medido. O backend preserva a temperatura DHT22 original em `complements.umidadeSolo.temperaturaFonteC`, com origem `DHT22_TEMPERATURA`, método `CONVERSAO_LINEAR_DEMONSTRATIVA` e `simulado=true`.

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

A análise do Isolation Forest permanece `PENDENTE_ADEQUACAO_CONTRATO_ML`, com `analysis.executed=false`; esta ingestão não executa o modelo legado de três variáveis. Capturas repetidas com o mesmo `deviceId` e `observationId` retornam HTTP 409. O dashboard usa os quatro campos persistidos em `/api/v1/dashboard/readings`; o snapshot mobile continua predefinido e independente do banco de telemetria.

### Agrupamento Node-RED

O fluxo agrupa os tópicos `estufa/bmp180/temperatura`, `estufa/dht22/temperatura`, `estufa/dht22/umidade` e `estufa/ldr/luminosidade`. BMP180 também permanece conectado ao nó de exibição já existente. O agrupador abaixo guarda no máximo uma leitura pendente por tópico, descarta o conjunto quando um sensor se repete antes de completar a captura ou quando a diferença temporal ultrapassa 2 segundos, e limpa o estado antes de emitir o POST. Assim ele não reutiliza uma leitura de um ciclo incompleto. Como os tópicos não incluem id de ciclo, a janela de chegada é uma aproximação temporal; atomicidade física exigiria um identificador comum publicado pelos sensores.

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

Os valores entre aspas acima descrevem as fontes, não são strings válidas no payload HTTP. Em runtime, todos os quatro campos são números.

## Persistência e aprendizado

A tabela `iot_readings` guarda `values`, `units` e `complements` em JSONB; não foi necessária nova migration. O dashboard exibe `umidadeSolo` com indicação de valor simulado. O modelo Isolation Forest, seu scaler e seu artefato não foram adaptados nem executados para este contrato.

## Banco isolado

Provisionamento local de exemplo (substitua credenciais fora do repositório):

```powershell
createdb agroconnect_demo
$env:TELEMETRY_DATABASE_URL = "postgresql+psycopg://telemetry_app:<senha>@localhost:5432/agroconnect_demo"
psql "$env:TELEMETRY_DATABASE_URL" -f migrations\telemetria\001_create_schema.sql
```

Use o banco PostgreSQL local próprio do módulo de IA configurado por `TELEMETRY_DATABASE_URL`. Para configuração do container, migrations e testes de persistência, consulte `documentacao/postgresql_local.md`. Configure credenciais por `.env` local, ignorado pelo Git. A API nunca cria nem migra tabelas no startup.

## Modelo

Treinamento: `python scripts/treinar_modelo.py`. Avaliação: `python scripts/avaliar_modelo.py`. A fixture `SIMULADO_TESTE` separa 120 registros de treino e 64 de avaliação; seus valores e faixas são sintéticos, com unidades declaradas para exercitar validação, sem evidência agrícola. Parâmetros padrão: 200 estimadores, contamination=0,05, semente=42, StandardScaler. Avaliação mostra precisão, revocação, F1 e matriz de confusão apenas no conjunto sintético. O score `-score_samples` não é probabilidade, risco, severidade agronômica nem diagnóstico. O formato de artefato mudou para 2 e a versão é `isolation-forest-v2`; artefatos antigos são rejeitados.

## Execução local

1. Instale dependências pelo fluxo do README e configure `.env`.
2. Provisione PostgreSQL separado e aplique a migração manual.
3. Treine o modelo v2.
4. Inicie `uvicorn app.principal:app --reload`; abra `/dashboard`. Em Docker, monte `modelos_treinados` como somente leitura em `/app/modelos_treinados` e passe `TELEMETRY_DATABASE_URL` ao container; a imagem não contém artefato nem credenciais.
5. No Node-RED, use um agregador por captura para os tópicos `estufa/dht22/temperatura`, `estufa/dht22/umidade`, `estufa/ldr/luminosidade`; envie JSON por HTTP para `/api/v1/iot/readings`. Para o firmware atual, confirme previamente que ele corresponde aos sensores DHT22/LDR: o arquivo externo `Sensores.c++` inspecionado é outro programa (ultrassônico PetCore), portanto não fornece esses tópicos.

Nenhuma migration foi aplicada a banco. O seed SQL da equipe mobile é outro arquivo e outra base; nenhuma conexão com ela foi aberta.
