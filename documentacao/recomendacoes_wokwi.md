# Recomendações por captura

O endpoint `POST /api/v1/recomendacoes` recebe `deviceId`, `observationId` e `cultura`. A API localiza a captura no PostgreSQL e valida a procedência, a qualidade, as unidades e a conversão demonstrativa do DHT22. O catálogo `base_conhecimento/recomendacoes.json` recupera itens cujas condições correspondem aos indicadores da captura e à cultura.

O adaptador Gemini organiza os itens recuperados e cita as referências pelos índices do catálogo. O resultado preserva os indicadores, a origem, a curadoria e as ressalvas de cada item. A especificação dos campos pode ser consultada no [Swagger local](http://127.0.0.1:8000/docs) enquanto a API estiver rodando na porta 8000.

O formulário principal do dashboard usa a [análise agrícola unificada](analise_agricola.md). A seleção da captura é automática nesse formulário e a recuperação técnica usa `base_conhecimento/documentos_agricolas.json`.

## Do pedido à orientação

1. `solicitar_recomendacoes()` recebe os IDs e a cultura. `obter_contexto()` busca a observação no PostgreSQL e valida a captura para que as condições do catálogo sejam comparadas com valores e unidades conhecidos. [Rota](../app/rotas/recomendacoes.py)
2. `recuperar()` combina a cultura e os indicadores com as condições de `recomendacoes.json`. A seleção mantém os itens aplicáveis e os motivos de exclusão, que permitem explicar por que uma orientação ficou de fora. [Recuperação](../app/inteligencia_artificial/recomendacoes/recuperacao.py) · [Catálogo](../base_conhecimento/recomendacoes.json)
3. `orquestrar()` devolve `SEM_EVIDENCIA_SUFICIENTE` quando a seleção está vazia. Quando há itens, passa os candidatos ao adaptador Gemini para compor as orientações. A validação vincula a resposta ao catálogo. Se a geração falhar ou o conteúdo for inválido, o retorno sinaliza o estado e pode incluir os itens recuperados. A rota devolve o resultado estruturado ao consumidor HTTP. [Orquestração](../app/inteligencia_artificial/recomendacoes/orquestracao.py) · [Adaptador](../app/inteligencia_artificial/recomendacoes/gerador_gemini.py)
