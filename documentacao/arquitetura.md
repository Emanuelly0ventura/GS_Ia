# Arquitetura

A aplicação FastAPI separa saúde, dados predefinidos do mobile, demonstração de anomalias, ingestão IoT, consultas do dashboard e conhecimento/RAG. Configurações e logging ficam em `app/nucleo`; contratos/adaptadores do banco principal permanecem em `app/repositorios`.

O banco principal do aplicativo continua sem mapeamento físico nem escrita pela API. Sua engine read-only em `app/banco/conexao.py` não é reutilizada pela telemetria. O fluxo de demonstração usa `TELEMETRY_DATABASE_URL`, ORM próprio em `app/telemetria` e DDL versionado em `migrations/telemetria`; a API não aplica DDL no startup.

A ingestão persiste um conjunto agrupado de temperatura do ar, umidade do ar e luminosidade ADC, executa modelo Isolation Forest v2 somente após validar os três valores e armazena o resultado com a versão do modelo. BMP180 é complementar. O snapshot mobile é fixo e não lê telemetria.

RAG e geração ficam em módulos independentes e mantêm seus contratos e fontes separados da telemetria.
