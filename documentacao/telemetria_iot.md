# Telemetria da demonstração e dashboard

O mobile permanece em `/api/v1/mobile/demo/snapshot`, com conteúdo predefinido explicitamente rotulado `PREDEFINED_DEMO`. Esse endpoint não consulta MQTT nem o banco de telemetria. O contrato real do aplicativo não está no repositório; confirme os nomes esperados com Mobile/Backend antes de substituir ou adaptar o contrato de demonstração.

O firmware colado publica temperatura, umidade e ADC em tópicos individuais, sem id de ciclo nos payloads. No Node-RED, normalize cada tópico para `{variavel, valor, recebidoEm}`, envie os três ramos a um `Join` configurado por chave de variável (`manual`, 3 mensagens) com timeout menor que o intervalo de publicação de 5 s, e descarte grupos incompletos ou cujo maior/menor horário de recebimento difira acima da tolerância definida (por exemplo, 2 s). Como o protocolo atual não traz timestamp/correlation id em cada payload, essa é uma aproximação temporal: para garantia de amostra atômica, o firmware deve publicar um JSON único com `observationId`/timestamp, mediante autorização e atualização separada. A API exige que o agrupador entregue o trio completo, gera `observationId` único e timestamp ISO-8601 com fuso; não presume ordem dos tópicos.

```json
{
  "deviceId":"esp32-estufa-01", "observationId":"captura-2026-11-11T10:20:00-03:00",
  "source":"WOKWI_HIVEMQ_NODE_RED", "measuredAt":"2026-11-11T10:20:00-03:00",
  "quality":"VALID",
  "values":{"temperaturaAr":25.4,"umidadeAr":62.0,"luminosidade":1870},
  "units":{"temperaturaAr":"°C","umidadeAr":"%","luminosidade":"ADC"},
  "complements":{"temperaturaBmp":25.1,"pressao":1012.2,"altitude":24.0}
}
```

`POST /api/v1/iot/readings` valida e persiste conjunto e análise. Responde 409 para `observationId` duplicado, 422 para campos incompletos/inválidos/unidades incompatíveis e 503 se banco ou artefato v2 não estiver pronto. As rotas `GET /api/v1/dashboard/readings?limit=100`, `GET /api/v1/dashboard/status` alimentam `/dashboard`. Status conectado é derivado de `last_seen_at` e `TELEMETRY_DEVICE_TIMEOUT_SECONDS`. O LDR é mostrado como ADC bruto, não lux. BMP é complemento e não participa do modelo.

### Node-RED: agrupamento das mensagens MQTT

Conecte as três entradas MQTT ao mesmo normalizador abaixo. Configure um `Join` em modo manual para gerar objeto por `msg.topic`, completar depois de 3 mensagens, com timeout de 2 segundos. Depois, ligue um Function de validação/serialização e um HTTP Request `POST`, com `Content-Type: application/json`, para `/api/v1/iot/readings`.

Function normalizador (antes do Join):

```javascript
const nomes = {
  "estufa/dht22/temperatura": "temperaturaAr",
  "estufa/dht22/umidade": "umidadeAr",
  "estufa/ldr/luminosidade": "luminosidade"
};
const chave = nomes[msg.topic];
const valor = Number(msg.payload);
if (!chave || !Number.isFinite(valor)) return null;
msg.topic = chave;
msg.payload = { value: valor, receivedAt: Date.now() };
return msg;
```

Function depois do Join (descarta grupos incompletos e com diferença temporal acima de 2 s):

```javascript
const grupo = msg.payload;
const nomes = ["temperaturaAr", "umidadeAr", "luminosidade"];
if (!grupo || nomes.some(n => !grupo[n] || !Number.isFinite(grupo[n].value))) return null;
const tempos = nomes.map(n => grupo[n].receivedAt);
if (Math.max(...tempos) - Math.min(...tempos) > 2000) return null;
const capturado = Math.max(...tempos);
const seq = (flow.get("telemetrySeq") || 0) + 1;
flow.set("telemetrySeq", seq);
msg.headers = { "Content-Type": "application/json" };
msg.payload = {
  deviceId: "esp32-estufa-01",
  observationId: `esp32-estufa-01-${capturado}-${seq}`,
  source: "WOKWI_HIVEMQ_NODE_RED",
  measuredAt: new Date(capturado).toISOString(),
  quality: "VALID",
  values: Object.fromEntries(nomes.map(n => [n, grupo[n].value])),
  units: { temperaturaAr: "°C", umidadeAr: "%", luminosidade: "ADC" },
  complements: {}
};
return msg;
```

O protocolo MQTT individual não contém id/timestamp de ciclo. A validação temporal acima é uma aproximação pela hora de chegada e não comprova que valores pertencem à mesma amostra física. Um JSON único por ciclo enviado pelo firmware seria necessário para atomicidade; o firmware não foi alterado.

## Banco isolado

Provisionamento local de exemplo (substitua credenciais fora do repositório):

```powershell
createdb agroconnect_demo
$env:TELEMETRY_DATABASE_URL = "postgresql+psycopg://telemetry_app:<senha>@localhost:5432/agroconnect_demo"
psql "$env:TELEMETRY_DATABASE_URL" -f migrations\telemetria\001_create_schema.sql
```

Use um banco exclusivamente da demonstração, separado de `DATABASE_URL` (que continua read-only). Execute o DDL com uma conta de provisionamento; para runtime, use uma conta própria com `CONNECT`, `SELECT`, `INSERT` e `UPDATE` somente nas tabelas `iot_devices`, `iot_readings` e `iot_anomaly_analyses`, mais `USAGE/SELECT` nas respectivas sequences. Configure credenciais por ambiente/secret manager; não inclua credenciais no Git. A API nunca cria nem migra tabelas no startup.

## Modelo

Treinamento: `python scripts/treinar_modelo.py`. Avaliação: `python scripts/avaliar_modelo.py`. A fixture `SIMULADO_TESTE` separa 120 registros de treino e 64 de avaliação; seus valores e faixas são sintéticos, com unidades declaradas para exercitar validação, sem evidência agrícola. Parâmetros padrão: 200 estimadores, contamination=0,05, semente=42, StandardScaler. Avaliação mostra precisão, revocação, F1 e matriz de confusão apenas no conjunto sintético. O score `-score_samples` não é probabilidade, risco, severidade agronômica nem diagnóstico. O formato de artefato mudou para 2 e a versão é `isolation-forest-v2`; artefatos antigos são rejeitados.

## Execução local

1. Instale dependências pelo fluxo do README e configure `.env`.
2. Provisione PostgreSQL separado e aplique a migração manual.
3. Treine o modelo v2.
4. Inicie `uvicorn app.principal:app --reload`; abra `/dashboard`. Em Docker, monte `modelos_treinados` como somente leitura em `/app/modelos_treinados` e passe `TELEMETRY_DATABASE_URL` ao container; a imagem não contém artefato nem credenciais.
5. No Node-RED, use um agregador por captura para os tópicos `estufa/dht22/temperatura`, `estufa/dht22/umidade`, `estufa/ldr/luminosidade`; envie JSON por HTTP para `/api/v1/iot/readings`. Para o firmware atual, confirme previamente que ele corresponde aos sensores DHT22/LDR: o arquivo externo `Sensores.c++` inspecionado é outro programa (ultrassônico PetCore), portanto não fornece esses tópicos.

Nenhuma migration foi aplicada a banco. O seed SQL da equipe mobile é outro arquivo e outra base; nenhuma conexão com ela foi aberta.
