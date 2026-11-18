-- Enquadramentos acadêmicos para a demonstração. Preserva qualquer regra cadastrada.
INSERT INTO compatibilidades (id, semente_id, solo_id, resultado, criterios, justificativa, referencia_fonte)
SELECT demo.id::uuid, semente.id, solo.id, demo.resultado, demo.criterios::jsonb,
       demo.justificativa, 'https://www.embrapa.br/en/web/agencia-de-informacao-tecnologica/cultivos/milho/pre-producao/caracteristicas-da-especie-e-relacoes-com-o-ambiente/relacoes-com-o-solo'
FROM (VALUES
    ('b30d05d2-4c34-4e11-a882-fdb6fc6904aa', 'ARENOSO', 'INCOMPATIVEL',
     '["Demonstração: baixa retenção de água e nutrientes em solos arenosos."]',
     'Enquadramento acadêmico baseado na textura típica. Depende de confirmação das condições locais.'),
    ('760b52eb-f156-49d9-97b5-ca9ce5e89eb0', 'ARGILOSO', 'COMPATIVEL',
     '["Demonstração: solos argilosos podem ser adequados quando têm boa estrutura e drenagem."]',
     'Compatibilidade acadêmica condicionada a estrutura e drenagem adequadas, não aferidas pelo simulador.')
) AS demo(id, codigo, resultado, criterios, justificativa)
JOIN tipos_solo AS solo ON solo.codigo = demo.codigo
JOIN tipos_semente AS semente ON semente.codigo = 'MILHO'
ON CONFLICT (semente_id, solo_id) DO NOTHING;
