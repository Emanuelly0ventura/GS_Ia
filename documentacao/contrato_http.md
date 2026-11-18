# Contrato HTTP do AgroConnect AI

O AgroConnect AI oferece sua própria API FastAPI e mantém seus registros em um PostgreSQL dedicado. O Swagger em [`/docs`](http://127.0.0.1:8000/docs) descreve o contrato para consumidores HTTP.

| Caso de uso | Entrada |
| --- | --- |
| Enviar uma captura IoT | `POST /api/v1/iot/readings` |
| Consultar capturas e classificações | `GET /api/v1/dashboard/readings` |
| Solicitar uma análise agrícola | `POST /api/v1/agricultura/analise-unificada` |
| Consultar o histórico agrícola | `GET /api/v1/agricultura/analises` |

A entrada e a apresentação dos dados estão descritas nos guias de [telemetria](telemetria_iot.md) e [análise agrícola](analise_agricola.md).
