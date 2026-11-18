# 🌱 AgroConnect AI
## FIAP · Global Solution 2026/2 · Disruptive Architectures: IoT, IoB & Generative IA

---

## 👥 Integrantes

#### NOME: Rafael Pascotte Mercadante

RM564928 - 2TDSPI

#### NOME: Rafael de Freitas Moraes

RM563210 - 2TDSPI

#### NOME: Carolina Nascimento Gonçalves

RM564786 - 2TDSPI

#### NOME: Emanuelly Ventura do Nascimento

RM562339 - 2TDSPI

#### NOME: Julia Sayuri Kina

RM564555 - 2TDSPI

---

## 📌 Problema e público

O projeto aborda o tema 07 da CitizenTech, **Pequenos produtores sem informação para decidir**. O AgroConnect AI ajuda pequenos produtores rurais a interpretar as condições de uma estufa, identificar leituras que merecem atenção e consultar critérios de compatibilidade entre uma cultura e um tipo de solo. O painel reúne as leituras, a classificação estatística, os critérios agrícolas e as respectivas fontes.

Por exemplo, ao consultar **Feijão + Argiloso**, o painel apresenta o resultado **Desconhecido** e explica o que precisa ser verificado no solo, como a compactação e o encharcamento. Essa orientação ajuda a definir o próximo passo da avaliação. O projeto contribui para o **ODS 2 — Fome Zero e Agricultura Sustentável** ao apoiar decisões de cultivo com informações rastreáveis.

### Arquitetura

```mermaid
flowchart TB
    subgraph ingestao["1. Ingestão e classificação"]
        W["ESP32 no Wokwi"] --> M["HiveMQ · MQTT"]
        M --> N["Node-RED · agrupa quatro indicadores"]
        N --> I["FastAPI · POST /api/v1/iot/readings"]
        I -->|"Valida, converte e salva a captura"| P[("PostgreSQL")]
        P -->|"Indicadores persistidos"| F["Isolation Forest v3"]
        F -->|"Grava classificação e score"| P
        F -->|"Contexto da explicação"| G["Google Gemini"]
        G -->|"FastAPI valida e salva a explicação"| P
    end

    subgraph consulta["2. Análise agrícola"]
        D["Dashboard · seleção de cultura e solo"] --> A["FastAPI · POST /api/v1/agricultura/analise-unificada"]
        A <-->|"Lê regras, captura e classificação; grava histórico"| P
        R["Base técnica local · Embrapa e Incaper"] -->|"Busca por cultura e solo"| A
        A <-->|"Contexto e explicação em JSON"| G
        A -->|"Resultado da análise"| D
    end
```

Na ingestão, o FastAPI salva a captura antes de executar o detector. Na análise agrícola, a API seleciona a captura válida mais recente dentro da janela configurada e consulta a classificação já persistida. A compatibilidade é determinada pela matriz de **25 combinações de culturas e solos**. A decisão é gravada antes da geração, e o Gemini acrescenta a explicação ao mesmo registro de histórico.

---

## 📊 Dados e preparação

| Fonte | Preparação e uso |
| --- | --- |
| **Sensores no Wokwi** | O Node-RED agrupa temperatura do ar do BMP180, temperatura e umidade relativa do DHT22 e luminosidade do LDR. O FastAPI valida os valores e as unidades. Converte a temperatura do DHT22 em um índice demonstrativo de umidade do solo e mantém a umidade relativa do ar como uma leitura separada. |
| **Conjunto de treinamento e avaliação** | A [fixture sintética](tests/fixtures/isolation_forest_rotulado.json) fornece 120 exemplos de treino e 64 exemplos rotulados de avaliação. Os indicadores são ordenados de forma canônica e padronizados com o scaler ajustado no treino. |
| **Fontes agrícolas** | Os critérios e as referências se baseiam em publicações da Embrapa e do Incaper. Na análise unificada, o recuperador local filtra trechos por cultura, solo e assunto. Os resultados mantêm título, instituição, endereço e curadoria. |

Veja os guias de [telemetria](documentacao/telemetria_iot.md), [modelo](documentacao/aprendizado_maquina.md) e [matriz de compatibilidade](documentacao/compatibilidade_agricola.md).

---

## 🛠️ Escolhas técnicas

| Tecnologia | Por que foi escolhida |
| --- | --- |
| **Isolation Forest v3 com scikit-learn** | Detecta padrões atípicos nas quatro leituras usando treinamento não supervisionado. A classificação e o score ficam no PostgreSQL e podem ser reutilizados em novas análises agrícolas. |
| **RAG básico com documentos locais** | Os filtros por cultura, classe de solo e assunto são adequados ao tamanho da base e permitem rastrear quais trechos fundamentam a explicação. |
| **Google Gemini via API** | Organiza a regra agrícola, a telemetria e as referências em uma explicação em português. A API solicita JSON estruturado e valida os campos e as referências antes de exibir o resultado. A validação local usou `gemini-3.5-flash-lite`. |
| **FastAPI, PostgreSQL e Docker Compose** | O FastAPI centraliza a ingestão e a consulta. O PostgreSQL mantém capturas, regras e histórico. O Docker Compose provisiona o banco local. As migrations usam SQL e blocos PL/pgSQL para verificar e criar restrições de estado no banco. |

