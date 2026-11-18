# Explicações com Google Gemini

O AgroConnect usa o SDK `google-genai` por meio de um cliente compartilhado. Configure `GEMINI_API_KEY`, `GEMINI_MODEL` e `GEMINI_TIMEOUT_SEGUNDOS` no ambiente de execução. Os valores reais ficam no ambiente local. O registro de validação utilizou `gemini-3.5-flash-lite`.

| Fluxo | Contexto da explicação | Registro |
| --- | --- | --- |
| Anomalias IoT | Classificação, score e indicadores da captura | `iot_anomaly_analyses` |
| Análise agrícola unificada | Resultado cadastrado, captura, classificação associada e documentos recuperados | `analises_compatibilidade` |
| Compatibilidade pelo contrato original | Resultado e critérios da regra ativa | `analises_compatibilidade` |

O resultado determinístico é persistido primeiro. A API solicita JSON estruturado ao Gemini e valida o retorno antes de atualizar a explicação e seu estado. Na análise unificada, as referências são citadas por IDs recuperados pelo código Python. As orientações e ressalvas aparecem no resultado do dashboard, e o histórico registra a mensagem principal.

A API registra separadamente a classificação do modelo, o resultado da regra e o estado da geração. O dashboard usa esses campos para apresentar a decisão e a explicação correspondente. Consulte [as evidências de execução](validacao.md) e [o fluxo agrícola](analise_agricola.md).
