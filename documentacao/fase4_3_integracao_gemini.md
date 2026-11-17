# Fase 4.3 — Explicações Gemini nos fluxos de análise

## Sequência dos fluxos

### Anomalias IoT

1. Validar e persistir a captura e os quatro indicadores.
2. Executar o Isolation Forest v3 e persistir classificação, score, variáveis e justificativa.
3. Se o modelo concluir, chamar o serviço explicativo existente com o resultado e os dados persistidos.
4. Salvar a explicação em `generative_explanation`, o estado em `generative_status` e eventual `generative_error_code`.

Uma falha na etapa generativa não altera a classificação nem remove a captura ou a análise ML. Se o modelo falhar, Gemini não é chamado. A resposta de `POST /api/v1/iot/readings` expõe os campos `generativeExplanation`, `generativeStatus` e `generativeErrorCode` dentro de `analysis`.

### Compatibilidade agrícola

1. Consultar a regra ativa e produzir o resultado determinístico.
2. Persistir snapshot de sementes, solos, resultado, critérios, justificativa e fonte.
3. Chamar a explicação existente somente se houver regra ativa e critérios.
4. Salvar `explicacao_gemini`, `estado_explicacao` e `codigo_erro_explicacao` na própria análise.

Sem regra válida, o resultado continua `DADOS_INSUFICIENTES`, estado generativo `SEM_CRITERIOS` e nenhuma chamada é feita. A resposta expõe `explicacaoGemini`, `estadoExplicacao` e `codigoErroExplicacao`.

## Estados generativos

| Estado | Significado |
| --- | --- |
| `PENDENTE` | Resultado determinístico persistido, explicação ainda não finalizada. |
| `NAO_CONFIGURADO` | Chave/modelo não configurados; nenhuma chamada foi realizada. |
| `SEM_CRITERIOS` | Fluxo agrícola sem regra/critério suficiente; nenhuma chamada foi realizada. |
| `CONCLUIDA` | Explicação validada e persistida. |
| `FALHA` | Serviço, limite, timeout ou resposta/persistência falhou; resultado determinístico permanece. |

O texto generativo nunca é usado para alterar status de anomalia, score, resultado agrícola, critérios ou justificativa oficial. Os códigos de erro são sanitizados; credenciais e detalhes do provedor não são enviados nas respostas.

## Configuração e testes

Configure `GEMINI_API_KEY`, `GEMINI_MODEL` e `GEMINI_TIMEOUT_SEGUNDOS` somente no ambiente local ou de execução. O código não faz chamadas durante importação ou startup. Os testes dos fluxos usam provedores simulados; não precisam de chave real e não fazem chamadas pagas. Integração PostgreSQL é executada separadamente e exige `TEST_TELEMETRY_DATABASE_URL` apontando para banco com nome terminado em `_test`, migrado até 006.

Migration `006_explicacoes_gemini.sql` adiciona apenas campos e restrições de estado às tabelas de análise existentes. Ela não altera captura, classificação, score, regra agrícola ou dados existentes.
