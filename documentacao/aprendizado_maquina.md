# Fase 3 — Isolation Forest com quatro indicadores

## Features e dados

A definição única em `app/inteligencia_artificial/aprendizado_maquina/caracteristicas.py` fixa a ordem usada por preparação, treinamento e inferência:

| Ordem | Feature persistida | Unidade | Origem |
|---:|---|---|---|
| 1 | `temperaturaAr` | °C | BMP180 |
| 2 | `umidadeSolo` | % | Percentual demonstrativo já convertido pelo backend a partir da temperatura DHT22 |
| 3 | `umidadeAr` | % | DHT22 |
| 4 | `luminosidade` | ADC | LDR |

A inferência lê os valores canônicos da captura já persistida em PostgreSQL. `umidadeSolo` entra como percentual; o módulo ML não repete a conversão. Os metadados `complements.umidadeSolo` continuam disponíveis na captura para registrar origem, método, simulação e temperatura bruta do DHT22.

A consulta somente leitura ao banco local `agroconnect_ai`, realizada nesta fase, encontrou **0 capturas**. Portanto, não há histórico real suficiente para treinar ou validar o detector. O treino usa exclusivamente `tests/fixtures/isolation_forest_rotulado.json`, identificado como `SIMULADO_TESTE`: 120 linhas sintéticas de treino e 64 de avaliação, com 40 rótulos normais e 24 anômalos criados para o exercício. A fixture marca expressamente que não representa medições nem limites agronômicos.

## Preparação e modelo

`preparar_leituras` valida qualidade, presença e finitude dos valores e unidades canônicas. Para cada linha, monta uma matriz NumPy `float64` exatamente na ordem centralizada acima; dicts recebidos em outra ordem são reordenados por nome. Linhas incompletas são descartadas no treino; a inferência exige uma linha completa e rejeita valor ausente, nulo, NaN, infinito ou unidade incompatível. Nenhuma transformação de unidade ou segunda conversão de `umidadeSolo` é aplicada.

O pipeline é `StandardScaler(with_mean=True, with_std=True)` seguido de `IsolationForest`. O scaler calcula média e escala das quatro colunas com o conjunto de treino, e o mesmo pipeline aplica a padronização na inferência. O scaler e o detector ficam no mesmo objeto `Pipeline`, evitando combinações de artefatos distintos.

Os parâmetros preservados do modelo anterior são `n_estimators=200`, `contamination=0.05`, `random_state=42` e `n_jobs=1`. `contamination` orienta o limiar interno estimado pelo ajuste; não é uma taxa observada em campo. O conjunto de treino não tem rótulos e o algoritmo continua não supervisionado.

A saída técnica usa `IsolationForest.predict`: `1` é estimada como não atípica e `-1` como anomalia estatística. O score exposto é `-score_samples`; valores maiores indicam maior atipicidade relativa ao conjunto de treino. O score não é probabilidade, confiança, risco, severidade ou diagnóstico agronômico. Não são geradas explicações generativas.

## Artefato, manifesto e versão

A versão ativa é `isolation-forest-v3`, formato de artefato 3, com Scikit-learn 1.9.1 no ambiente de treino. `scripts/treinar_modelo.py` aceita somente fixtures `SIMULADO_TESTE` cuja versão, ordem e unidades coincidam com a definição central. O artefato padrão fica em `modelos_treinados/isolation_forest.joblib`; o manifesto lateral fica em `modelos_treinados/isolation_forest.manifest.json`. O joblib local é ignorado pelo Git; o manifesto JSON permanece como metadado auditável ao lado do artefato. Ambos devem ser fornecidos juntos no runtime.

O manifesto inclui versão do modelo/formato, algoritmo, versão e ordem das features, unidades, versão/configuração do pré-processamento, versão Scikit-learn, origem e identificador do dataset, flag sintética, contagens, data UTC e parâmetros do Isolation Forest. O carregador compara o manifesto lateral com os metadados dentro do joblib e valida a versão do framework, ordem/unidades, etapas e dimensões de scaler/modelo e parâmetros. Artefatos antigos de três features são rejeitados; incompatibilidade ou ausência do manifesto interrompe a inferência.

O artefato anterior de três features foi preservado como `modelos_treinados/isolation_forest-v2-3features-2dd29952.backup.joblib`, com SHA-256 `2dd2995220fc19311bd52006cc10fd22b46a3fab0c585876b0776ca523a081f9`. Esse backup é somente referência e não é aceito para a inferência v3.

Treino e avaliação, executados fora do fluxo HTTP:

```powershell
python scripts\treinar_modelo.py
python scripts\avaliar_modelo.py
```

## Integração com a API e falhas

No endpoint `POST /api/v1/iot/readings`, a API valida e normaliza a entrada e commita primeiro a captura, incluindo as quatro features e metadados. Depois recupera a leitura canônica do PostgreSQL e executa inferência. O resultado e o estado `CONCLUIDA` são gravados em `iot_anomaly_analyses` e `iot_readings.analysis_status`. A unicidade de `deviceId` + `observationId` continua impedindo duplicatas; a mesma captura não duplica análise.

Se o artefato estiver ausente, incompatível ou a inferência/persistência da análise falhar, o commit anterior da telemetria é preservado, não é gravado resultado falso, o status vira `FALHA` quando o banco permite e a API informa `analysis.executed=false`. O detalhe diagnóstico é registrado nos logs; a captura permanece consultável. Leituras antigas sem resultado mantêm estado `PENDENTE`.

A migration aditiva `migrations/telemetria/003_anomaly_four_features.sql` adiciona o estado da análise e troca a constraint de três para quatro nomes em `iot_anomaly_analyses.variables`. Ela deve ser aplicada depois das migrations 001 e 002. Nenhuma migration roda no startup.

## Teste sintético e limitações

Com a fixture v3, 200 árvores, contamination 0,05 e seed 42, o treino usou 120 linhas. Na avaliação separada de 64 linhas sintéticas, o resultado observado foi precisão 1,00, revocação 1,00, F1 1,00 e matriz `[[40, 0], [0, 24]]`. Os cenários anômalos foram construídos artificialmente; essas métricas verificam execução e regressão, não generalização nem desempenho real.

O detector não foi avaliado com capturas reais da estufa, histórico temporal, safras ou rótulos revisados por especialistas. `umidadeSolo` é demonstrativa e deriva da temperatura DHT22, portanto não é uma medição física de solo. Antes de interpretação operacional, será necessário reunir dados autorizados e rotulados, revisar unidades/calibração e avaliar por períodos/dispositivos sem vazamento entre treino e teste.
