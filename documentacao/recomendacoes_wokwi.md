# Recomendações no cenário Wokwi

A recuperação local aceita `ContextoRecuperacao.captura_wokwi` com a origem `WOKWI_HIVEMQ_NODE_RED`, valores canônicos já processados e as unidades correspondentes. Para `umidadeSolo`, informe também `metadados_umidade_solo` a partir de `complements.umidadeSolo` da telemetria. A captura pode conter parte dos quatro indicadores. Cada recomendação exige todos os seus indicadores e todas as suas condições. O rótulo de um indicador avulso continua sem valor como evidência verificada.

Como o simulador Wokwi não possui um sensor específico de umidade do solo, utilizamos a leitura de temperatura do sensor DHT22 para gerar um valor demonstrativo de umidade do solo, por meio de uma conversão linear. A leitura de umidade do ar do próprio DHT22 permanece independente e é utilizada normalmente na análise ambiental. Dessa forma, aproveitamos todos os dados gerados pelos sensores, sem adicionar leituras artificiais ou duplicar informações.

| Indicador | Canal e unidade canônica | Condições de demonstração |
|---|---|---|
| `temperaturaAr` | Temperatura ambiente do BMP180 em °C | ≥ 32 °C |
| `umidadeAr` | Umidade atmosférica do DHT22 em % | ≥ 80% |
| `umidadeSolo` | Conversão da temperatura do DHT22 em % | ≤ 25% ou ≥ 75% |
| `luminosidade` | Sinal bruto relativo do LDR em ADC | ≤ 800 ADC |

Os limites inclusivos são pontos de exercício do fluxo, sem interpretação como faixas agronômicas ótimas. O sinal ADC depende da montagem e da escala do cenário. A conversão existente tem os pontos padrão 15 °C → 0%, 25 °C → 50% e 35 °C → 100%. A recuperação usa o percentual já calculado pela telemetria e exige `simulado: true`, `origem: DHT22_TEMPERATURA` e `metodo: CONVERSAO_LINEAR_DEMONSTRATIVA`. Ela não recalcula o índice nem autentica o produtor do dado.

O catálogo ativo substitui os gatilhos de observação indisponíveis da Etapa 1.1 por sete cenários preliminares. A verificação de umidade e a observação da ventilação, da temperatura e do sombreamento reaproveitam temas anteriores com condições compatíveis com os dados disponíveis. A versão anterior serve como fixture de regressão dos filtros de procedência. As referências da Embrapa continuam candidatas, com curadoria pendente.

Os indicadores identificam condições de demonstração. A recomendação acrescenta uma verificação contextualizada pela cultura. Combinações como calor e índice hídrico baixo ou calor e umidade do ar elevada pedem todos os sinais da mesma captura. A recuperação e a orquestração mantêm `PRELIMINAR`, os metadados de simulação, as ressalvas e a prioridade de inspeção cadastrada. A prova de conceito continua local, sem rota pública ou Gemini real. O catálogo precisa estar disponível no sistema de arquivos para o carregador padrão.
