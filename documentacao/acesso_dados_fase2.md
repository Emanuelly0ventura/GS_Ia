# Acesso a dados — preparação da Fase 2

Os contratos lógicos estão em `app/repositorios/contratos.py`. `AdaptadorPostgreSQLConfiguravel` aceita somente consultas `SELECT` configuradas externamente, usa parâmetros nomeados do SQLAlchemy e não contém tabelas, colunas ou schemas padrão. Uma operação sem query mapeada falha explicitamente; não há consultas habilitadas na inicialização da API.

O engine deve ser criado por `criar_engine_leitura()` e a conta do PostgreSQL deve ter permissões mínimas de leitura. O parâmetro de transação read-only é defesa adicional, não substitui privilégios do servidor. As consultas ainda precisam ser produzidas e revisadas com o Backend C#; as saídas devem usar aliases canônicos, incluindo `acesso_permitido` booleano na consulta de autorização.

As fixtures em `tests/fixtures/` e o dublê em `tests/suporte/` existem exclusivamente para testes. Todos os arquivos declaram `SIMULADO_TESTE`; a aplicação não os carrega e eles não representam o schema físico.

## Bloqueios para consultas reais

Faltam schema/view de leitura homologado, tipos e formato dos identificadores, relações, aliases canônicos, semântica de autorização, unidades, códigos de qualidade e acesso de homologação. Até receber esses dados, não há consultas de produção nem validação de relacionamento real.
