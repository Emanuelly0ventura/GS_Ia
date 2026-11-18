# Análise agrícola personalizada

Abra o [dashboard](http://127.0.0.1:8000/dashboard), selecione uma cultura e um tipo de solo e clique em **Analisar combinação**. O formulário envia os IDs `sementeId` e `soloId` para `POST /api/v1/agricultura/analise-unificada`.

## Etapas da análise

1. **Compatibilidade.** A API consulta a regra ativa pelo par cultura–solo. A matriz inicial contém 25 combinações com critérios demonstrativos, justificativas e fontes da Embrapa ou do Incaper. O resultado **Desconhecido** corresponde ao código `DADOS_INSUFICIENTES`, usado quando a conclusão depende de condições ainda por confirmar. O cartão informa quais condições precisam ser confirmadas.
2. **Captura Wokwi.** O serviço consulta as capturas da mais recente para a mais antiga, pela data da medição e pelo ID. Usa a primeira que tenha origem Wokwi no registro e no dispositivo, identificadores preenchidos, qualidade `VALID` e quatro indicadores com valores e unidades canônicos. Também confere os metadados e a conversão do índice demonstrativo do solo. A janela é definida por `TELEMETRY_DEVICE_TIMEOUT_SECONDS`: 600 segundos na configuração local da validação e 60 segundos no arquivo de exemplo.
3. **Isolation Forest.** A análise consulta a classificação e o score já associados à captura em `iot_anomaly_analyses`. A etapa de ingestão calcula e registra esse resultado.
4. **Referências técnicas.** Para a geração aumentada por recuperação (RAG), a API consulta `base_conhecimento/documentos_agricolas.json`. Filtra por cultura, solo e assunto, prioriza as correspondências mais específicas e seleciona até quatro trechos. Cada documento tem título, instituição, endereço, trecho e estado de curadoria. A base cobre as 25 combinações e recupera referências gerais da cultura mesmo quando não há uma captura recente.
5. **Explicação Gemini.** A API envia os critérios, o contexto da captura, a classificação associada e os trechos recuperados. A resposta segue um JSON com explicação, orientações, ressalvas e identificadores de referência. O serviço valida o formato e verifica os identificadores citados antes de exibir o texto.

## Resultado e histórico

O dashboard separa a decisão de compatibilidade, os indicadores ambientais, a classificação do Isolation Forest e a explicação do Gemini. A API grava a decisão, os critérios e a fonte em `analises_compatibilidade` antes de gerar a explicação. Depois, atualiza a mensagem principal e o estado do Gemini no mesmo registro. A tabela exibe as dez análises agrícolas mais recentes.

Consulte a [matriz de compatibilidade](compatibilidade_agricola.md), a [integração Gemini](integracao_gemini.md) e as [evidências de execução](validacao.md). As instruções de instalação e testes estão no [README](../README.md).
