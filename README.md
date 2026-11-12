# AgroConnect AI

API de demonstração do AgroConnect. O projeto contém Isolation Forest com três variáveis, RAG/geração configurável e um fluxo IoT separado para telemetria da demonstração. O snapshot mobile predefinido não depende do simulador. O banco principal continua isolado; a telemetria usa PostgreSQL próprio. A base documental começa vazia; não há fontes oficiais, pesos de embeddings ou credenciais incluídos.

## Requisitos

- Python x64 3.12 ou 3.13, Docker Linux amd64 e `uv` 0.13.7.
- `uv.lock` fixa dependências e hashes para Windows/Linux. O índice CPU oficial está associado somente ao pacote PyTorch; `torch==2.15.0+cpu` exclui build CUDA.

Os ambientes anteriores são preservados. A Fase 4 usa `intfloat/multilingual-e5-small`, revisão fixa e prefixos `query: ` e `passage: `. Os pesos locais ficam fora do Git e do contexto/imagem Docker; injete-os em runtime se necessário. O lock instala `psycopg[binary]`.

### Instalação reproduzível no Windows

Instale `uv==0.13.7` com o método aprovado pela equipe. Para criar um ambiente novo sem tocar nos ambientes anteriores:

```powershell
py -3.13 -m venv .venv-fase4
.\.venv-fase4\Scripts\Activate.ps1
python -m pip install uv==0.13.7
$env:UV_PROJECT_ENVIRONMENT = ".venv-fase4"
uv sync --locked --python .\.venv-fase4\Scripts\python.exe
```

`pyproject.toml` declara as dependências diretas e o índice PyTorch CPU; `uv.lock` contém a resolução transitiva multiplataforma. `requirements.txt` espelha os pins diretos para consulta. Use `uv sync --locked` para instalar; não use `pip install -r requirements.txt` para escolher a origem do PyTorch.

## Executar

```powershell
.\.venv-fase4\Scripts\Activate.ps1
uvicorn app.principal:app --reload
```

- Health: <http://127.0.0.1:8000/health>
- Prontidão: <http://127.0.0.1:8000/health/ready>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>
- Estado do RAG: <http://127.0.0.1:8000/api/v1/conhecimento/status>

`/health/ready` retorna 503 até que um PostgreSQL configurado esteja acessível. A ausência de `DATABASE_URL` não impede a inicialização da API.

## PostgreSQL compartilhado

A conexão está preparada para PostgreSQL via SQLAlchemy 2 e psycopg 3. A engine força transações padrão read-only por parâmetro de conexão. **Isso é uma proteção adicional, não substitui permissões do banco**: em integração, configure um usuário PostgreSQL que possua apenas `CONNECT` e `SELECT` nas estruturas compartilhadas necessárias. Não coloque uma URL com credenciais reais no repositório.

Para o banco principal, não foram definidos nomes físicos nem criadas tabelas/migrations; `app/repositorios/contratos.py` define interfaces canônicas e `adaptadores.py` é um ponto provisório até confirmação do contrato do Backend C#. A telemetria da demonstração tem conexão e schema separados, descritos em `migrations/telemetria/001_create_schema.sql`; aplique essa migration manualmente somente no banco de demonstração.

## Configuração

Copie `.env.example` para `.env`. Variáveis nesta fase:

