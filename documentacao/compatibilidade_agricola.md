# Catálogo agrícola e compatibilidade determinística

A migration 005 cadastra cinco culturas e cinco classes de solo com IDs estáveis. As migrations 007 e 008 completam as **25 combinações**. Cada regra registra resultado, critério, justificativa e URL técnica da Embrapa ou do Incaper. A chave única é o par cultura–solo. As cargas inserem somente pares novos e preservam os registros existentes.

| Cultura | Arenoso | Argiloso | Siltoso | Humoso | Franco |
| --- | --- | --- | --- | --- | --- |
| Alface | Desconhecido | Desconhecido | Desconhecido | Desconhecido | Compatível |
| Tomate | Desconhecido | Desconhecido | Desconhecido | Desconhecido | Compatível |
| Milho | Incompatível | Compatível | Desconhecido | Desconhecido | Compatível |
| Feijão | Desconhecido | Desconhecido | Desconhecido | Desconhecido | Compatível |
| Cenoura | Desconhecido | Desconhecido | Desconhecido | Desconhecido | Compatível |

**Compatível** indica um cenário favorável condicionado ao critério cadastrado. **Incompatível** indica uma combinação desfavorável no enquadramento didático. **Desconhecido** corresponde a `DADOS_INSUFICIENTES` na API. A interface destaca o motivo, como a necessidade de confirmar drenagem, estrutura ou fertilidade. A justificativa de cada par e sua fonte são exibidas no cartão de compatibilidade.

## Justificativa e bibliografia por combinação

As fontes técnicas descrevem condições de cultivo, como disponibilidade de água, estrutura, drenagem e fertilidade. A matriz do AgroConnect aplica essas condições aos pares do catálogo como regras demonstrativas. **Desconhecido** sinaliza uma condição que precisa de confirmação com dados do terreno. Por exemplo, selecionar solo arenoso para alface informa a classe do solo, enquanto a água disponível e a fertilidade do canteiro precisam ser avaliadas à parte. A bibliografia da tabela é a cadastrada para cada cultura. O par alface e solo arenoso também inclui uma referência complementar sobre avaliação da fertilidade.

| Cultura | Solo | Resultado | Justificativa | Bibliografia |
| --- | --- | --- | --- | --- |
| Alface | Arenoso | Desconhecido | A retenção de água é relevante para a cultura. É preciso confirmar a água disponível e a fertilidade do canteiro. | [Incaper · Cultura da alface][alface] e [Incaper · Fertilidade da alface][fertilidade] |
| Alface | Argiloso | Desconhecido | A classe argilosa, por si só, deixa em aberto a drenagem e o risco de encharcamento. | [Incaper · Cultura da alface][alface] |
| Alface | Siltoso | Desconhecido | É preciso verificar se há crosta superficial e se a estrutura permite infiltração e aeração. | [Incaper · Cultura da alface][alface] |
| Alface | Humoso | Desconhecido | A presença de matéria orgânica deixa em aberto a textura, a drenagem e a fertilidade medida. | [Incaper · Cultura da alface][alface] |
| Alface | Franco | Compatível | A textura média é favorável no cenário didático, desde que o canteiro seja bem drenado e fértil. | [Incaper · Cultura da alface][alface] |
| Tomate | Arenoso | Desconhecido | Mesmo com drenagem fácil, é preciso confirmar a retenção de água e a fertilidade. | [Embrapa · Tomate de mesa][tomate] |
| Tomate | Argiloso | Desconhecido | A classe argilosa deixa em aberto a compactação e a drenagem na região das raízes. | [Embrapa · Tomate de mesa][tomate] |
| Tomate | Siltoso | Desconhecido | É preciso confirmar a permeabilidade e a aeração na região das raízes. | [Embrapa · Tomate de mesa][tomate] |
| Tomate | Humoso | Desconhecido | O teor aparente de matéria orgânica deixa em aberto o pH, a fertilidade e a drenagem. | [Embrapa · Tomate de mesa][tomate] |
| Tomate | Franco | Compatível | A textura equilibrada é favorável no cenário didático, com boa estrutura, drenagem e fertilidade. | [Embrapa · Tomate de mesa][tomate] |
| Milho | Arenoso | Incompatível | A baixa retenção típica de água e nutrientes motiva o enquadramento desfavorável no cenário didático. As condições locais precisam de confirmação. | [Embrapa · Milho e solo][milho] |
| Milho | Argiloso | Compatível | A textura argilosa pode ser adequada no cenário didático se o solo tiver boa estrutura e drenagem. | [Embrapa · Milho e solo][milho] |
| Milho | Siltoso | Desconhecido | É preciso conhecer a proporção de argila e a capacidade de água disponível no perfil. | [Embrapa · Milho e solo][milho] |
| Milho | Humoso | Desconhecido | A matéria orgânica aparente deixa em aberto a textura, a profundidade e a drenagem. | [Embrapa · Milho e solo][milho] |
| Milho | Franco | Compatível | A textura média favorece o cenário didático com retenção de água e nutrientes e boa drenagem. A estrutura e o teor de argila precisam de confirmação. | [Embrapa · Milho e solo][milho] |
| Feijão | Arenoso | Desconhecido | É preciso confirmar se o perfil terá água disponível durante o ciclo e profundidade para as raízes. | [Embrapa · Feijoeiro][feijao] |
| Feijão | Argiloso | Desconhecido | É preciso verificar a compactação, a drenagem e o risco de encharcamento. | [Embrapa · Feijoeiro][feijao] |
| Feijão | Siltoso | Desconhecido | A classe siltosa deixa em aberto a textura média, a profundidade efetiva e a drenagem. | [Embrapa · Feijoeiro][feijao] |
| Feijão | Humoso | Desconhecido | É preciso confirmar a profundidade efetiva, a aeração e a fertilidade. | [Embrapa · Feijoeiro][feijao] |
| Feijão | Franco | Compatível | A textura média é favorável no cenário didático com profundidade efetiva e boa drenagem. | [Embrapa · Feijoeiro][feijao] |
| Cenoura | Arenoso | Desconhecido | A textura pode favorecer o formato da raiz, mas é preciso confirmar a retenção de água, a profundidade e a fertilidade. | [Embrapa · Sistema de produção de cenoura][cenoura] |
| Cenoura | Argiloso | Desconhecido | Solo compactado pode deformar a raiz. É preciso verificar a estrutura e a drenagem na profundidade de formação da raiz. | [Embrapa · Sistema de produção de cenoura][cenoura] |
| Cenoura | Siltoso | Desconhecido | É preciso verificar a permeabilidade, a formação de crosta e possíveis barreiras físicas ao crescimento da raiz. | [Embrapa · Sistema de produção de cenoura][cenoura] |
| Cenoura | Humoso | Desconhecido | A matéria orgânica deixa em aberto a textura, a profundidade e a drenagem do perfil. | [Embrapa · Sistema de produção de cenoura][cenoura] |
| Cenoura | Franco | Compatível | A textura média é favorável no cenário didático com solo solto, profundo, bem drenado e fértil. | [Embrapa · Sistema de produção de cenoura][cenoura] |

