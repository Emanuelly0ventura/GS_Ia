# Arquitetura

A aplicação FastAPI separa saúde, dados predefinidos do mobile, demonstração de anomalias, ingestão IoT, consultas do dashboard e conhecimento/RAG. Configurações e logging ficam em `app/nucleo`; o banco local próprio da IA usa `app/telemetria`. Os contratos em `app/repositorios` são históricos e não são carregados pelas rotas.

O PostgreSQL da IA é configurado por `TELEMETRY_DATABASE_URL` e pode ser iniciado localmente por Docker Compose. O ORM está em `app/telemetria`; o schema é criado somente pelas migrations versionadas em `migrations/telemetria`, executadas manualmente. O health check consulta esse banco e não depende de conexão ao banco principal do AgroConnect. Consulte `documentacao/postgresql_local.md` para iniciar, migrar e testar o banco.

A ingestão persiste um conjunto agrupado de temperatura do ar, umidade do ar e luminosidade ADC, executa modelo Isolation Forest v2 somente após validar os três valores e armazena o resultado com a versão do modelo. BMP180 é complementar. O snapshot mobile é fixo e não lê telemetria.

RAG e geração ficam em módulos independentes e mantêm seus contratos e fontes separados da telemetria.
