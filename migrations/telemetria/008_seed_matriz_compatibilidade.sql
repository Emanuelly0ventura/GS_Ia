-- Completa a matriz demonstrativa de 5 culturas por 5 classes de solo.
-- Duas combinações de milho vêm da migration 007.
WITH fontes(cultura, url) AS (
    VALUES
    ('ALFACE', 'https://biblioteca.incaper.es.gov.br/digital/bitstream/item/4194/1/CulturaDaAlface-Cap3.pdf'),
    ('TOMATE', 'https://www.atermaisdigital.cnptia.embrapa.br/web/tomate-de-mesa/preparo-do-solo-e-plantio'),
    ('MILHO', 'https://www.embrapa.br/en/web/agencia-de-informacao-tecnologica/cultivos/milho/pre-producao/caracteristicas-da-especie-e-relacoes-com-o-ambiente/relacoes-com-o-solo'),
    ('FEIJAO', 'https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/254606/1/CPAOCIR.TEC.1790.pdf'),
    ('CENOURA', 'https://ainfo.cnptia.embrapa.br/digital/bitstream/item/227451/1/sistema-producao-cenoura-8out20211.pdf')
), matriz(id, cultura, tipo_solo, resultado, criterio, justificativa) AS (
    VALUES
    ('b83c0800-82a6-4800-8600-000000000001', 'ALFACE', 'ARENOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Retenção adequada de água na camada superficial.', 'Confirme a disponibilidade de água no perfil arenoso e a fertilidade antes de enquadrar a combinação.'),
    ('b83c0800-82a6-4800-8600-000000000002', 'ALFACE', 'ARGILOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Boa drenagem e aeração. O encharcamento é desfavorável.', 'A classe argilosa não informa se o canteiro é bem drenado ou permanece saturado.'),
    ('b83c0800-82a6-4800-8600-000000000003', 'ALFACE', 'SILTOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Estrutura que mantenha a aeração e a infiltração.', 'Verifique se há crosta superficial ou drenagem deficiente no canteiro siltoso.'),
    ('b83c0800-82a6-4800-8600-000000000004', 'ALFACE', 'HUMOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Solo fértil, bem drenado e com estrutura adequada.', 'O rótulo humoso não determina a textura, a drenagem nem a fertilidade medida.'),
    ('b83c0800-82a6-4800-8600-000000000005', 'ALFACE', 'FRANCO', 'COMPATIVEL', 'Demonstração: Textura média e boa drenagem favorecem o crescimento da alface.', 'O solo franco é favorável no cenário didático, se o canteiro estiver bem drenado e fértil.'),
    ('b83c0800-82a6-4800-8600-000000000006', 'TOMATE', 'ARENOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Drenagem fácil e disponibilidade de água e nutrientes.', 'O solo arenoso pode drenar bem, mas é preciso confirmar a retenção de água e a fertilidade.'),
    ('b83c0800-82a6-4800-8600-000000000007', 'TOMATE', 'ARGILOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Boa estrutura física e drenagem na zona radicular.', 'O teor de argila sozinho não permite saber se haverá compactação ou saturação.'),
    ('b83c0800-82a6-4800-8600-000000000008', 'TOMATE', 'SILTOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Permeabilidade e aeração na região das raízes.', 'A classe siltosa não assegura a estrutura e a drenagem de que o tomateiro precisa.'),
    ('b83c0800-82a6-4800-8600-000000000009', 'TOMATE', 'HUMOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Matéria orgânica, baixa acidez e drenagem fácil.', 'O rótulo humoso só sugere presença de matéria orgânica. Faltam dados de pH, fertilidade e drenagem.'),
    ('b83c0800-82a6-4800-8600-000000000010', 'TOMATE', 'FRANCO', 'COMPATIVEL', 'Demonstração: Textura equilibrada, boa estrutura e drenagem fácil.', 'Franco é favorável no cenário didático quando a boa drenagem e a fertilidade são confirmadas.'),
    ('b83c0800-82a6-4800-8600-000000000011', 'MILHO', 'SILTOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Retenção de água e nutrientes associada à textura e à estrutura.', 'O rótulo siltoso não confirma a proporção de argila nem a capacidade de água disponível.'),
    ('b83c0800-82a6-4800-8600-000000000012', 'MILHO', 'HUMOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Boa retenção de água e nutrientes, com drenagem adequada.', 'O teor aparente de matéria orgânica não informa a textura, a profundidade nem a drenagem do perfil.'),
    ('b83c0800-82a6-4800-8600-000000000013', 'MILHO', 'FRANCO', 'COMPATIVEL', 'Demonstração: Textura média com retenção de água e nutrientes e boa drenagem.', 'A textura franca é uma aproximação didática. Confirme o teor de argila e a estrutura do perfil.'),
    ('b83c0800-82a6-4800-8600-000000000014', 'FEIJAO', 'ARENOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Aeração com água disponível e profundidade efetiva.', 'A classe arenosa não informa se haverá água disponível suficiente durante o ciclo do feijoeiro.'),
    ('b83c0800-82a6-4800-8600-000000000015', 'FEIJAO', 'ARGILOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Drenagem e estrutura suficientes para o crescimento das raízes.', 'A classe argilosa admite solos com estruturas distintas. Verifique a compactação e o encharcamento.'),
    ('b83c0800-82a6-4800-8600-000000000016', 'FEIJAO', 'SILTOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Textura média e boa profundidade efetiva.', 'O rótulo siltoso não confirma que o perfil seja um barro limoso de textura média nem que seja bem drenado.'),
    ('b83c0800-82a6-4800-8600-000000000017', 'FEIJAO', 'HUMOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Propriedades físicas e químicas adequadas ao sistema radicular.', 'A matéria orgânica por si só não informa a profundidade efetiva, a aeração ou a fertilidade.'),
    ('b83c0800-82a6-4800-8600-000000000018', 'FEIJAO', 'FRANCO', 'COMPATIVEL', 'Demonstração: Textura média e profundidade efetiva favoráveis ao feijoeiro.', 'Franco é favorável no cenário didático quando o perfil apresenta profundidade suficiente e boa drenagem.'),
    ('b83c0800-82a6-4800-8600-000000000019', 'CENOURA', 'ARENOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Solo profundo, solto e bem drenado, com água e nutrientes disponíveis.', 'A textura arenosa pode favorecer a conformação da raiz, mas é preciso confirmar retenção, profundidade e fertilidade.'),
    ('b83c0800-82a6-4800-8600-000000000020', 'CENOURA', 'ARGILOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Estrutura solta e drenagem na profundidade de formação da raiz.', 'Solos pesados ou compactados podem deformar as raízes. O rótulo argiloso não confirma essas condições.'),
    ('b83c0800-82a6-4800-8600-000000000021', 'CENOURA', 'SILTOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Estrutura sem crosta e profundidade para o crescimento da raiz.', 'O teor de silte sozinho não informa a permeabilidade nem se há impedimentos físicos no perfil.'),
    ('b83c0800-82a6-4800-8600-000000000022', 'CENOURA', 'HUMOSO', 'DADOS_INSUFICIENTES', 'Demonstração: Matéria orgânica, textura média, profundidade e drenagem.', 'O rótulo humoso não comprova a textura nem que o perfil seja profundo e bem drenado.'),
    ('b83c0800-82a6-4800-8600-000000000023', 'CENOURA', 'FRANCO', 'COMPATIVEL', 'Demonstração: Textura média, profundidade e boa drenagem favorecem a cultura.', 'Franco é favorável no cenário didático se houver estrutura solta, profundidade e fertilidade adequadas.')
)
INSERT INTO compatibilidades (
    id, semente_id, solo_id, resultado, criterios, justificativa, referencia_fonte
)
SELECT matriz.id::uuid, semente.id, solo.id, matriz.resultado,
       jsonb_build_array(matriz.criterio), matriz.justificativa, fontes.url
FROM matriz
JOIN fontes USING (cultura)
JOIN tipos_semente AS semente ON semente.codigo = matriz.cultura
JOIN tipos_solo AS solo ON solo.codigo = matriz.tipo_solo
ON CONFLICT (semente_id, solo_id) DO NOTHING;
