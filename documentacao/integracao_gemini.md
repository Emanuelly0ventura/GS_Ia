# Explicações com Google Gemini

O AgroConnect usa o SDK `google-genai` por meio de um cliente compartilhado. Configure `GEMINI_API_KEY`, `GEMINI_MODEL` e `GEMINI_TIMEOUT_SEGUNDOS` no ambiente de execução. Os valores reais ficam no ambiente local. O registro de validação utilizou `gemini-3.5-flash-lite`. O `.env.example` fornece um valor de configuração inicial para `GEMINI_MODEL`.

| Fluxo | Contexto da explicação | Registro |
| --- | --- | --- |
| Anomalias IoT | Classificação, score e indicadores da captura | `iot_anomaly_analyses` |
| Análise agrícola unificada | Resultado cadastrado, captura, classificação associada e documentos recuperados | `analises_compatibilidade` |
| Compatibilidade pelo contrato original | Resultado e critérios da regra ativa | `analises_compatibilidade` |

O resultado determinístico é persistido primeiro. A API solicita JSON estruturado ao Gemini e valida o retorno antes de atualizar a explicação e seu estado. Na análise unificada, as referências são citadas por IDs recuperados pelo código Python. As orientações e ressalvas aparecem no resultado do dashboard, e o histórico registra a mensagem principal.

A API registra separadamente a classificação do modelo, o resultado da regra e o estado da geração. O dashboard usa esses campos para apresentar a decisão e a explicação correspondente. Consulte [as evidências de execução](validacao.md) e [o fluxo agrícola](analise_agricola.md).

## Como o contexto chega ao modelo

- **Anomalias IoT.** Após gravar o resultado do Isolation Forest, `receber()` passa classificação, score, indicadores, unidades e complementos a `tentar_explicar_anomalia()`. O serviço usa `EntradaExplicacaoAnomalia` para construir a solicitação. O texto e o estado voltam para os campos `generative_*` em `iot_anomaly_analyses`. [Rota](../app/telemetria/rotas.py) · [Orquestração](../app/inteligencia_artificial/generativa/orquestracao.py) · [Serviços](../app/inteligencia_artificial/generativa/servicos.py)
- **Análise agrícola unificada.** `preparar_contexto()` reúne regra, leitura, anomalia e trechos. `gerar_mensagem()` envia esse contexto ao provedor e exige `MensagemAgricola`. Confere se os IDs citados estão na recuperação e valida o texto. O dashboard recebe mensagem, orientações e ressalvas. O histórico guarda a mensagem principal e o estado. [Fluxo unificado](../app/compatibilidade/analise_unificada.py)
- **Compatibilidade pelo contrato original.** `analisar_compatibilidade()` registra a análise do par e, quando há regra e critérios, chama `tentar_explicar_compatibilidade()` com esse contexto. Sem critérios, registra `SEM_CRITERIOS`. O serviço devolve uma explicação para a resposta HTTP e o histórico agrícola. [Rota](../app/compatibilidade/rotas.py)
- **Recomendações por captura.** O gerador recebe os itens selecionados do catálogo local para compor orientações ligadas aos itens recuperados. A validação confere o conteúdo antes de devolvê-lo ao consumidor da rota. [Fluxo de recomendações](recomendacoes_wokwi.md)

## Chamada, validação e falha

`criar_provedor_gemini()` configura o cliente a partir do ambiente. `ProvedorGemini.gerar()` serializa os dados em JSON, envia esse conteúdo e as instruções a `generate_content()` e solicita uma resposta no esquema Pydantic do fluxo. O esquema valida a resposta antes que ela volte ao chamador. As rotas de telemetria e análise agrícola registram a falha de geração separadamente do resultado já salvo. [Fábrica](../app/inteligencia_artificial/generativa/fabrica.py) · [Cliente](../app/inteligencia_artificial/generativa/cliente_gemini.py)
