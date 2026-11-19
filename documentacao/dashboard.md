# Dashboard operacional

Abra [`/dashboard`](http://127.0.0.1:8000/dashboard) após iniciar a API, conforme o [README](../README.md). O FastAPI serve a página HTML, CSS e JavaScript e fornece as rotas usadas para preencher o painel.

## Áreas do painel

| Área | O que exibe |
| --- | --- |
| Indicadores atuais | Temperatura do ar, índice demonstrativo de umidade do solo, umidade do ar e luminosidade. As cores dos cartões correspondem às séries do gráfico. |
| Monitoramento IoT | Gráfico das últimas capturas e cartão com horário, dispositivo, qualidade e valores da última leitura completa. Cada série conserva sua unidade e é normalizada para exibição. |
| Anomalias | Classificação, score de atipicidade, justificativa do Isolation Forest e estado da explicação Gemini. |
| Análise agrícola | Formulário de cultura e solo, critérios da combinação, condições ambientais, explicação e referências. O estado **Desconhecido** traz a justificativa logo abaixo. |
| Histórico | Capturas de telemetria e as dez análises agrícolas mais recentes, com resultado e estado da explicação. |

## Atualização

O painel carrega os catálogos ao abrir e atualiza a saúde da API, as capturas e o histórico a cada 15 segundos. O formulário chama `POST /api/v1/agricultura/analise-unificada` ao selecionar **Analisar combinação**. Quando a resposta chega, a tabela consulta novamente o histórico.

O gráfico busca até 50 registros por `GET /api/v1/dashboard/readings`. O histórico agrícola usa `GET /api/v1/agricultura/analises`. O [contrato HTTP](contrato_http.md) reúne as rotas principais.

## Endereço da API

Por padrão, o painel usa a mesma origem do FastAPI. Para configurar outra origem, defina `DASHBOARD_API_BASE_URL` como a origem HTTP(S) da API e configure o servidor para aceitar as requisições dessa origem.

## Origem dos dados de cada área

| Função do navegador | Entrada e destino |
| --- | --- |
| `refresh()` | Consulta `/health` e `/health/ready` para mostrar disponibilidade do serviço e do banco. Também lê `/api/v1/dashboard/status` para o estado do dispositivo. |
| `renderCapture()`, `renderIoT()` e `drawChart()` | Consomem os registros de `/api/v1/dashboard/readings` para preencher a última captura, o histórico IoT e as séries. O gráfico normaliza as escalas para exibir indicadores com unidades diferentes na mesma área. |
| `analysisMarkup()` | Renderiza o objeto de análise associado à leitura para mostrar classe, score, justificativa e estado ou texto do Gemini. |
| `loadCatalog()` e `analysisResult()` | Os catálogos fornecem os IDs selecionados. O envio do formulário usa os IDs para obter o resultado unificado e renderizar regra, captura, anomalia, mensagem e referências. |
| `renderCompatHistory()` | Recebe até dez análises de `/api/v1/agricultura/analises` para mostrar o que foi registrado em cada consulta anterior. |

A função `api()` centraliza as chamadas HTTP do navegador e trata respostas com erro antes de tentar renderizar os dados. [JavaScript do painel](../dashboard/index.html) · [Rotas de leitura](../app/telemetria/rotas.py)
