# AgroConnect AI

API independente do AgroConnect para análise de contexto agrícola e geração futura de recomendações. Esta entrega cobre a **Fase 1**: estrutura, configuração, health checks e preparação das integrações. Ainda não consulta dados de negócio nem implementa Machine Learning, RAG ou geração de recomendações.

## Requisitos

- Python 3.12 ou superior, preferencialmente 64 bits. Foi encontrado Python 3.13.7 de 32 bits nesta máquina e Python 3.11.9; ambos são instalações globais e não foram alteradas.
- Docker para executar a imagem preparada para publicação no Render.

### Ambiente local isolado no Windows

Nesta máquina há Python 3.13.7 de 32 bits e Python 3.11.9 de 64 bits; não há Python 3.12+ de 64 bits. Nenhuma instalação global foi modificada. Instale Python 3.12 ou superior pelo instalador oficial Windows x86-64, escolhendo instalação somente para o usuário atual e sem marcar instalação para todos os usuários. Alternativamente, use `uv` para obter uma versão gerenciada por usuário. Depois confirme com `py -0p`.

Para não remover nem substituir o ambiente atual antes de validar o novo, crie um ambiente paralelo:

```powershell
py -3.12-64 -m venv .venv-312-x64
.\.venv-312-x64\Scripts\python.exe -m pip install --upgrade pip
.\.venv-312-x64\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-312-x64\Scripts\python.exe -m pytest -q
```

Após confirmar os testes, use esse ambiente como o ambiente de desenvolvimento 64-bit. O ambiente `.venv` existente foi criado com Python 3.13 de 32 bits e permanece preservado. Em uma máquina que já tenha Python 3.12+ x64, crie diretamente `.venv` com `py -3.12-64 -m venv .venv`.

As dependências foram resolvidas em modo `pip --dry-run` para CPython 3.12 x64/Windows. Para conectar localmente ao PostgreSQL com psycopg puro, instale `libpq` compatível; a imagem Docker Linux instala `psycopg[binary]`.

## Executar

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.principal:app --reload
```

- Health: <http://127.0.0.1:8000/health>
- Prontidão: <http://127.0.0.1:8000/health/ready>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

`/health/ready` retorna 503 até que um PostgreSQL configurado esteja acessível. A ausência de `DATABASE_URL` não impede a inicialização da API.

## PostgreSQL compartilhado

A conexão está preparada para PostgreSQL via SQLAlchemy 2 e psycopg 3. A engine força transações padrão read-only por parâmetro de conexão. **Isso é uma proteção adicional, não substitui permissões do banco**: em integração, configure um usuário PostgreSQL que possua apenas `CONNECT` e `SELECT` nas estruturas compartilhadas necessárias. Não coloque uma URL com credenciais reais no repositório.

Não foram definidos nomes de tabelas ou colunas, nem criados bancos, tabelas, entidades paralelas ou migrations. `app/repositorios/contratos.py` define interfaces canônicas e `adaptadores.py` é um ponto provisório de extensão. O mapeamento físico será feito somente após confirmação do contrato do Backend C#.

## Configuração

Copie `.env.example` para `.env`. Variáveis nesta fase:

- `AMBIENTE`: nome do ambiente.
- `NIVEL_LOG`: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`.
- `NOME_APLICACAO`: nome exibido nos health checks.
- `DATABASE_URL`: URL PostgreSQL com usuário de somente leitura; opcional para inicialização.
- `PROVEDOR_IA`, `PROVEDOR_IA_MODELO`, `PROVEDOR_IA_URL`, `PROVEDOR_IA_API_KEY`: pontos de configuração reservados para uma integração futura; nenhum provedor é chamado nesta fase e o segredo deve ser definido somente no ambiente.

## Testes

```powershell
pytest -q
```

## Docker e Render

A imagem usa Python 3.12 slim e inicia Uvicorn na porta `PORT` fornecida pelo Render (com fallback local 8000):

```powershell
docker build -t agroconnect-ai .
docker run --rm -p 8000:8000 -e PORT=8000 agroconnect-ai
```

Configure variáveis e credenciais no painel do serviço, nunca na imagem ou no Git. Não há migrações no startup.

## Próximas integrações (fora desta etapa)

- Confirmar schema, unidades, qualidade e relações de acesso com o Backend C#.
- Implementar os repositórios concretos e autorização após o contrato de banco estar disponível.
- Interface abstrata do provedor generativo já preparada; implementação e chamadas continuam pendentes de aprovação.
- Manter o RAG em módulo independente do banco compartilhado, com documentos e referências rastreáveis.
- Adicionar Machine Learning, RAG e IA generativa somente nas fases aprovadas.


Consulte [`documentacao/INTEGRACAO_BACKEND_CSHARP.md`](documentacao/INTEGRACAO_BACKEND_CSHARP.md) para o checklist e as informações pendentes do Backend C#.
