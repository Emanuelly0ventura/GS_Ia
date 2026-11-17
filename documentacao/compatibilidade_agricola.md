# Catálogo agrícola e compatibilidade determinística

## Catálogo

A migration `005_seed_catalogos_agricolas.sql` cadastra cinco sementes e cinco classes de solo com UUIDs e códigos estáveis. A carga usa `ON CONFLICT (codigo) DO NOTHING`: uma reexecução não duplica itens nem restaura nome ou situação alterados por administração. Os cadastros podem ser desativados sem exclusão física.

## Regras e evidência

Uma regra ativa relaciona uma semente e um tipo de solo, guarda o resultado, critérios, justificativa e URL da fonte. A regra é única por par. Resultados aceitos: `COMPATIVEL`, `INCOMPATIVEL` e `DADOS_INSUFICIENTES`.

A carga inicial **não cria regras de compatibilidade**. As fontes agronômicas consultadas condicionam a avaliação a propriedades que o catálogo atual não recebe, como drenagem, estrutura, retenção hídrica, pH e fertilidade. A classe ampla de solo, por si só, não demonstra essas propriedades. Por isso, uma combinação sem regra ativa gera `DADOS_INSUFICIENTES`, critérios vazios e justificativa/fonte nulas; a API não inventa uma conclusão.

Referências técnicas consultadas:

- Embrapa, [Relações do milho com o solo](https://www.embrapa.br/en/web/agencia-de-informacao-tecnologica/cultivos/milho/pre-producao/caracteristicas-da-especie-e-relacoes-com-o-ambiente/relacoes-com-o-solo): relaciona textura a retenção de água/nutrientes e destaca drenagem/estrutura.
- Embrapa, [Solos para feijão](https://www.atermaisdigital.cnptia.embrapa.br/web/feijao/solos): exige considerar fertilidade e evitar encharcamento; recomenda análise do solo.
- Embrapa, [Informações gerais de tomate de mesa](https://www.atermaisdigital.cnptia.embrapa.br/web/tomate-de-mesa/gerais): condiciona o uso dos solos às condições físicas e retenção de umidade.

Essas referências fundamentam a decisão de não inferir uma regra binária usando apenas os dois códigos do catálogo. Não representam uma validação de recomendação para uma propriedade específica.

## Rotas

- `GET /api/v1/agricultura/sementes`: catálogo de sementes ativas.
- `GET /api/v1/agricultura/solos`: catálogo de solos ativos.
- `POST /api/v1/agricultura/analises`: recebe `{ "sementeId": "<UUID>", "soloId": "<UUID>" }`, consulta os registros e a regra ativa, grava o histórico e retorna o resultado determinístico.

Semente/solo inexistente retorna `404`; registro inativo retorna `409`; JSON ou UUID inválido retorna `422`; indisponibilidade do banco retorna `503`. O Swagger documenta as rotas em `/docs`.

Exemplo sem regra cadastrada (IDs ilustrativos):

```json
{
  "sementeId": "5a2212bb-aabc-52a3-8fe4-baf6485e7f12",
  "soloId": "57467907-fc4a-509e-b02e-0d0213d2c62c"
}
```

Resposta: `201 Created`, com `resultado: "DADOS_INSUFICIENTES"`, `criterios: []`, `justificativa: null` e `referenciaFonte: null`. Cada tentativa válida é registrada em `analises_compatibilidade`, incluindo snapshots dos nomes/códigos e o instante da análise.

Depois de gravar o resultado determinístico, a API pode chamar o serviço de explicação Gemini se houver uma regra ativa com critérios. A explicação é complementar: não escolhe nem altera resultado, critérios ou justificativa. Sem regra/critério não há chamada e `estadoExplicacao` é `SEM_CRITERIOS`. Sem chave configurada o estado é `NAO_CONFIGURADO`; erros de timeout, limite, indisponibilidade ou resposta inválida resultam em `FALHA`, mantendo a análise determinística. `explicacaoGemini`, `estadoExplicacao` e `codigoErroExplicacao` são também persistidos no registro. Testes usam mocks e não fazem chamadas pagas.
