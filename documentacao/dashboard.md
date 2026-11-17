# Dashboard operacional

O dashboard é uma página HTML/CSS/JavaScript sem framework, servida por `GET /dashboard` no mesmo FastAPI. Não conecta diretamente ao PostgreSQL e não precisa de build, pacote Node ou biblioteca de gráficos. A identificação textual provisória usa “AC”; o repositório não fornece uma logo AgroConnect para exibir.

## Executar

1. Configure o PostgreSQL local e aplique as migrations, incluindo 006.
2. Inicie a API na raiz do projeto:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn app.principal:app --reload
   ```

3. Acesse `http://127.0.0.1:8000/dashboard`.

O painel usa a mesma origem por padrão. `DASHBOARD_API_BASE_URL` permite definir outra origem HTTP(S), sem caminho ou credenciais. Configure a variável no processo da API; não há chave Gemini nem URL de banco no HTML. Uma hospedagem em origem diferente precisa permitir CORS no servidor API.

## Dados consultados

- `/health` e `/health/ready`: status da API e prontidão PostgreSQL.
- `/api/v1/dashboard/status`: conexão recente dos dispositivos.
- `/api/v1/dashboard/readings?limit=50`: últimas capturas e análises ML persistidas, com limite.
- `/api/v1/agricultura/sementes` e `/api/v1/agricultura/solos`: opções ativas do catálogo.
- `/api/v1/agricultura/analises?limit=10`: histórico recente de compatibilidade.
- `POST /api/v1/agricultura/analises`: solicita uma nova análise determinística usando IDs selecionados.

O histórico agrícola é paginado por limite (`1` a `100`, padrão `20`). A consulta de telemetria já existente aceita limite (`1` a `1000`); o painel pede no máximo 50. Nenhum acesso é feito diretamente ao banco.

## Apresentação e comportamento

O painel apresenta os quatro indicadores canônicos e trata `umidadeSolo` como demonstrativa. O gráfico SVG não depende de pacote externo e normaliza cada série visualmente, preservando unidades nos rótulos. Dados vazios permanecem como traços ou mensagens explícitas; não há valores de demonstração inventados.

Classificação e score do Isolation Forest são mostrados separadamente da explicação Gemini e da justificativa do modelo. O score não é apresentado como probabilidade. A compatibilidade é decidida exclusivamente pelas regras cadastradas; `DADOS_INSUFICIENTES` é explicado como ausência de informação suficiente. Critérios, justificativa, fonte e texto Gemini são exibidos somente quando a API os retorna.

O painel consulta os dados ao abrir e atualiza leituras e históricos a cada 15 segundos. Carrega catálogos uma vez por abertura e só envia uma análise agrícola quando a pessoa submete o formulário. Erros de rede ou API são indicados no painel, sem preencher dados fictícios.
