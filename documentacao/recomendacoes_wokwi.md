# Recomendações por captura

O endpoint `POST /api/v1/recomendacoes` recebe `deviceId`, `observationId` e `cultura`. A API localiza a captura no PostgreSQL e valida a procedência, a qualidade, as unidades e a conversão demonstrativa do DHT22. O catálogo `base_conhecimento/recomendacoes.json` recupera itens cujas condições correspondem aos indicadores da captura e à cultura.

O adaptador Gemini organiza os itens recuperados e cita as referências pelos índices do catálogo. O resultado preserva os indicadores, a origem, a curadoria e as ressalvas de cada item. A especificação dos campos pode ser consultada no [Swagger](http://127.0.0.1:8000/docs).

O formulário principal do dashboard usa a [análise agrícola unificada](analise_agricola.md). A seleção da captura é automática nesse formulário e a recuperação técnica usa `base_conhecimento/documentos_agricolas.json`.
