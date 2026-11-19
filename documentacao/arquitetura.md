# Arquitetura

O AgroConnect AI concentra a ingestão, o processamento e o dashboard em um serviço Python/FastAPI. O PostgreSQL do módulo é provisionado pelo Docker Compose com schema versionado pelas migrations SQL. O navegador consulta as rotas HTTP do FastAPI.

## Telemetria

1. O ESP32 no Wokwi publica as leituras do BMP180, DHT22 e LDR no HiveMQ via MQTT.
2. O [fluxo Node-RED](../iot/node_red/fluxo_agroconnect.json) agrupa os quatro indicadores e envia a captura para `POST /api/v1/iot/readings`.
3. A API valida valores e unidades, calcula o índice demonstrativo de solo a partir da temperatura DHT22 e persiste a captura em `iot_readings`.
4. A API chama o Isolation Forest v3 com os quatro indicadores persistidos e grava a classificação retornada em `iot_anomaly_analyses`. O Gemini recebe o resultado calculado e acrescenta sua explicação ao registro.

## Análise agrícola

1. O dashboard lista culturas e solos ativos e envia seus IDs a `POST /api/v1/agricultura/analise-unificada`.
2. O serviço consulta a regra em `compatibilidades`, seleciona a captura Wokwi válida mais recente e recupera a análise de anomalias associada.
3. O recuperador local seleciona referências técnicas aplicáveis à cultura e ao solo.
4. A API grava a decisão e os critérios em `analises_compatibilidade`. O Gemini explica o contexto, e o serviço valida e grava a explicação no mesmo registro.
5. O dashboard exibe as etapas do resultado e atualiza a lista a partir de `GET /api/v1/agricultura/analises`.

## Responsabilidades no código

| Caminho | Responsabilidade |
| --- | --- |
| `app/nucleo` | Configuração e logging |
| `app/telemetria` | Ingestão, conversão, consulta de capturas e fábrica de sessões SQLAlchemy |
| `app/compatibilidade` | Catálogos, regras e orquestração da análise agrícola |
| `app/inteligencia_artificial/aprendizado_maquina` | Preparação, treinamento e inferência do Isolation Forest |
| `app/inteligencia_artificial/recomendacoes/documentos.py` | Recuperação e ranking das referências da análise agrícola |
| `app/inteligencia_artificial/generativa` | Cliente Gemini e validação das explicações |
| `dashboard/index.html` | Interface, gráfico, formulários e histórico |

A ingestão, o dashboard e o módulo agrícola usam o PostgreSQL dedicado da IA. A seleção de referências lê `base_conhecimento/documentos_agricolas.json`. Os contratos genéricos de leitura ficam em `app/repositorios`, com cobertura unitária.

Consulte [os contratos de telemetria](telemetria_iot.md), [o fluxo agrícola](analise_agricola.md) e [as evidências de execução](validacao.md).

## Do dado de entrada até o consumidor

| Componente | Entrada e motivo da etapa | Transformação e destino |
| --- | --- | --- |
| ESP32 e HiveMQ | O firmware lê os sensores simulados. Publicar por MQTT permite que o Node-RED receba os valores sem que o ESP32 precise conhecer o endereço da API. | `lerSensoresEEnviar()` publica um valor por tópico. O HiveMQ entrega as mensagens aos assinantes. [Sketch](../iot/wokwi/sketch.ino) |
| Node-RED | Recebe mensagens individuais. O agrupamento evita enviar ao backend uma captura incompleta. | A função reúne quatro tópicos dentro da janela de dois segundos e passa o JSON para o nó HTTP. [Fluxo exportado](../iot/node_red/fluxo_agroconnect.json) |
| FastAPI e SQLAlchemy | Recebem o JSON do Node-RED ou as requisições do navegador. As rotas definem o contrato HTTP e a sessão SQLAlchemy faz as operações no PostgreSQL. | `receber()` grava a captura e o resultado do modelo. As rotas de consulta devolvem JSON para o dashboard. [Inicialização](../app/principal.py) · [Rotas de telemetria](../app/telemetria/rotas.py) |
| Isolation Forest e Gemini | O primeiro recebe quatro indicadores na ordem do treino. O segundo recebe o resultado calculado e o contexto para explicá-lo. | `predizer()` retorna classificação e score à rota. A geração retorna um texto validado, com estado próprio. [Modelo](aprendizado_maquina.md) · [Geração](integracao_gemini.md) |
| Regra agrícola e recuperação de referências | O serviço recebe os IDs do formulário. A regra fornece a conclusão cadastrada e o recuperador traz trechos para fundamentar a explicação. | `preparar_contexto()` agrega regra, captura e documentos. O histórico guarda a decisão e a mensagem principal gerada. [Implementação](../app/compatibilidade/analise_unificada.py) |
| Dashboard | O navegador recebe JSON da API para exibir a captura, a classificação e o histórico. | O JavaScript atualiza cartões, gráfico e tabela. Ao enviar o formulário, chama a análise unificada e atualiza o histórico. [Interface](../dashboard/index.html) |

Se o banco falhar na ingestão, a rota interrompe o fluxo antes da classificação. Se a inferência falhar após a gravação da captura, a leitura pode continuar disponível com o estado de análise em falha. Se a geração falhar depois da classificação ou da consulta à regra, o resultado persistido continua disponível com seu estado de explicação.
