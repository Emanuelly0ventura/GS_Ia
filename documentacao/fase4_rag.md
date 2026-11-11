# Fase 4 — recuperação de conhecimento agronômico (RAG)

## Estado real da implementação

O repositório agora contém uma pipeline local de ingestão, segmentação, embeddings, índice FAISS, recuperação com limiar, construção de contexto, validação de citações e adaptação HTTP do provedor. A ingestão ocorre somente pelo script local scripts/reconstruir_indice_rag.py; não existe rota pública para enviar ou modificar documentos.

**Não há documentos agronômicos oficiais incluídos neste repositório, nem pesos do modelo de embeddings ou credenciais de um provedor generativo.** A pasta base_conhecimento/documentos/ começa vazia. As fixtures de teste declaram que são sintéticas e não são carregadas pela aplicação. A ausência de qualquer componente retorna estado incompleto/indisponibilidade; não é produzida uma resposta generativa fixa como se viesse de um LLM.

A presença local de um documento ou uma instituição declarada em seus metadados não autentica sua origem nem valida cientificamente seu conteúdo. Antes da ingestão operacional, uma pessoa responsável deve verificar a publicação, a instituição, a versão e a aplicabilidade agronômica.

## Arquitetura

1. ingestao.py lê arquivos locais Markdown ou texto UTF-8 acompanhados de sidecar JSON. Não busca URLs, não executa o texto e não aceita arquivos fora do diretório configurado.
2. segmentacao.py agrupa parágrafos até o limite configurado. Parágrafos longos são divididos por caracteres, com sobreposição configurável. Os offsets são relativos ao texto normalizado ingerido; cada trecho preserva ID, título, instituição, referência, URL, autoria, data, tipo e data de ingestão.
3. SentenceTransformerLocal carrega pesos exclusivamente de uma pasta local, sem download ou código remoto durante requisições. Codifica consulta e documentos em vetores normalizados.
4. IndiceVetorialLocal guarda um índice exato FAISS IndexFlatIP, os trechos JSONL e um manifesto com formato, dimensão, identificador/revisão/fingerprint SHA-256 do modelo, prefixos de consulta/documento e hashes dos arquivos. O formato 2 rejeita índices criados com outra configuração de codificação. O índice pode ser reconstruído dos documentos originais com o script local.
5. RecuperadorSemantico aplica o limiar configurável e devolve metadados, posições e pontuação. A pontuação é similaridade vetorial para ordenação e filtragem; **não comprova relevância científica, validade ou aplicabilidade**. Um trecho acima do limiar ainda precisa de revisão humana.
6. ServicoRAG forma o contexto e chama o protocolo ProvedorGenerativo. A resposta valida que cada ID citado existe entre os trechos recuperados.
7. O status valida manifesto e artefatos disponíveis e só tenta carregar os pesos locais quando existe um índice verificável; o objeto do modelo fica em cache por processo. Sem validar conteúdo científico, índice/modelo incompatível ou provedor real, não declara `PRONTO`.

O Isolation Forest é uma fonte de contexto estatístico independente: sua saída continua significando atipicidade segundo o modelo e não diagnóstico, probabilidade ou confirmação de problema agronômico. O RAG recupera fontes; o modelo generativo redige a explicação. Nenhum deles substitui avaliação agronômica de campo.

## Arquivos e metadados de entrada

Para cada documento, coloque um par:

    base_conhecimento/documentos/
      identificador-publicacao.md
      identificador-publicacao.metadata.json

O sidecar exige identificador, titulo, instituicao e referencia_origem. São opcionais url, autor, data_publicacao (ISO AAAA-MM-DD) e tipo_documento. O conteúdo vem do arquivo .md ou .txt. O ID precisa ser único na base. Não use o domínio example ou dados de fixture para representar uma fonte real.

## Modelo de embeddings e dependências

