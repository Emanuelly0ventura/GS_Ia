# PostgreSQL local do AgroConnect AI

O FastAPI usa um PostgreSQL dedicado à telemetria e às análises do AgroConnect AI. O Docker Compose mantém os dados no volume `agroconnect_ai_postgres_data`. A API lê a conexão de `TELEMETRY_DATABASE_URL`.

A fábrica de sessões em `app/telemetria/banco.py` usa SQLAlchemy. A ingestão, as consultas do dashboard e o histórico agrícola compartilham essa configuração de banco.

## Tabelas e relações

- `iot_devices`: dispositivo externo único, origem, última comunicação e datas de criação/atualização. Um dispositivo possui várias leituras.
- `iot_readings`: uma captura por dispositivo + `observation_id`; guarda horários medido/recebido, qualidade, origem e objetos JSONB `sensor_values`, `units` e `complements`. Os objetos suportam novos indicadores e metadados; o contrato IoT persiste quatro indicadores e os metadados da conversão demonstrativa de umidade do solo.
- `iot_anomaly_analyses`: resultado único associado a cada leitura, com versão do modelo, classificação, score, data, variáveis e justificativa.
- `analises_compatibilidade`: snapshot da decisão determinística agrícola e, após migration 006, explicação Gemini opcional, estado e código de erro.

Após migration 006, `iot_anomaly_analyses` também contém `generative_explanation`, `generative_status` e `generative_error_code`. Esses campos persistem a explicação separadamente da classificação e do score.

Uma captura tem no máximo uma análise, e as chaves estrangeiras usam exclusão em cascata. O catálogo agrícola usa `tipos_semente`, `tipos_solo`, `compatibilidades` e `analises_compatibilidade`, criadas em migrations próprias sem alterar as tabelas IoT. Regras só devem ser cadastradas com critérios e fonte técnica verificados.

## Configuração no PowerShell

Na raiz do projeto, crie `.env` a partir do exemplo e defina uma senha local:

```powershell
Copy-Item .env.example .env
notepad .env
```

Ajuste `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_PORT`. Configure `TELEMETRY_DATABASE_URL` com os mesmos valores. Mantenha os valores reais no `.env` local, ignorado pelo Git.

## Iniciar e verificar o PostgreSQL

```powershell
docker compose up -d postgres
docker compose ps
docker compose logs --tail 50 postgres
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

O comando `pg_isready` dentro do container confirma o serviço. `docker compose ps` deve mostrar `healthy`. Para executar a API no ambiente Python local, carregue a URL do `.env` no processo (ou use as configurações de ambiente do seu terminal) e rode Uvicorn. O endpoint `GET /health/ready` verifica a conexão com `SELECT 1` e retorna HTTP 200 quando o banco está pronto.

## Aplicar migrations

Aplique as migrations SQL manualmente, em ordem numérica, antes de iniciar a API:

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
foreach ($migration in Get-ChildItem migrations/telemetria/*.sql | Sort-Object Name) {
    Get-Content -Raw -Encoding UTF8 $migration.FullName |
        docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
    if ($LASTEXITCODE -ne 0) { throw "Migration não aplicada: $($migration.Name)" }
}
```

A migration 004 cria as tabelas agrícolas, a 005 insere os catálogos e a 006 acrescenta os campos do Gemini. As migrations 007 e 008 carregam as regras de compatibilidade.

## Testes de integração PostgreSQL

Os testes de `tests/integration/` são separados e usam somente `TEST_TELEMETRY_DATABASE_URL`. Aponte essa variável para um banco descartável cujo nome termine em `_test`, por exemplo `agroconnect_ai_test`, e aplique nele as migrations 001 a 008 antes de executar:

```powershell
$env:TEST_TELEMETRY_DATABASE_URL = 'postgresql+psycopg://agroconnect:senha-local@localhost:5432/agroconnect_ai_test'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest -q
```

A suíte consulta o schema migrado e usa registros temporários para verificar ingestão, catálogo, histórico e persistência. Os testes marcados como integração usam o banco dedicado configurado acima.

## Parar, reiniciar e remover

```powershell
docker compose stop postgres
docker compose start postgres
docker compose down
```

Os três comandos acima preservam o volume `agroconnect_ai_postgres_data`.