---

## 🚀 Executar localmente

**Requisitos:** Python x64 3.12 ou 3.13, Docker com contêineres Linux e `uv` 0.13.7. Para transmitir novas capturas, prepare também o Wokwi, o HiveMQ e o Node-RED conforme o [guia de telemetria](documentacao/telemetria_iot.md).

### 1. Instalar as dependências

Na raiz do repositório, execute no PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv==0.13.7
$env:UV_PROJECT_ENVIRONMENT = ".venv"
uv sync --locked --python .\.venv\Scripts\python.exe
```

### 2. Configurar o banco e o Gemini

Crie o `.env` local a partir de [`.env.example`](.env.example) e preencha os valores do PostgreSQL, a URL `TELEMETRY_DATABASE_URL` e a chave `GEMINI_API_KEY`. Para reproduzir o modelo usado na validação local, defina `GEMINI_MODEL=gemini-3.5-flash-lite`.

```powershell
docker compose up -d postgres
```

Aplique as migrations **001 a 008** na ordem indicada no [guia do PostgreSQL](documentacao/postgresql_local.md).

### 3. Gerar o modelo e iniciar a API

```powershell
python scripts/treinar_modelo.py
python -m uvicorn app.principal:app --reload
```

- [Dashboard do AgroConnect](http://127.0.0.1:8000/dashboard)
- [Swagger UI](http://127.0.0.1:8000/docs)
- [Prontidão do PostgreSQL](http://127.0.0.1:8000/health/ready)

No dashboard, confira **Última captura**, selecione uma cultura e um solo e clique em **Analisar combinação**. O resultado aparece ao lado dos critérios e das referências. A tabela de histórico exibe as análises persistidas.

### 4. Importar o fluxo Node-RED

No Node-RED, abra **Menu → Importar** e selecione o [fluxo de ingestão do AgroConnect](iot/node_red/fluxo_agroconnect.json). Abra a configuração compartilhada **HiveMQ Cloud**, troque o host de exemplo pelo endereço do seu cluster e informe usuário e senha no próprio Node-RED. O fluxo usa MQTT com TLS na porta `8883`.

No nó HTTP, confira a URL `http://127.0.0.1:8000/api/v1/iot/readings`. Quando a API estiver em outro host ou contêiner, informe um endereço alcançável pelo processo do Node-RED. Clique em **Deploy**, inicie o Wokwi e acompanhe a resposta da API no nó de depuração. O [guia de telemetria](documentacao/telemetria_iot.md#importar-o-fluxo-node-red) detalha a configuração e os tópicos.

---

## 🧪 Avaliação e evidências

O [registro de validação](documentacao/validacao.md) reúne consultas reproduzíveis, resultados locais e métricas. Na verificação de 17/11/2026:

- **299 testes** passaram com PostgreSQL, incluindo ingestão, persistência e histórico quando o Gemini responde ou expira.
- **53 capturas Wokwi** foram classificadas pelo Isolation Forest, com 36 observações atípicas e 9 explicações Gemini gravadas para essas capturas.
- A avaliação do modelo sobre **64 exemplos sintéticos** obteve precisão, revocação e F1 de **1,00**. Essas métricas descrevem o conjunto de avaliação. Os registros Wokwi documentam a execução do fluxo integrado.

Use um banco de testes dedicado configurado em `TEST_TELEMETRY_DATABASE_URL`, conforme o [guia PostgreSQL](documentacao/postgresql_local.md), e execute:

```powershell
python scripts/avaliar_modelo.py
python -m pytest -q
```

---

## ⚠️ Interpretação e uso responsável

- O **score do Isolation Forest** indica atipicidade em relação ao conjunto de treino. Serve para priorizar leituras que merecem conferência.
- O **índice demonstrativo de umidade do solo** é calculado com a temperatura do DHT22. Para decisões sobre a umidade real, é necessária uma medição no solo.
- A **explicação Gemini** serve como apoio informativo e cita as referências recuperadas. A classificação vem do Isolation Forest, e o resultado de compatibilidade vem das regras cadastradas. As condições do terreno, como drenagem e compactação, devem ser confirmadas antes de uma decisão de cultivo.
- A chave Gemini e as credenciais do banco ficam no `.env` local. O contexto enviado ao Gemini reúne dados técnicos da captura e da análise agrícola.

---

## 🤖 Uso de IA no desenvolvimento

O Codex auxiliou na revisão do README e dos guias, na organização das evidências e no apoio ao desenvolvimento e à verificação do projeto. O Google Gemini é o modelo generativo utilizado pela aplicação.


## Link do video da demonstração

[https://youtu.be/oQxdT7qftBk](https://www.youtube.com/watch?v=oQxdT7qftBk)

## 📚 Guias da entrega

- [Arquitetura](documentacao/arquitetura.md)
- [Análise agrícola](documentacao/analise_agricola.md)
- [Evidências de validação](documentacao/validacao.md)
- [Integração Gemini](documentacao/integracao_gemini.md)
- [Dashboard](documentacao/dashboard.md)
- [Contrato HTTP](documentacao/contrato_http.md)
