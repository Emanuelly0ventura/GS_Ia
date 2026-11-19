# Evidências de execução

Verificação realizada em **17/11/2026** com a API local, o PostgreSQL do AgroConnect e o fluxo Node-RED da estufa Wokwi. Horários desta página usam o fuso de São Paulo. As contagens registram o estado do ambiente nessa data. Ao repetir as consultas, os totais dependem dos dados do banco consultado.

## Telemetria persistida e consumo pela API

| Verificação | Resultado |
|---|---:|
| Capturas com origem `WOKWI_HIVEMQ_NODE_RED` | 53 |
| Capturas com classificação do Isolation Forest | 53 |
| Capturas classificadas como atípicas | 36 |
| Explicações Gemini persistidas nessas capturas | 9 |
| Regras agrícolas ativas | 25 |
| Análises agrícolas no histórico local | 8 |
| Análises agrícolas com explicação Gemini persistida | 2 |

A captura `esp32-estufa-01-1794955840958-32`, medida às **19:50:40,958**, foi classificada como **anomalia estatística** pelo `isolation-forest-v3`, com score **0,583599** e explicação Gemini registrada como `CONCLUIDA`. O identificador vincula a captura em `iot_readings` à análise em `iot_anomaly_analyses`.

A inspeção do Node-RED confirmou os quatro tópicos de sensor ligados à função de agrupamento e o nó HTTP configurado para `POST /api/v1/iot/readings`. Na API local, `GET /health/ready`, `GET /api/v1/dashboard/readings?limit=5` e `GET /api/v1/agricultura/analises?limit=10` responderam HTTP 200. A última consulta retornou as oito análises persistidas.

### Reproduzir a consulta

Abra o `psql` do banco da aplicação e execute:

```sql
SELECT count(*) AS capturas,
       count(a.id) AS classificadas,
       count(*) FILTER (WHERE a.is_anomaly) AS atipicas,
       count(*) FILTER (
           WHERE a.generative_status = 'CONCLUIDA'
             AND a.generative_explanation IS NOT NULL
       ) AS explicadas
FROM iot_readings AS r
LEFT JOIN iot_anomaly_analyses AS a ON a.reading_id = r.id
WHERE r.source = 'WOKWI_HIVEMQ_NODE_RED';

SELECT count(*) AS analises,
       count(*) FILTER (
           WHERE estado_explicacao = 'CONCLUIDA'
             AND explicacao_gemini IS NOT NULL
       ) AS explicadas
FROM analises_compatibilidade;
```

## Avaliação do Isolation Forest

O script `python scripts/avaliar_modelo.py` ajustou o detector com 120 exemplos e avaliou 64 exemplos rotulados do conjunto **sintético** `iforest-sintetico-4-variaveis-v3`. Foram obtidas precisão **1,00**, revocação **1,00** e F1 **1,00**. A matriz de confusão, com linhas para o rótulo esperado e colunas para a previsão, foi `[[40, 0], [0, 24]]`, na ordem normal e anomalia. Essas métricas medem o desempenho nesse conjunto. A tabela de telemetria acima documenta o processamento das capturas do simulador.

## Suíte automatizada

`python -m pytest -q` com `TEST_TELEMETRY_DATABASE_URL` apontando para um PostgreSQL dedicado com migrations 001 a 008 apresentou **299 aprovados**. A suíte cobre ingestão, persistência, compatibilidade, seleção da captura, reaproveitamento da classificação, cobertura das 25 combinações no RAG e histórico com diferentes estados do Gemini. Os testes automatizados do provedor usam dublês. As explicações concluídas na tabela acima são registros da execução local com a API Gemini.

## Como interpretar as evidências

- **Ingestão e classificação.** A junção por `reading_id` acompanha a captura persistida até a análise atribuída a ela. Os contadores usam o conjunto de capturas da origem Wokwi e distinguem capturas processadas pelo detector de explicações efetivamente concluídas. [Rota de ingestão](../app/telemetria/rotas.py)
- **Histórico agrícola.** A consulta conta os registros gravados e exige estado concluído e texto presente para contar uma explicação. Esses mesmos registros alimentam a consulta de histórico do painel. [Rota de histórico](../app/compatibilidade/rotas.py)
- **Avaliação do modelo.** O script compara as classes previstas com os rótulos da fixture. A matriz dá os acertos e os erros em cada classe. A precisão mede a proporção de alertas que eram anomalias rotuladas e a revocação mede a proporção das anomalias rotuladas que foram detectadas. O F1 combina as duas métricas. [Script de avaliação](../scripts/avaliar_modelo.py)
- **Suíte.** Os testes de integração usam PostgreSQL dedicado para verificar o contrato entre a API e o banco. Os dublês do provedor exercitam a validação e os estados de geração. Os registros datados acima documentam a execução local com o serviço Gemini. [Testes](../tests)
