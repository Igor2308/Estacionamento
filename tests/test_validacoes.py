from controllers.clientes_controller import cadastrar_cliente
from controllers.enderecos_controller import cadastrar_endereco, atualizar_endereco
from controllers.veiculos_controller import cadastrar_veiculo
from controllers.vagas_controller import cadastrar_vaga, atualizar_status_vaga
from controllers.movimentacoes_controller import registrar_entrada
from controllers.pagamentos_controller import registrar_pagamento


def test_cliente_sem_nome_e_rejeitado_sem_banco():
    resposta, status = cadastrar_cliente({})
    assert status == 400
    assert "nome" in resposta["erro"].lower()


def test_endereco_sem_campos_obrigatorios_e_rejeitado_sem_banco():
    resposta, status = cadastrar_endereco({"id_cliente": 1})
    assert status == 400
    assert "logradouro" in resposta["erro"].lower()


def test_endereco_rejeita_estado_com_sigla_invalida_sem_banco():
    resposta, status = atualizar_endereco(1, {"estado": "São Paulo"})
    assert status == 400
    assert "2 letras" in resposta["erro"]


def test_veiculo_sem_placa_e_rejeitado_sem_banco():
    resposta, status = cadastrar_veiculo({"id_cliente": 1})
    assert status == 400
    assert "placa" in resposta["erro"].lower()


def test_vaga_sem_codigo_e_rejeitada_sem_banco():
    resposta, status = cadastrar_vaga({})
    assert status == 400
    assert "código" in resposta["erro"].lower()


def test_status_vaga_exige_booleano():
    resposta, status = atualizar_status_vaga(1, "sim")
    assert status == 400
    assert "verdadeiro ou falso" in resposta["erro"]


def test_entrada_sem_placa_e_rejeitada_sem_banco():
    resposta, status = registrar_entrada({})
    assert status == 400
    assert "placa" in resposta["erro"].lower()


def test_pagamento_rejeita_tipo_invalido_sem_banco():
    resposta, status = registrar_pagamento({"tipo_pagamento": "INVALIDO"})
    assert status == 400
    assert "tipo de pagamento" in resposta["erro"].lower()