[alface]: https://biblioteca.incaper.es.gov.br/digital/handle/item/4194
[fertilidade]: https://biblioteca.incaper.es.gov.br/digital/handle/item/4195
[tomate]: https://www.atermaisdigital.cnptia.embrapa.br/web/tomate-de-mesa/preparo-do-solo-e-plantio
[milho]: https://www.embrapa.br/en/web/agencia-de-informacao-tecnologica/cultivos/milho/pre-producao/caracteristicas-da-especie-e-relacoes-com-o-ambiente/relacoes-com-o-solo
[feijao]: https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/254606/1/CPAOCIR.TEC.1790.pdf
[cenoura]: https://ainfo.cnptia.embrapa.br/digital/bitstream/item/227451/1/sistema-producao-cenoura-8out20211.pdf

Para consultar os critérios de textura, drenagem e retenção de água do milho em PDF, veja também [Cultivo do milho: clima e solo, da Embrapa](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/491176/4/Climasolo.pdf).

## Contratos HTTP

| Método e rota | Operação |
| --- | --- |
| `GET /api/v1/agricultura/sementes` | Lista as culturas ativas. |
| `GET /api/v1/agricultura/solos` | Lista os solos ativos. |
| `POST /api/v1/agricultura/analise-unificada` | Executa a análise usada pelo dashboard e persiste o histórico. |
| `GET /api/v1/agricultura/analises` | Retorna as análises recentes. Aceita `limit` de 1 a 100, com padrão 20. |
| `POST /api/v1/agricultura/analises` | Executa a rota de compatibilidade com o contrato original e registra a análise no mesmo histórico. |

As duas operações POST recebem `sementeId` e `soloId`, extraídos das rotas de catálogo. O histórico guarda uma cópia do resultado, critérios, justificativa e referência usados no momento da análise, além do estado e do texto da explicação. Consulte [o fluxo do dashboard](analise_agricola.md) e o [contrato HTTP da API](contrato_http.md), que descreve as rotas e suas funções. Para consultar e testar as rotas pelo navegador, abra o [Swagger da API local](http://127.0.0.1:8000/docs). O link do Swagger só funciona enquanto a API estiver rodando localmente na porta 8000.

## De onde vem a conclusão agrícola

1. O dashboard usa `listar_sementes()` e `listar_solos()` para obter IDs e nomes ativos. Esses IDs identificam a combinação enviada ao backend. [Rotas do catálogo](../app/compatibilidade/rotas.py)
2. `ServicoAnaliseCompatibilidade` resolve os IDs e procura a regra para o par. Os critérios e a fonte explicam o enquadramento registrado. IDs ausentes ou inativos são tratados pelo serviço. A ausência de regra ativa leva ao estado `DADOS_INSUFICIENTES`. [Serviço](../app/compatibilidade/servicos.py)
3. A rota registra o resultado da consulta, os critérios e a fonte como estavam na hora da análise. Essa cópia permite que o histórico conserve a justificativa usada mesmo que a regra seja editada depois. O texto Gemini, quando disponível, complementa o registro. [Modelos](../app/compatibilidade/modelos.py) · [Fluxo unificado](analise_agricola.md)
