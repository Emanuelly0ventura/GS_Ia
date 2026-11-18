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

## Contratos HTTP

| Método e rota | Operação |
| --- | --- |
| `GET /api/v1/agricultura/sementes` | Lista as culturas ativas. |
| `GET /api/v1/agricultura/solos` | Lista os solos ativos. |
| `POST /api/v1/agricultura/analise-unificada` | Executa a análise usada pelo dashboard e persiste o histórico. |
| `GET /api/v1/agricultura/analises` | Retorna as análises recentes. Aceita `limit` de 1 a 100, com padrão 20. |
| `POST /api/v1/agricultura/analises` | Executa a rota de compatibilidade com o contrato original e registra a análise no mesmo histórico. |

As duas operações POST recebem `sementeId` e `soloId`, extraídos das rotas de catálogo. O histórico guarda uma cópia do resultado, critérios, justificativa e referência usados no momento da análise, além do estado e do texto da explicação. Consulte [o fluxo do dashboard](analise_agricola.md) e [/docs](http://127.0.0.1:8000/docs).