O modelo selecionado para a validação é `intfloat/multilingual-e5-small`, revisão imutável `fd1525a9fd15316a2d503bf26ab031a61d056e98`, dimensão **384**. O model card informa suporte multilíngue e exige prefixar consultas com `query: ` e passagens/documentos com `passage: `; essa configuração agora é aplicada pelo codificador e gravada no manifesto do índice. [Model card e instruções do E5](https://huggingface.co/intfloat/multilingual-e5-small/tree/fd1525a9fd15316a2d503bf26ab031a61d056e98).

Os pesos não são versionados nem baixados durante requisições. Armazene-os em `modelos_embeddings/multilingual-e5-small` com revisão imutável correspondente. Depois de instalar `sentence-transformers`, obtenha os arquivos explicitamente:

    hf download intfloat/multilingual-e5-small --revision fd1525a9fd15316a2d503bf26ab031a61d056e98 --local-dir modelos_embeddings/multilingual-e5-small

O snapshot validado ocupou aproximadamente 471 MB. O fingerprint SHA-256 calculado para os arquivos carregados foi `c0c2a74e11b3276ab1825364054d932f24a1b2f5dd7a54ee1faf34704ca6dd23`. Para atualizar pesos ou prefixos, fixe a revisão e reconstrua o índice; um manifesto com configuração diferente é rejeitado.

As dependências diretas estão fixadas em `requirements.txt` e `pyproject.toml`; `uv.lock` guarda a resolução transitiva com hashes, marcadores Windows/Linux e faixa Python `>=3.12,<3.14`. O índice oficial `https://download.pytorch.org/whl/cpu` é configurado como fonte explícita exclusivamente para `torch==2.15.0+cpu`; PyPI continua sendo a origem dos demais pacotes. Não há dependências `nvidia-*` nem `triton` no lock. Instale com `uv sync --locked`, não com pip direto, para respeitar a origem CPU por pacote.

A instalação limpa pelo lock também foi validada no Windows Python 3.13.17 x64: PyTorch 2.15.0+cpu reportou `torch.version.cuda is None` e `torch.cuda.is_available() is False`; FAISS 1.15.1 e Sentence Transformers 6.2.0 importaram, e a busca vetorial simples retornou similaridade 1.0 para o vetor idêntico. A suíte Linux descrita abaixo passou integralmente; esse resultado de testes, por si só, não registra a variante de PyTorch nem comprova build ou execução da imagem Docker.

### Recuperação real em português

O script `scripts/validar_embeddings_reais.py` usa os pesos reais acima, o codificador do projeto e um índice FAISS temporário. Em 10/11/2026, com limiar configurado em `0.85`, os resultados foram:

| Consulta | Documento no topo | Score | Retidos pelo limiar |
| --- | --- | ---: | --- |
| Déficit hídrico no milho | Texto sintético de água no milho | 0.9190 | somente o esperado |
| Ferrugem asiática da soja | Texto sintético de ferrugem da soja | 0.9111 | somente o esperado |
| Escalação da seleção brasileira de futebol | Energia fotovoltaica (irrelevante) | 0.7937 | nenhum |

Os quatro textos do ensaio são **fixtures sintéticas**, não documentos técnicos ou fontes científicas. A pontuação de similaridade não prova relevância: scores fora de tema chegaram a 0.7937 e os demais distratores a aproximadamente 0.82. O limiar `0.85` é apenas um valor inicial que separou estas três consultas; ele ainda precisa de calibração com perguntas e documentos revisados da base real. O score não é uma probabilidade ou avaliação de qualidade científica.

## Provedor generativo

ProvedorChatCompletions implementa o protocolo ProvedorGenerativo para endpoints compatíveis com Chat Completions. Requer PROVEDOR_IA=chat_completions ou openai_compatible, modelo, URL HTTPS (HTTP somente em loopback local) e chave no ambiente. Timeout é configurável. Chaves e conteúdo de respostas de erro não são escritos em logs.

O prompt pede português brasileiro, separação entre fatos e interpretações, citações por identificador existente e declaração de insuficiência. Trechos são envolvidos como conteúdo de referência não confiável; instruções dentro deles não devem ser seguidas. Isso reduz risco de prompt injection, mas não é uma garantia formal contra erro/alucinação do provedor.

## Endpoints

- GET /api/v1/conhecimento/status: reporta documentos locais, modelo, dependências, índice e provedor ausentes/configurados. Não declara que uma fonte é oficial.
- POST /api/v1/conhecimento/buscar: aceita {"pergunta": "..."} e retorna trechos rastreáveis; lista vazia significa que nada atingiu o limiar.
- POST /api/v1/analises/agronomicas: recebe pergunta, dados agrícolas explicitamente enviados e, opcionalmente, um resultado de anomalia. Não busca talhões, sensores ou identidades no Backend C#.

Não há rota administrativa ou pública de ingestão. Índice ausente/corrompido, incompatibilidade de modelo, falta de credencial e falha de provedor são apresentados como configuração incompleta/indisponibilidade. Consulta sem correspondência retorna EVIDENCIA_INSUFICIENTE, sem chamar o LLM.

## Limites de entrada, contexto e resposta

Os limites são configuráveis e validados por Pydantic. Os valores atuais preservam os contratos existentes:

| Recurso | Configuração | Padrão |
| --- | --- | ---: |
| Profundidade de arrays/objetos JSON nas rotas POST RAG | `API_JSON_PROFUNDIDADE_MAXIMA` | 32 níveis |
| Corpo HTTP completo | `API_LIMITE_CORPO_HTTP_BYTES` | 65.536 bytes |
| Chave da rota de análise | `RAG_ANALISE_CHAVE_API` | não configurada; rota fechada |
| Exceção local sem chave | `RAG_ANALISE_PERMITIR_SEM_CHAVE_LOCAL` | `false` |
| Limite da rota de análise | `RAG_ANALISE_RATE_LIMIT_REQUISICOES` / `RAG_ANALISE_RATE_LIMIT_JANELA_SEGUNDOS` | 30 por 60 segundos/IP |
| Pergunta | fixo no esquema | 2.000 caracteres |
| Dados agrícolas | fixo no esquema | 40 campos e 20.000 caracteres JSON |
| Segmentação | `RAG_TAMANHO_TRECHO` / `RAG_SOBREPOSICAO_TRECHOS` | 1.200 / 160 caracteres |
| Trechos recuperados | `RAG_LIMITE_TRECHOS` | 5; máximo 20 |
| Orçamento do contexto completo | `RAG_ORCAMENTO_CONTEXTO_BYTES` | 100.000 bytes |
| Tokens da resposta | `PROVEDOR_IA_LIMITE_TOKENS_RESPOSTA` | 2.048 tokens |
| Campo Chat Completions para limite | `PROVEDOR_IA_CAMPO_LIMITE_TOKENS` | `max_completion_tokens` |
| Bytes da resposta HTTP do provedor | `PROVEDOR_IA_LIMITE_RESPOSTA_BYTES` | 1.000.000 bytes |
| Timeout do provedor | `PROVEDOR_IA_TIMEOUT_SEGUNDOS` | 30 segundos |
| Documento de ingestão | `RAG_INGESTAO_LIMITE_DOCUMENTO_BYTES` | 5.000.000 bytes |
| Quantidade de documentos | `RAG_INGESTAO_LIMITE_DOCUMENTOS` | 100 |
| Ingestão total (documentos + sidecars) | `RAG_INGESTAO_LIMITE_TOTAL_BYTES` | 50.000.000 bytes |
| Sidecar de metadados | `RAG_INGESTAO_LIMITE_METADADOS_BYTES` | 65.536 bytes |
| Trechos por reconstrução | `RAG_INGESTAO_LIMITE_TRECHOS` | 20.000 |

A verificação de profundidade ocorre antes da decodificação JSON do FastAPI, ignora delimitadores dentro de strings e retorna HTTP 422 quando excedida. Validações Pydantic existentes também retornam 422.

O orçamento conta o corpo JSON UTF-8 completo enviado ao Chat Completions: instrução de sistema, pergunta, dados, metadados, referências e trechos. O serviço rejeita contexto acima do orçamento e o adaptador revalida o corpo HTTP exato antes de abrir a conexão. Excesso retorna HTTP 413; nenhuma evidência ou referência é truncada ou removida silenciosamente.

O adaptador envia `max_completion_tokens` por padrão. Configure `PROVEDOR_IA_CAMPO_LIMITE_TOKENS=max_tokens` somente para provedores compatíveis que ainda exijam o campo legado. A referência atual do Chat Completions marca `max_tokens` como depreciado e incompatível com alguns modelos; prefira `max_completion_tokens` quando disponível ([referência do contrato Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)).

O limite da resposta é aplicado antecipadamente quando há `Content-Length` e durante a leitura em streaming, incluindo respostas sem esse cabeçalho. O corpo e a credencial não são incluídos nas mensagens de erro.

### Proteção da rota de análise

O contrato `ValidadorToken` do projeto é apenas um protocolo; não há validador JWT nem integração de identidade com o Backend .NET nesta fase. Por isso, a análise aceita uma chave de serviço opcional em `RAG_ANALISE_CHAVE_API`, sempre tratada como segredo e nunca registrada. Quando configurada, o cliente envia `X-API-Key`: ausência retorna 401 e valor incorreto retorna 403, comparado com `hmac.compare_digest`. A chave deve ter pelo menos 32 caracteres. Sem chave, o endpoint fica fechado por padrão em todos os ambientes (503). A exceção local exige simultaneamente ambiente `desenvolvimento`, `development`, `teste`, `test` ou `testing` e `RAG_ANALISE_PERMITIR_SEM_CHAVE_LOCAL=true`. Essa variável deve permanecer falsa em qualquer ambiente exposto.

O rate limit padrão é 30 requisições por IP por janela fixa de 60 segundos; valores configuráveis são `RAG_ANALISE_RATE_LIMIT_REQUISICOES` e `RAG_ANALISE_RATE_LIMIT_JANELA_SEGUNDOS`. O limiter é limitado em cardinalidade e em memória do processo. Com vários workers/instâncias, cada um mantém seu próprio contador; atrás de proxy, o endereço visível pode ser o IP do proxy. Isso não é autenticação por usuário e não substitui a integração de token do Backend .NET.

### Ingestão limitada

`ingerir_diretorio` aplica limites antes de ler o conteúdo completo: no padrão, até 5 MB por documento, 100 documentos, 50 MB combinados (documentos e sidecars) e 64 KB por sidecar. A leitura é limitada a máximo configurado mais um byte, para detectar alterações e arquivos acima do teto. A reconstrução interrompe quando ultrapassa 20.000 trechos (`RAG_INGESTAO_LIMITE_TRECHOS`). Erros de UTF-8, JSON, metadados, symlinks fora da raiz, contagem e tamanho encerram a ingestão sem publicar um índice parcial.

## Fontes oficiais avaliadas (11/11/2026)

Não há conteúdo documental oficial incorporado à base. Foram conferidos registros bibliográficos oficiais da Infoteca-e/Embrapa que são pertinentes a irrigação e cultivo protegido:

| Publicação | Metadados verificados | Acesso/condição declarada |
| --- | --- | --- |
| [Viabilidade e manejo da irrigação da cultura do milho](https://www.infoteca.cnptia.embrapa.br/infoteca/handle/doc/490417) | Camilo de Lelis Teixeira de Andrade, Paulo Emilio Pereira de Albuquerque, R. A. L. Brito e M. Resende; Embrapa Milho e Sorgo, Circular Técnica 85, 2006, 12 páginas. | Registro indica acesso aberto e licença CC BY-NC-ND 4.0. |
| [Cultivo protegido do tomateiro](https://www.infoteca.cnptia.embrapa.br/handle/doc/765429) | Nozomu Makishima e Osmar Alves Carrijo; Embrapa Hortaliças, Circular Técnica 13, 1998, 18 páginas. | Registro indica acesso aberto e licença CC BY-NC-ND 4.0. |

**Data de consulta dos registros: 11/11/2026.** A instituição, os metadados e a licença foram confirmados no repositório Embrapa. Os arquivos não foram copiados para a pasta do projeto nem convertidos para texto/índice: a licença indica ausência de autorização para obras derivadas, e não foi feita análise de direitos que permita extrair e redistribuir o conteúdo em outro formato. A ingestão fica pendente de autorização/licença compatível e revisão técnica do conteúdo. Não se usaram os testes sintéticos como evidência agronômica.

## Reconstrução e execução local

Instale `uv==0.13.7`, crie/ative um ambiente Python x64 3.12 ou 3.13 e execute `uv sync --locked`. O Dockerfile usa o mesmo `uv.lock`. Forneça documentos verificados, pesos locais e revisão imutável; configure as variáveis em `.env` (nunca versione segredos). Os pesos não são copiados para a imagem; `.dockerignore` exclui o diretório local de pesos do contexto do build.

    .\.venv-fase4\Scripts\python.exe scripts\reconstruir_indice_rag.py
    .\.venv-fase4\Scripts\python.exe -m uvicorn app.principal:app --reload

Sem documentos, pesos, índice ou credencial, a API permanece claramente indisponível para análise generativa. Não foram conectados PostgreSQL/Render, Backend C#, Mobile ou serviços de dados reais.

## Testes

Fixtures de embedding/provedor em testes são doubles explícitos e nunca são usados pelo runtime. A suíte verifica ingestão inválida/duplicada, chunking e metadados, recuperação relevante/irrelevante com limiar, índice ausente/corrompido/incompatível, citação inexistente, documento com instrução maliciosa, ausência de evidências e provedor indisponível. A similaridade sintética testa apenas o mecanismo de ranking, não relevância científica.

    .\.venv-fase4\Scripts\python.exe -m pytest -q
    .\.venv-fase4\Scripts\python.exe scripts\validar_embeddings_reais.py

## Limitações

- Sem fontes técnicas validadas, pesos e credencial, ainda não existe uma demonstração end-to-end com evidência científica real.
- A busca é FAISS exata por produto interno de vetores normalizados; o limiar precisa ser calibrado em conjunto de consultas revisado e não equivale a uma probabilidade.
- A validação de citação garante apenas que o ID veio da recuperação; não comprova que a frase é sustentada pelo trecho.
- O manifesto e os hashes detectam inconsistência/corrupção acidental. Um índice local adulterado e acompanhado de manifesto refeito ainda é material não confiável: carregue somente arquivos de diretório controlado.
- O armazenamento local não oferece persistência de produção nem governança editorial. A chave configurável protege a chamada de serviço, não autentica usuários; o rate limit é por processo, não distribuído. Integração de identidade/autorização com o Backend .NET continua pendente.
- A avaliação agronômica depende de cultura, região, solo, estágio e condições reais; recomendações de manejo exigem profissional agrônomo.

## Registro de dependências e testes (11/11/2026)

- uv.lock foi gerado com uv 0.13.7 e abrange requires-python >=3.12,<3.14, marcadores de plataforma e hashes. O índice PyTorch CPU é uma fonte explícita somente para o pacote torch, sem --extra-index-url global.
- A instalação limpa pelo lock no Windows Python 3.13.17 x64 instalou 66 distribuições. PyTorch reportou 2.15.0+cpu, torch.version.cuda=None e torch.cuda.is_available()=False; FAISS reportou 1.15.1, Sentence Transformers 6.2.0, e a busca FAISS de vetor unitário idêntico obteve score 1.0.
- Antes das últimas proteções de corpo HTTP, disponibilidade e autenticação, a suíte integral foi executada em Linux com Python **3.12.16** e uv **0.13.7**, após `uv sync --locked --all-groups`, usando `pytest -q`: **80 passed, 0 failed, em 5,69 s**.
- Após as proteções descritas nesta revisão, a suíte completa atual foi executada no Windows com **Python 3.13.17 x64**: **102 passed, 0 failed, em 2,97 s**. Foram incluídos os testes assíncronos. `python -m compileall -q app scripts tests` também passou. Este resultado não substitui uma execução da revisão atual no Linux.
- O resultado Linux de **80 passed, 0 failed, em 5,69 s** é da revisão anterior, antes das proteções desta revisão; não o apresente como validação do código atual. Nesta sessão, `uv` não estava disponível no PowerShell, o Docker não conseguiu acessar o named pipe do Engine (`permission denied`) e o WSL retornou `Wsl/E_ACCESSDENIED`; por isso não foi possível fazer `uv sync --locked --all-groups`, rodar a suíte atual em Linux nem reconstruir/testar a imagem.
- O resultado Linux anterior não constitui validação agronômica, execução ponta a ponta com fontes oficiais nem teste de uma conta real de provedor generativo.
- Verificação local via ASGI no mesmo ambiente: `/health` 200, `/openapi.json` 200, `/health/ready` 503 sem banco e `/api/v1/conhecimento/status` 200 com `CONFIGURACAO_INCOMPLETA`. Isso valida a aplicação local; não substitui a execução dos mesmos endpoints no container atualizado.
- scripts/validar_embeddings_reais.py passou no ambiente limpo usando os pesos E5 reais já presentes localmente: modelo intfloat/multilingual-e5-small, revisão fd1525a9fd15316a2d503bf26ab031a61d056e98, dimensão 384 e fingerprint c0c2a74e11b3276ab1825364054d932f24a1b2f5dd7a54ee1faf34704ca6dd23. Consultas sintéticas sobre milho e ferrugem da soja recuperaram o fixture esperado (0.9190 e 0.9111); a consulta irrelevante de futebol não reteve trechos no limiar 0.85. Esses resultados não representam fonte científica. Na repetição final, o Windows negou a criação de temporário na raiz do projeto; a validação foi repetida sem alterar o script, redirecionando somente o TemporaryDirectory para uma pasta gravável autorizada.
- A suíte atualizada, o build da imagem, a inicialização de container, a inspeção de PyTorch CPU-only e os endpoints dentro da imagem não foram validados nesta rodada. Nesta sessão, Docker retorna `permission denied` no named pipe `dockerDesktopLinuxEngine` e WSL retorna `Wsl/E_ACCESSDENIED`.
- .dockerignore exclui ambientes, temporários, segredos, pesos locais e índice local. O Dockerfile não copia modelos_embeddings; os pesos E5 continuam fora da imagem.

Para validar separadamente o build e a execução da imagem em um PowerShell com acesso ao Engine:

    docker image inspect agroconnect-ai:fase4 --format '{{.Size}}'
    docker build --progress=plain -t agroconnect-ai:fase4-cpu .
    docker image inspect agroconnect-ai:fase4-cpu --format '{{.Size}}'
    docker run -d --rm --name agroconnect-fase4-cpu -p 8000:8000 agroconnect-ai:fase4-cpu
    Invoke-RestMethod http://localhost:8000/health
    Invoke-RestMethod http://localhost:8000/openapi.json
    Invoke-RestMethod http://localhost:8000/api/v1/conhecimento/status
    (Invoke-WebRequest http://localhost:8000/health/ready -SkipHttpErrorCheck).StatusCode
    docker exec agroconnect-fase4-cpu python -c "import torch,faiss,sentence_transformers; print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),faiss.__version__,sentence_transformers.__version__)"
    docker stop agroconnect-fase4-cpu

A imagem deverá mostrar 2.15.0+cpu, CUDA None e disponibilidade CUDA False. Sem banco, /health/ready deve continuar 503; sem arquivos locais e credenciais, /api/v1/conhecimento/status deve informar configuração incompleta.
