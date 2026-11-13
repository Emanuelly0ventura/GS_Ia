# PostgreSQL local do AgroConnect AI

O serviço FastAPI usa um PostgreSQL próprio para telemetria e análises. Ele não consulta o PostgreSQL do Backend C#, Render ou Mobile. O container Docker mantém seus dados no volume nomeado `agroconnect_ai_postgres_data`. O health check da API verifica esse banco pela variável `TELEMETRY_DATABASE_URL`; não há conexão obrigatória ao inicializar a aplicação.

## Tabelas e relações

- `iot_devices`: dispositivo externo único, origem, última comunicação e datas de criação/atualização. Um dispositivo possui várias leituras.
- `iot_readings`: uma captura por dispositivo + `observation_id`; guarda horários medido/recebido, qualidade, origem e objetos JSONB `sensor_values`, `units` e `complements`. Os objetos suportam novos indicadores e metadados; a fase atual mantém o contrato de três variáveis.
- `iot_anomaly_analyses`: resultado único associado a cada leitura, com versão do modelo, classificação, score, data, variáveis e justificativa.

Uma captura tem no máximo uma análise, e as chaves estrangeiras usam exclusão em cascata. Os catálogos de sementes, solos e compatibilidade devem ser introduzidos em uma migration futura própria, quando a modelagem e os critérios forem definidos.

## Configuração no PowerShell

Na raiz do projeto, crie `.env` a partir do exemplo e defina uma senha local:

```powershell
Copy-Item .env.example .env
notepad .env
```

Ajuste `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_PORT`. Configure `TELEMETRY_DATABASE_URL` com os mesmos valores. O `.env` é ignorado pelo Git; não coloque credenciais reais em arquivos versionados.

## Iniciar e verificar o PostgreSQL

```powershell
docker compose up -d postgres
docker compose ps
docker compose logs --tail 50 postgres
docker compose exec postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB
```

O comando `pg_isready` dentro do container confirma o serviço. `docker compose ps` deve mostrar `healthy`. Para executar a API no ambiente Python local, carregue a URL do `.env` no processo (ou use as configurações de ambiente do seu terminal) e rode Uvicorn. O endpoint `GET /health/ready` verifica `TELEMETRY_DATABASE_URL` e retorna 200 somente quando o PostgreSQL responde a `SELECT 1`; sem URL/conexão, retorna 503.

## Aplicar migrations

As migrations são SQL versionadas e manuais; o startup não executa DDL nem `create_all()`. No PowerShell, aplique-as nesta ordem:

```powershell
$envFile = Get-Content .env | Where-Object { $_ -match '^POSTGRES_(DB|USER|PASSWORD)=' }
$vars = @{}
foreach ($line in $envFile) { $parts = $line -split '=', 2; $vars[$parts[0]] = $parts[1] }
Get-Content migrations/telemetria/001_create_schema.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $vars.POSTGRES_USER -d $vars.POSTGRES_DB
Get-Content migrations/telemetria/002_device_timestamps.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U $vars.POSTGRES_USER -d $vars.POSTGRES_DB
```

As tabelas agrícolas não fazem parte desta fase. Para mudanças futuras, crie migrations numeradas novas; não altere migrations já aplicadas em ambientes compartilhados.

## Testes de integração PostgreSQL

Os testes de `tests/integration/` são separados e usam somente `TEST_TELEMETRY_DATABASE_URL`. Aponte essa variável para um banco descartável cujo nome termine em `_test`, por exemplo `agroconnect_ai_test`, e aplique nele as duas migrations antes de executar:

```powershell
$env:TEST_TELEMETRY_DATABASE_URL = 'postgresql+psycopg://agroconnect:senha-local@localhost:5432/agroconnect_ai_test'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv-fase4\Scripts\python.exe -m pytest -m integration -q -p no:cacheprovider
```

O teste não cria nem apaga schema; verifica o schema migrado e remove somente o dispositivo único criado para o próprio teste. Sem `TEST_TELEMETRY_DATABASE_URL`, o teste é reportado como ignorado. Não aponte para um banco com dados importantes.

## Parar, reiniciar e remover

```powershell
docker compose stop postgres
docker compose start postgres
docker compose down
```

`stop`, `start` e `down` preservam o volume. Para excluir permanentemente o volume e todos os dados locais, seria necessário `docker compose down -v`; esse comando não faz parte do fluxo normal.
