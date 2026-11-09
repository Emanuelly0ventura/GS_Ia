# Fase 3 — Isolation Forest

## Objetivo e limites

O módulo identifica observações estatisticamente atípicas em relação ao conjunto usado no treinamento. Isolation Forest foi escolhido por ser não supervisionado, trabalhar com vetores numéricos tabulares e não exigir rótulo de cada observação para ajustar o baseline. A saída não é diagnóstico agronômico, risco ou probabilidade de falha.

## Variáveis e contrato provisório

O contrato interno usa `umidadeSolo`, `temperaturaAr`, `umidadeAr` e `luminosidade`. Esses nomes não substituem o contrato do Backend C# e deverão ser mapeados pelo adaptador após a confirmação. O modelo exige valores finitos e uma unidade declarada e consistente por variável. Ele não converte unidades nem infere calibração; linhas sem qualidade canônica `VALIDA`, valores faltantes e unidades ausentes são descartados, e unidades divergentes interrompem a preparação. A enumeração de qualidade também é interna/provisória; o adaptador futuro mapeará códigos externos confirmados.

## Preparação e pipeline

As observações são ordenadas segundo as quatro variáveis fixas, convertidas em matriz numérica e padronizadas por `StandardScaler`. Em seguida, um `IsolationForest` é ajustado com `n_estimators`, `contamination` e `random_state` configuráveis. A contaminação controla a fração esperada de outliers no conjunto de ajuste; não é uma métrica de acurácia nem uma probabilidade. A inferência exige as mesmas unidades e não treina novamente.

O escore retornado é `-score_samples`, de modo que um valor maior indica maior atipicidade no escore do modelo. A classificação normal/anomalia usa `predict` do Isolation Forest. O escore não é normalizado e não representa confiança probabilística.

## Treinamento e artefatos

Treinar somente por script, fora do fluxo HTTP. O manifesto registra versão interna, versão Scikit-learn, variáveis, unidades, origem, quantidades e parâmetros. `joblib` grava em arquivo temporário e substitui o destino atomicamente. O carregador aceita somente artefatos locais no formato esperado e na mesma versão Scikit-learn; nunca carregue modelos enviados por usuários ou fontes desconhecidas. Retreine o artefato após mudanças incompatíveis do ambiente.

```powershell
.\.venv-311-x64\Scripts\python.exe scripts\treinar_modelo.py
.\.venv-311-x64\Scripts\python.exe scripts\avaliar_modelo.py
```

O artefato padrão vai para `modelos_treinados/isolation_forest.joblib`, ignorado pelo Git. O treinamento não ocorre no startup nem em requisições.

## Demonstração HTTP local

Inicie o modelo com o script de treinamento, rode `uvicorn app.principal:app --reload` em ambiente `desenvolvimento` e envie uma observação sintética: 

```powershell
$corpo = @{
  idObservacao = "demo-atipica"
  valores = @{ umidadeSolo = 7.0; temperaturaAr = 7.0; umidadeAr = 7.0; luminosidade = 7.0 }
  unidades = @{ umidadeSolo = "indice_sintetico_sem_unidade_fisica"; temperaturaAr = "indice_sintetico_sem_unidade_fisica"; umidadeAr = "indice_sintetico_sem_unidade_fisica"; luminosidade = "indice_sintetico_sem_unidade_fisica" }
  qualidade = "VALIDA"
  origem = "SIMULADO_TESTE"
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/anomalias/analisar-demo -ContentType "application/json" -Body $corpo
```

O endpoint só responde em ambiente de desenvolvimento/teste, aceita apenas `SIMULADO_TESTE` e exige um modelo já treinado. Não há endpoint de treinamento.

## Avaliação reproduzível

`tests/fixtures/isolation_forest_rotulado.json` separa 120 observações sintéticas de treinamento de 64 observações rotuladas para avaliação (40 dentro da distribuição artificial e 24 valores extremos artificiais). A unidade é declarada como índice sintético sem unidade física. O conjunto não representa leituras reais nem condições normais agronômicas. O script reporta precisão, revocação, F1 e matriz de confusão calculadas nesse conjunto. Esses resultados descrevem somente a fixture sintética e não evidenciam desempenho em campo.

## Limitações

O schema externo, unidades, calibração e códigos de qualidade ainda dependem do Backend C# e dos responsáveis pelos sensores. O modelo não compreende limites da cultura, estação do ano, fase de plantio ou relações causais; alterações sazonais podem mudar o baseline. A avaliação sintética é ilustrativa. Antes de qualquer uso operacional, será necessário obter dados autorizados, definir segmentação por dispositivo/sensor e unidade, validar qualidade temporal e realizar avaliação em dados reais rotulados e revisados por especialistas.
