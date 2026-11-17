# Recomendações no cenário Wokwi

A recuperação local aceita `ContextoRecuperacao.captura_wokwi` com a origem `WOKWI_HIVEMQ_NODE_RED`, valores canônicos já processados e as unidades correspondentes. Para `umidadeSolo`, informe também `metadados_umidade_solo` a partir de `complements.umidadeSolo` da telemetria. A captura pode conter parte dos quatro indicadores. Cada recomendação exige todos os seus indicadores e todas as suas condições. O rótulo de um indicador avulso continua sem valor como evidência verificada.

Como o simulador Wokwi não possui um sensor específico de umidade do solo, utilizamos a leitura de temperatura do sensor DHT22 para gerar um valor demonstrativo de umidade do solo, por meio de uma conversão linear. A leitura de umidade do ar do próprio DHT22 permanece independente e é utilizada normalmente na análise ambiental. Dessa forma, aproveitamos todos os dados gerados pelos sensores, sem adicionar leituras artificiais ou duplicar informações.

| Indicador | Canal e unidade canônica | Condições de demonstração |
|---|---|---|
| `temperaturaAr` | Temperatura ambiente do BMP180 em °C | ≥ 32 °C |
| `umidadeAr` | Umidade atmosférica do DHT22 em % | ≥ 80% |
| `umidadeSolo` | Conversão da temperatura do DHT22 em % | ≤ 25% ou ≥ 75% |
| `luminosidade` | Sinal bruto relativo do LDR em ADC | ≤ 800 ADC |

Os limites inclusivos são pontos de exercício do fluxo, sem interpretação como faixas agronômicas ótimas. O sinal ADC depende da montagem e da escala do cenário. A conversão existente tem os pontos padrão 15 °C → 0%, 25 °C → 50% e 35 °C → 100%. A recuperação usa o percentual já calculado pela telemetria e exige `simulado: true`, `origem: DHT22_TEMPERATURA` e `metodo: CONVERSAO_LINEAR_DEMONSTRATIVA`. O validador confere o percentual com a mesma função e os mesmos limites da telemetria. A captura continua sendo demonstrativa e a procedência declarada não é autenticada.

O catálogo ativo substitui os gatilhos de observação indisponíveis da Etapa 1.1 por sete cenários preliminares. A verificação de umidade e a observação da ventilação, da temperatura e do sombreamento reaproveitam temas anteriores com condições compatíveis com os dados disponíveis. A versão anterior serve como fixture de regressão dos filtros de procedência. As referências da Embrapa continuam candidatas, com curadoria pendente.

Os indicadores identificam condições de demonstração. A recomendação acrescenta uma verificação contextualizada pela cultura. Combinações como calor e índice hídrico baixo ou calor e umidade do ar elevada pedem todos os sinais da mesma captura. A recuperação e a orquestração mantêm `PRELIMINAR`, os metadados de simulação, as ressalvas e a prioridade de inspeção cadastrada. O fluxo está disponível como função interna. O catálogo precisa estar disponível no sistema de arquivos para o carregador padrão.

## Orquestração e Gemini

`orquestrar(catalogo, contexto)` começa pela recuperação. Ausência de captura ou de indicadores necessários e cultura incompatível levam a `SEM_EVIDENCIA_SUFICIENTE` quando nenhuma entrada qualifica. Nesse caso, a função devolve as exclusões antes de instanciar o provedor. Erros de validação da captura ou da recuperação mantêm seu comportamento próprio.

Quando há resultados, a orquestração projeta somente os dados permitidos e usa a fábrica Gemini compartilhada para construir o adaptador `GeradorGeminiRecomendacoes`. A cultura selecionada é passada explicitamente ao adaptador. O Gemini escolhe a ordem dos trechos do catálogo e os índices das referências de cada item. IDs, prioridade, valores, unidades, procedência, simulação, curadoria e ressalvas vêm da aplicação. As sete entradas permanecem `PENDENTE` e a orientação exibida pelo fluxo é `PRELIMINAR`.

| Situação | Estado e código |
|---|---|
| Gemini sem conteúdo suficiente para compor | `SEM_CONTEUDO_SUFICIENTE` |
| Falta de configuração, timeout, HTTP 429 ou indisponibilidade como HTTP 503 | `FALHA_GERADOR`, com `GEMINI_NOT_CONFIGURED`, `GEMINI_TIMEOUT`, `GEMINI_RATE_LIMITED` ou `GEMINI_UNAVAILABLE` |
| Resposta inválida do provedor | `RESPOSTA_INVALIDA` com `GEMINI_INVALID_RESPONSE` |
| Erro inesperado na geração | `FALHA_GERADOR` com `GENERATION_INTERNAL_ERROR` |

Em falhas, a seleção projetada e as exclusões ficam disponíveis sem orientação gerada. A operação não repete chamadas. A verificação final também rejeita respostas incompatíveis com os IDs, as referências ou as composições permitidas.

Chamadores podem continuar injetando um `GeradorRecomendacoes`. Os testes também substituem a fábrica por um cliente com SDK falso para cobrir o caminho padrão e os erros, sem credenciais ou rede. A cobertura demonstra o comportamento do fluxo acadêmico. A qualidade agronômica e a validação das referências dependem de curadoria própria. A integração ainda não foi exposta por rota HTTP.
