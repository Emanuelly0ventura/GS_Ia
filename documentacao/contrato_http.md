# Contrato HTTP do AgroConnect AI

O AgroConnect AI oferece sua própria API FastAPI e mantém seus registros em um PostgreSQL dedicado. O [Swagger local](http://127.0.0.1:8000/docs) mostra os esquemas de entrada e saída e permite testar as rotas pelo navegador enquanto a API estiver rodando na porta 8000.

| Caso de uso | Entrada |
| --- | --- |
| Enviar uma captura IoT | `POST /api/v1/iot/readings` |
| Consultar capturas e classificações | `GET /api/v1/dashboard/readings` |
| Solicitar uma análise agrícola | `POST /api/v1/agricultura/analise-unificada` |
| Consultar o histórico agrícola | `GET /api/v1/agricultura/analises` |

A entrada e a apresentação dos dados estão descritas nos guias de [telemetria](telemetria_iot.md) e [análise agrícola](analise_agricola.md).

## Rotas de consulta e demonstração

| Rota | Origem dos dados e finalidade |
| --- | --- |
| `GET /health` | Retorna o estado do processo FastAPI. O painel usa essa informação para verificar se o serviço responde. |
| `GET /health/ready` | Executa a verificação da conexão PostgreSQL. O estado de prontidão informa se o banco pode atender às rotas que dependem dele. |
| `GET /api/v1/dashboard/status` | Consulta o estado da telemetria para indicar se o dispositivo tem comunicação recente. |
| `GET /api/v1/agricultura/sementes` e `GET /api/v1/agricultura/solos` | Retornam os IDs do catálogo ativo para preencher os seletores da análise. |
| `POST /api/v1/recomendacoes` | Recebe dispositivo, observação e cultura. Consulta a captura e o catálogo local para devolver orientações ou o estado da recuperação e geração. |
| `POST /api/v1/anomalias/analisar-demo` | Recebe uma leitura simulada no corpo HTTP e devolve o resultado de `predizer()` diretamente ao solicitante. |
| `GET /api/v1/mobile/demo/snapshot` | Devolve um conjunto predefinido no código para as telas de demonstração mobile. |

[Saúde](../app/rotas/saude.py) · [Status da telemetria](../app/telemetria/rotas.py) · [Catálogo agrícola](../app/compatibilidade/rotas.py) · [Recomendações](../app/rotas/recomendacoes.py) · [Inferência de demonstração](../app/rotas/anomalias.py) · [Snapshot mobile](../app/rotas/mobile_demo.py)
