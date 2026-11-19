# Isolation Forest com quatro indicadores

## Indicadores e dados

A definição única em `app/inteligencia_artificial/aprendizado_maquina/caracteristicas.py` fixa a ordem usada por preparação, treinamento e inferência:

| Ordem | Feature persistida | Unidade | Origem |
|---:|---|---|---|
| 1 | `temperaturaAr` | °C | BMP180 |
| 2 | `umidadeSolo` | % | Percentual demonstrativo já convertido pelo backend a partir da temperatura DHT22 |
| 3 | `umidadeAr` | % | DHT22 |
| 4 | `luminosidade` | ADC | LDR |

A inferência lê os valores canônicos da captura já persistida em PostgreSQL. O modelo recebe `umidadeSolo` como percentual, após a conversão no módulo de telemetria. Os metadados `complements.umidadeSolo` continuam disponíveis na captura para registrar origem, método, simulação e temperatura bruta do DHT22.

O treinamento usa a fixture `tests/fixtures/isolation_forest_rotulado.json`, com 120 exemplos sintéticos de treino. A avaliação separada usa 64 exemplos rotulados, sendo 40 normais e 24 anômalos. As capturas Wokwi processadas pela API são documentadas no [registro de validação](validacao.md).

## Preparação e modelo

`preparar_leituras` seleciona linhas com qualidade válida, valores finitos e unidades canônicas. A função lê os indicadores na ordem fixa de `VARIAVEIS_MODELO` e monta uma matriz NumPy `float64` na sequência da tabela. Para cada inferência, o detector recebe uma linha com os quatro indicadores nas unidades persistidas.

O pipeline é `StandardScaler(with_mean=True, with_std=True)` seguido de `IsolationForest`. O scaler calcula média e escala das quatro colunas com o conjunto de treino, e o mesmo pipeline aplica a padronização na inferência. O scaler e o detector ficam no mesmo objeto `Pipeline`.

Os parâmetros do modelo são `n_estimators=200`, `contamination=0.05`, `random_state=42` e `n_jobs=1`. `contamination` orienta o limiar interno calculado durante o ajuste. O treinamento é não supervisionado. Os rótulos são usados na avaliação do detector.

A saída técnica usa `IsolationForest.predict`: `1` indica uma observação estimada como não atípica e `-1` indica uma anomalia estatística. O score exposto é `-score_samples`; valores maiores indicam maior atipicidade relativa ao conjunto de treino. A API solicita a explicação Gemini depois de persistir o resultado do detector.

## Artefato, manifesto e versão

A versão ativa é `isolation-forest-v3`, formato de artefato 3, com Scikit-learn 1.9.1 no ambiente de treino. `scripts/treinar_modelo.py` aceita somente fixtures `SIMULADO_TESTE` cuja versão, ordem e unidades coincidam com a definição central. O artefato padrão fica em `modelos_treinados/isolation_forest.joblib`; o manifesto lateral fica em `modelos_treinados/isolation_forest.manifest.json`. O joblib local é ignorado pelo Git; o manifesto JSON permanece como metadado auditável ao lado do artefato. Ambos devem ser fornecidos juntos no runtime.

O manifesto inclui versão do modelo/formato, algoritmo, versão e ordem das features, unidades, versão/configuração do pré-processamento, versão Scikit-learn, origem e identificador do dataset, flag sintética, contagens, data UTC e parâmetros do Isolation Forest. O carregador compara o manifesto lateral com os metadados dentro do joblib e valida a versão do framework, ordem/unidades, etapas e dimensões de scaler/modelo e parâmetros.

Treino e avaliação, executados fora do fluxo HTTP:

```powershell
python scripts\treinar_modelo.py
python scripts\avaliar_modelo.py
```

## Integração com a API

No endpoint `POST /api/v1/iot/readings`, a API valida e normaliza a entrada e persiste primeiro a captura, incluindo as quatro features e metadados. Depois recupera a leitura canônica do PostgreSQL e executa inferência. O resultado e o estado `CONCLUIDA` são gravados em `iot_anomaly_analyses` e `iot_readings.analysis_status`. O par `deviceId` e `observationId` identifica uma captura. O banco associa até uma análise a cada captura.

A API grava o estado de execução em `iot_readings.analysis_status`. A captura e a análise persistida podem ser consultadas em `GET /api/v1/dashboard/readings`.

A migration aditiva `migrations/telemetria/003_anomaly_four_features.sql` adiciona o estado da análise e troca a constraint de três para quatro nomes em `iot_anomaly_analyses.variables`. Ela deve ser aplicada depois das migrations 001 e 002. Nenhuma migration roda no startup.

## Avaliação do detector

Execute `python scripts/avaliar_modelo.py` para obter precisão, revocação, F1 e a matriz de confusão. O [registro de validação](validacao.md) reúne a avaliação sintética e exemplos de classificação das capturas Wokwi no PostgreSQL.

## Por que o modelo e onde ele atua

O Isolation Forest permite procurar combinações atípicas com treinamento não supervisionado. Suas árvores dividem as observações por cortes nos valores das variáveis. Uma combinação que costuma se separar das demais em poucos cortes tende a ter um score maior de atipicidade. No AgroConnect, essa comparação usa a distribuição do conjunto sintético de treino.

- **Treino.** [`treinar_modelo.py`](../scripts/treinar_modelo.py) lê a fixture, confere seu contrato e ajusta o pipeline. O scaler e o detector seguem juntos no artefato para que a inferência aplique a mesma transformação usada no treino.
- **Inferência.** [`preparar_leituras()`](../app/inteligencia_artificial/aprendizado_maquina/preparacao.py) valida qualidade, valores e unidades e monta a matriz. [`predizer()`](../app/inteligencia_artificial/aprendizado_maquina/detector_anomalias.py) usa `predict()` para a classe e `-score_samples()` para a pontuação. Se os dados ou o score forem inválidos, a inferência interrompe o processamento.
- **Destino.** A [rota de telemetria](../app/telemetria/rotas.py) grava a classificação, o score, a versão e a justificativa, e só então solicita a explicação. O dashboard consulta o registro persistido. A análise agrícola pode reutilizar a mesma classificação.