- `AMBIENTE`: nome do ambiente.
- `NIVEL_LOG`: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`.
- `NOME_APLICACAO`: nome exibido nos health checks.
- `DATABASE_URL`: URL PostgreSQL principal com usuário de somente leitura; opcional para inicialização. `TELEMETRY_DATABASE_URL`: conexão independente do PostgreSQL exclusivo da demonstração IoT. `TELEMETRY_DEVICE_TIMEOUT_SECONDS`: prazo para derivar o status de conexão do ESP32.
- `PROVEDOR_IA`, `PROVEDOR_IA_MODELO`, `PROVEDOR_IA_URL`, `PROVEDOR_IA_API_KEY`: configuração opcional do provedor compatível com Chat Completions; nenhum segredo deve ser salvo no repositório. As variáveis `RAG_*` configuram caminhos locais, chunking, revisão do modelo, limiar de busca, limites de ingestão e a chave de API da rota generativa. Sem documentos, pesos, índice ou credenciais, o endpoint informa configuração incompleta.
- Limites HTTP/contexto/resposta: `API_LIMITE_CORPO_HTTP_BYTES=65536`, `API_JSON_PROFUNDIDADE_MAXIMA=32`, `RAG_ORCAMENTO_CONTEXTO_BYTES=100000`, `PROVEDOR_IA_LIMITE_TOKENS_RESPOSTA=2048`, `PROVEDOR_IA_CAMPO_LIMITE_TOKENS=max_completion_tokens` e `PROVEDOR_IA_LIMITE_RESPOSTA_BYTES=1000000`. O corpo acima do teto retorna 413 antes de materializar o JSON; contexto excedido retorna 413 sem truncar fontes; resposta do provedor é limitada por bytes e lida em streaming.
- Limites padrão da ingestão local: 5.000.000 bytes por documento, 100 documentos, 50.000.000 bytes no total, 65.536 bytes por sidecar e 20.000 trechos por reconstrução.

`POST /api/v1/analises/agronomicas` usa `X-API-Key` quando `RAG_ANALISE_CHAVE_API` está configurada (mínimo de 32 caracteres: 401 sem chave e 403 inválida). Sem chave, a rota fica fechada por padrão (503); para demonstração local, configure `AMBIENTE=desenvolvimento` e `RAG_ANALISE_PERMITIR_SEM_CHAVE_LOCAL=true`. Em qualquer ambiente, o limite padrão é 30 requisições por 60 segundos por IP. Para exposição pública, mantenha a exceção local falsa e configure `AMBIENTE=producao` e uma chave secreta. O rate limit fica em memória por processo e não substitui autenticação do usuário via Backend .NET.

## Testes

```powershell
.\.venv-fase4\Scripts\python.exe -m pytest -q
```

## Docker e Render

A imagem usa Python 3.12 slim, instala pelo `uv.lock` com `uv sync --locked` e inicia Uvicorn na porta `PORT` (com fallback local 8000). `.dockerignore` exclui ambientes, temporários, pesos e índice local, sem excluir fontes documentais:

```powershell
docker build -t agroconnect-ai .
.\.venv-fase4\Scripts\python.exe scripts\treinar_modelo.py
$env:TELEMETRY_DATABASE_URL = "postgresql+psycopg://usuario:senha@host.docker.internal:5432/agroconnect_demo"
docker run --rm -p 8000:8000 -e PORT=8000 -e TELEMETRY_DATABASE_URL=$env:TELEMETRY_DATABASE_URL -v "${PWD}/modelos_treinados:/app/modelos_treinados:ro" agroconnect-ai
```

Os pesos do modelo E5 não vêm na imagem; sem modelo, documentos, índice e credenciais, o status RAG permanece incompleto, sem resposta simulada.

Configure variáveis e credenciais no painel do serviço, nunca na imagem ou no Git. Monte/injete o artefato v2 treinado em runtime; ele é ignorado pelo Git. A migration da telemetria continua manual e não roda no startup.

## Próximas integrações (fora desta etapa)

- Confirmar schema, unidades, qualidade e relações de acesso com o Backend C#.
- Implementar os repositórios concretos e autorização após o contrato de banco estar disponível.
- A Fase 4 depende de documentos técnicos revisados, pesos locais e credenciais de provedor; veja `documentacao/fase4_rag.md`.
- Validação Linux anterior às últimas proteções: Python 3.12.16, uv 0.13.7, `uv sync --locked --all-groups` e `pytest -q`: **80 passed em 5,69 s**. Após esta implementação, a suíte completa passou com **108 testes** no ambiente existente `.venv-f4-clean-uv` (que inclui FAISS, necessário pelos testes do RAG). A versão atual ainda não foi testada integralmente em Linux. A Fase 4 não está pronta para produção: faltam documentos agronômicos oficiais licenciados/revisados para ingestão, credenciais e teste real do provedor, integração de identidade com o Backend .NET e rate limit compartilhado entre workers. O status não atesta fontes oficiais automaticamente. Build/execução Docker e endpoints dentro da imagem também não foram validados nesta rodada.


Consulte [`documentacao/INTEGRACAO_BACKEND_CSHARP.md`](documentacao/INTEGRACAO_BACKEND_CSHARP.md) para o checklist e as informações pendentes do Backend C#.

## Acesso a dados e integração pendente

Os contratos lógicos e o adaptador de consultas estão em `app/repositorios/`. O adaptador só aceita `SELECT` configurado externamente, usa parâmetros vinculados e falha quando não há mapeamento. Nenhuma consulta de negócio é carregada por padrão; o schema do Backend C# precisa ser aprovado antes de configurar consultas reais. Fixtures simuladas ficam exclusivamente em `tests/fixtures/` e não são carregadas pela API. Consulte `documentacao/INTEGRACAO_BACKEND_CSHARP.md` e `documentacao/acesso_dados_fase2.md`.

## Machine Learning (demonstração)

O modelo é treinado manualmente por script, não no startup nem em requisições:

```powershell
.\.venv-313-x64\Scripts\python.exe scripts\treinar_modelo.py
.\.venv-313-x64\Scripts\python.exe scripts\avaliar_modelo.py
```

O endpoint `POST /api/v1/anomalias/analisar-demo` é exclusivo de desenvolvimento/teste e aceita apenas dados `SIMULADO_TESTE`. A implementação, o contrato e as limitações estão em [`documentacao/aprendizado_maquina.md`](documentacao/aprendizado_maquina.md). O escore não é probabilidade nem diagnóstico agronômico.

## IoT e dashboard

Consulte [`documentacao/telemetria_iot.md`](documentacao/telemetria_iot.md) para aplicar manualmente o schema isolado, configurar Node-RED, treinar o modelo v2 e usar os endpoints. O dashboard web é servido em `/dashboard`; mobile de demonstração predefinido em `GET /api/v1/mobile/demo/snapshot`. O endpoint de ingestão aceita conjuntos completos e agrupados em `POST /api/v1/iot/readings`; as consultas do painel ficam em `/api/v1/dashboard/readings` e `/api/v1/dashboard/status`. Nenhuma migration é aplicada no startup.
