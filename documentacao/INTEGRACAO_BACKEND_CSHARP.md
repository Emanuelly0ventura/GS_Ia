# Integração com o Backend C# — informações pendentes

Este documento registra o que precisa ser confirmado antes de implementar repositórios ou autenticação. Os nomes abaixo são **conceitos lógicos**, não nomes de tabelas, colunas ou claims. A API não cria nem altera estruturas do banco compartilhado.

## 1. PostgreSQL

Solicitar ao grupo responsável: ambiente e versão do PostgreSQL; host/porta/nome do banco e exigências TLS; schemas/views que poderão ser consultados; processo seguro de entrega de segredo; usuário de serviço com `CONNECT` e `SELECT` mínimos; limites de conexões/timeouts; se haverá réplica de leitura; e política para mudanças de schema. Não incluir credenciais neste repositório.

## 2. Estruturas e relacionamentos

Receber o diagrama ou contrato oficial contendo nomes e finalidade das tabelas/views para usuário/permissões, propriedade rural, talhão, plantio, cultura, variedade/semente, solo e parâmetros agronômicos, dispositivo, sensor, leituras e eventos. Para cada estrutura, confirmar colunas, chaves primárias/estrangeiras, nulabilidade, cardinalidade, filtros de exclusão lógica e regras de retenção. A API usará adaptadores para mapear essas estruturas aos contratos canônicos em `app/repositorios/contratos.py`.

Relacionamentos lógicos a confirmar: usuário → permissões/propriedade; propriedade → talhões; talhão → plantio(s); plantio → cultura, semente/variedade e solo; talhão/estufa → dispositivo(s); dispositivo → sensor(es); sensor → leituras; dispositivo/sensor → eventos de estado e qualidade. Confirmar se essas relações são diretas, temporais ou mediadas por outras entidades.

## 3. Tipos e identificadores

Confirmar tipo, formato, escopo e estabilidade dos identificadores de usuário, propriedade, talhão, plantio, cultura, semente, solo, dispositivo e sensor. O contrato inicial de solicitação usa UUID para `idTalhao` e `idDispositivo`; confirmar se isso corresponde às chaves externas oficiais. Distinguir chave interna de código legível do dispositivo (por exemplo, um código impresso), e documentar conversões necessárias. Confirmar fuso horário e precisão dos timestamps.

## 4. Unidades e calibração

Para as leituras de demonstração, confirmar unidade, escala, faixa física, precisão, calibração e significado de ausente para temperatura do ar (DHT22), umidade do ar (DHT22), luminosidade bruta do LDR e complementos BMP180. O modelo usa somente as três primeiras variáveis; `fields.soil_type` é atributo cadastral do terreno, não sensor. Informar a versão e a fonte dos parâmetros agronômicos por cultura, variedade, solo cadastral e fase de desenvolvimento.

## 5. Qualidade e validade de leituras

Definir códigos e significado de qualidade, sensor inválido, offline, valor ausente, valor fora de faixa, duplicidade, atraso, relógio incorreto e leitura corrigida. Informar qual timestamp é de captura e qual é de ingestão, tolerância de atraso, regra de idempotência e se leituras inválidas permanecem consultáveis. Confirmar como identificar origem real versus simulada.

## 6. Dispositivos e sensores

Fornecer o contrato de dispositivo e sensor: identificador interno, código externo, vínculo com talhão/estufa/propriedade, tipo de sensor, grandeza medida, unidade, calibração, status, período de validade e associação temporal. Informar se o estado de conectividade é derivado ou mantido pelo Backend/simulador e qual evento o representa.

## 7. JWT emitido pelo Backend C#

Confirmar algoritmo e tipo de assinatura; material/chave pública ou endpoint JWKS e rotação; `issuer`; `audience` esperado pela API de IA; validação de expiração e, se aplicável, início de validade; claim que identifica o usuário; formato e nomes oficiais de claims de permissões/escopos; regras para tokens revogados; tolerância de relógio; e política de resposta para token inválido. Nenhum algoritmo, valor, claim ou chave foi fixado nesta implementação.

## 8. Contrato Mobile ↔ Backend C# ↔ API de IA

A proposta atual do projeto é o Mobile chamar `POST /api/v1/recomendacoes` com o JWT do Backend e `idTalhao`/`idDispositivo`; a API consulta dados autorizados no PostgreSQL e retorna uma recomendação estruturada. Confirmar se o Mobile chamará a API de IA diretamente ou se o Backend C# fará proxy; URL/ambiente e timeout; contrato final de entrada/saída; nomes e formatos JSON oficiais; política de erros; versionamento; e se haverá histórico de recomendações mantido por algum serviço. O endpoint ainda não está implementado.

## 9. Autorização do usuário ao talhão e dispositivo

Definir a fonte de verdade da autorização, como a API associa o `sub`/identificador validado à pessoa/conta interna, quais vínculos concedem acesso e se o dispositivo precisa pertencer ao talhão solicitado. Confirmar regras para acesso delegado, permissões temporárias, revogação, isolamento entre propriedades e diferença de resposta entre recurso inexistente e não autorizado. A checagem precisa acontecer antes de qualquer consulta generativa futura.

## 10. Dúvidas para o grupo

- [ ] Disponibilizar diagrama/schema oficial ou views de leitura aprovadas.
- [ ] Confirmar identificadores e tipos, incluindo compatibilidade dos UUIDs da requisição.
- [ ] Confirmar relações e cardinalidades entre usuário, propriedade, talhão, plantio e dispositivo.
- [ ] Definir a conta de banco somente leitura, rede/TLS, timeouts e limites.
- [ ] Entregar unidades, calibrações, parâmetros agronômicos e fontes.
- [ ] Definir códigos de qualidade, dados atrasados, duplicados, inválidos e simulados.
- [ ] Disponibilizar contrato de dispositivos/sensores e estados/eventos.
- [ ] Definir algoritmo, issuer, audience, chave/JWKS, claims e rotação do JWT.
- [ ] Confirmar identidade do usuário no token e regra de autorização ao talhão/dispositivo.
- [ ] Confirmar chamada direta pelo Mobile ou proxy do Backend C#.
- [ ] Aprovar contrato JSON, erros, timeouts e versionamento do endpoint.
- [ ] Definir política de retenção/histórico das recomendações e responsabilidade do serviço.
- [ ] Fornecer ambiente de homologação e dados de teste autorizados, sem usar produção nos testes.

## Checklist de integração

- [ ] Contrato/schema revisado pelo Backend C#.
- [ ] Mapeamento lógico-físico aprovado e versionado.
- [ ] Acesso de leitura validado em ambiente de homologação.
- [ ] Consultas limitadas e autorização por usuário verificadas.
- [ ] Contrato JWT validado com tokens de homologação.
- [ ] Unidades, qualidade e origem dos dados verificadas.
- [ ] Contrato Mobile/API aprovado pela equipe Mobile e Backend.
- [ ] Testes de integração isolados do banco de produção.
