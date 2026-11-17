# AgroConnect AI

API independente de demonstração do AgroConnect com FastAPI, PostgreSQL local próprio, ingestão IoT, dashboard, Isolation Forest v3 com quatro indicadores canônicos e serviços generativos internos para explicações via Google Gemini. O snapshot mobile predefinido não depende do simulador. O serviço não depende do Backend C# nem do aplicativo mobile.

## Requisitos e instalação

- Python x64 3.12 ou 3.13, Docker Linux amd64 e `uv` 0.13.7.
- `pyproject.toml` e `requirements.txt` declaram as dependências diretas; `uv.lock` reproduz dependências e hashes.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv==0.13.7
$env:UV_PROJECT_ENVIRONMENT = ".venv"
uv sync --locked --python .\.venv\Scripts\python.exe
```

Use `uv sync --locked` para respeitar o lock.

## Executar

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.principal:app --reload
```

- Health: <http://127.0.0.1:8000/health>
- Prontidão: <http://127.0.0.1:8000/health/ready>
- Swagger UI: <http://127.0.0.1:8000/docs>
- Dashboard: <http://127.0.0.1:8000/dashboard>

A prontidão verifica o PostgreSQL; a conexão é opcional no startup. O dashboard é servido pelo próprio FastAPI, sem build ou dependência de frontend adicional. Por padrão, consulta a API na mesma origem. Para configurar outra origem HTTP(S), defina `DASHBOARD_API_BASE_URL` no ambiente antes de iniciar a API; não inclua credenciais nessa URL.

## PostgreSQL local

O banco da IA é independente e usa Docker Compose com volume persistente. Configure o ambiente local, inicie o container e aplique migrations SQL manualmente. Consulte [`documentacao/postgresql_local.md`](documentacao/postgresql_local.md). O startup da API não executa DDL.

## Configuração Gemini

Copie `.env.example` para `.env` e configure `GEMINI_API_KEY`, `GEMINI_MODEL` e `GEMINI_TIMEOUT_SEGUNDOS`. A chave é armazenada como segredo e nunca deve ser versionada. Esta aplicação não chama o Gemini durante importação ou inicialização. Não há fallback para outro provedor.

A camada generativa possui dois serviços independentes: explica uma classificação/score de anomalia já calculados e um resultado de compatibilidade já decidido por regras determinísticas. Os fluxos chamam esses serviços somente após persistir o resultado oficial. O Gemini não altera classificação, score, critérios ou decisão. Explicação, estado e código de erro ficam em campos próprios; falhas generativas não removem o resultado determinístico. Sem chave não há chamada e, sem critérios agrícolas, a explicação é ignorada. A integração é detalhada em [`documentacao/fase4_3_integracao_gemini.md`](documentacao/fase4_3_integracao_gemini.md).

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes PostgreSQL usam exclusivamente `TEST_TELEMETRY_DATABASE_URL` com nome de banco terminado em `_test`; veja `documentacao/postgresql_local.md`. Os testes Gemini usam clientes simulados, sem chave real.

## Docker

```powershell
docker compose up -d postgres
docker build -t agroconnect-ai .
docker run --rm -p 8000:8000 -e PORT=8000 -e TELEMETRY_DATABASE_URL=$env:TELEMETRY_DATABASE_URL -e GEMINI_API_KEY=$env:GEMINI_API_KEY -e GEMINI_MODEL=$env:GEMINI_MODEL -v "${PWD}/modelos_treinados:/app/modelos_treinados:ro" agroconnect-ai
```

Configure credenciais no ambiente de execução, nunca na imagem ou no Git. Monte o modelo Isolation Forest e seu manifesto local em runtime; migrations continuam manuais.

## Machine Learning (demonstração)

O Isolation Forest v3 usa as quatro features canônicas; o treino é manual, baseado em fixture sintética identificada, e não ocorre no startup nem nas requisições.

```powershell
.\.venv\Scripts\python.exe scripts\treinar_modelo.py
.\.venv\Scripts\python.exe scripts\avaliar_modelo.py
```

`POST /api/v1/anomalias/analisar-demo` é exclusivo de desenvolvimento/teste e aceita apenas dados `SIMULADO_TESTE`. Consulte [`documentacao/aprendizado_maquina.md`](documentacao/aprendizado_maquina.md). O score não é probabilidade nem diagnóstico agronômico.

## IoT e dashboard

Consulte [`documentacao/telemetria_iot.md`](documentacao/telemetria_iot.md) para contrato Node-RED e endpoints. `POST /api/v1/iot/readings` persiste `temperaturaAr`, `umidadeSolo`, `umidadeAr` e `luminosidade`; no payload recebido, `umidadeSolo` contém temporariamente a temperatura DHT22 em °C e é convertida para `%` pelo backend. O Isolation Forest analisa as quatro features persistidas. O dashboard consulta `/health`, `/health/ready`, `/api/v1/dashboard/readings`, `/api/v1/dashboard/status`, os catálogos agrícolas e `/api/v1/agricultura/analises`. O GET de análises aceita `limit` de 1 a 100 (padrão 20); telemetria aceita `limit` de 1 a 1000. Consulte [`documentacao/dashboard.md`](documentacao/dashboard.md).

## Próximas integrações

- Confirmar schema, unidades, qualidade, autorização e relações de acesso com o Backend C# antes de integrar Backend C# e mobile.

Consulte [`documentacao/INTEGRACAO_BACKEND_CSHARP.md`](documentacao/INTEGRACAO_BACKEND_CSHARP.md) para pendências do Backend C#.

## Catálogo agrícola e compatibilidade

A API lista sementes e tipos de solo em /api/v1/agricultura/sementes e /api/v1/agricultura/solos; POST /api/v1/agricultura/analises consulta regras determinísticas e persiste o histórico. Como a carga inicial não possui evidência suficiente para inferir combinações apenas pela classe ampla do solo, pares sem regra retornam DADOS_INSUFICIENTES. Consulte [documentacao/compatibilidade_agricola.md](documentacao/compatibilidade_agricola.md).
