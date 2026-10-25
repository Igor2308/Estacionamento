"""Ocupação das vagas de mensalistas: cada vaga vinculada comporta UM veículo do cliente por vez.

A conta é por cliente e por tipo de veículo: um cliente com 2 vagas de carro pode ter 2 carros dentro,
mas um terceiro carro (ou uma moto, se ele não tem vaga de moto) é barrado na entrada.
"""


def vagas_do_cliente(cursor, id_cliente, tipo_veiculo, ignorar_vaga=None):
    """Quantidade de vagas mensalistas ativas do cliente para o tipo de veículo (cursor dictionary=True)."""
    sql = ("SELECT COUNT(*) AS n FROM vagas WHERE id_cliente = %s AND tipo_vaga = 'MENSALISTA' "
           "AND ativa = TRUE AND tipo_veiculo = %s")
    params = [id_cliente, tipo_veiculo]
    if ignorar_vaga:
        sql += " AND id_vaga <> %s"
        params.append(ignorar_vaga)
    cursor.execute(sql, tuple(params))
    return cursor.fetchone()["n"]


def veiculos_dentro(cursor, id_cliente, tipo_veiculo):
    """Devolve (quantidade, placas) dos veículos do cliente, desse tipo, que estão no estacionamento."""
    cursor.execute("""
        SELECT COUNT(*) AS n, GROUP_CONCAT(m.placa_registrada ORDER BY m.entrada_em SEPARATOR ', ') AS placas
        FROM movimentacoes m
        JOIN veiculos ve ON ve.id_veiculo = m.id_veiculo
        WHERE m.id_cliente = %s AND m.saida_em IS NULL AND ve.tipo_veiculo = %s
    """, (id_cliente, tipo_veiculo))
    linha = cursor.fetchone()
    return linha["n"], linha["placas"]


def mensagem_se_faltar_vaga(cursor, id_cliente, tipo_veiculo, id_vaga_removida):
    """Se tirar a vaga deixaria veículo do cliente sem lugar, devolve o aviso; senão None."""
    restantes = vagas_do_cliente(cursor, id_cliente, tipo_veiculo, ignorar_vaga=id_vaga_removida)
    dentro, placas = veiculos_dentro(cursor, id_cliente, tipo_veiculo)
    if dentro > restantes:
        return (f"O veículo {placas} deste cliente está no estacionamento. "
                "Registre a saída dele em Entradas e saídas antes de tirar a vaga.")
    return None
