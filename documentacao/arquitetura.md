# Arquitetura inicial

A aplicação FastAPI expõe rotas HTTP e health checks. Configurações e logging ficam em `nucleo`; a conectividade PostgreSQL fica isolada em `banco`; contratos de acesso a dados e adaptadores provisórios ficam em `repositorios`.

Nesta fase não há consultas de negócio nem inferência. O PostgreSQL compartilhado será acessado futuramente apenas por repositórios de consulta, com credencial `SELECT` e engine configurada para transações read-only. O schema físico é desconhecido e não é presumido.

A integração generativa e a base documental RAG serão módulos independentes, não acoplados ao schema compartilhado.
