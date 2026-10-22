-- Tarifas iniciais (opcional), uma para cada tipo de veículo. Depois você pode cadastrar/alterar na tela "Tarifas".
-- Observação: a vigência começa em 2020 para valer também para entradas antigas.
USE banco_estacionamento;
INSERT INTO configuracoes_tarifas (tipo_veiculo, mensalidade_por_vaga, valor_periodo_30_min, vigencia_inicio) VALUES
('CARRO',    300.00, 5.00, '2020-01-01'),
('MOTO',     150.00, 3.00, '2020-01-01'),
('VAN',      400.00, 7.00, '2020-01-01'),
('CAMINHAO', 600.00, 10.00, '2020-01-01'),
('OUTRO',    300.00, 5.00, '2020-01-01');
