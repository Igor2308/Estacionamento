"""Cobrança de mensalidade por vaga mensalista.

Ao vincular uma vaga a um cliente nasce uma cobrança (valor = mensalidade do tipo de veículo da vaga).
Quando o período acaba, a próxima cobrança é gerada automaticamente (na hora em que as telas consultam).
A vaga só pode ser cancelada/desvinculada se não houver cobrança em aberto.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from services.tarifas_service import buscar_tarifa, msg_sem_tarifa
from utils.auth import usuario_atual


def somar_mes(data, meses=1):
    """Soma meses a uma data (31/01 + 1 mês = 28/02 ou 29/02)."""
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return date(ano, mes, min(data.day, monthrange(ano, mes)[1]))


def fim_do_periodo(inicio):
    """Um período de mensalidade vai do início até a véspera do mesmo dia do mês seguinte."""
    return somar_mes(inicio) - timedelta(days=1)


def criar_cobranca(cursor, vaga, inicio):
    """Cria a cobrança de um período. `vaga` precisa ter id_vaga, id_cliente e tipo_veiculo.

    Retorna (id_cobranca, None) ou (None, mensagem_de_erro). O cursor deve ser dictionary=True.
    """
    tarifa = buscar_tarifa(cursor, vaga["tipo_veiculo"], inicio)
    if not tarifa:
        return None, msg_sem_tarifa(vaga["tipo_veiculo"])

    cursor.execute("""
        INSERT INTO cobrancas_mensalidade
            (id_cliente, id_vaga, tipo_veiculo, competencia_inicio, competencia_fim, valor, cadastrado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (vaga["id_cliente"], vaga["id_vaga"], vaga["tipo_veiculo"], inicio, fim_do_periodo(inicio),
          Decimal(str(tarifa["mensalidade_por_vaga"])), usuario_atual()))
    return cursor.lastrowid, None


def gerar_cobrancas_em_atraso(cursor):
    """Gera as cobranças dos meses que já começaram para toda vaga mensalista vinculada.

    Só estende vagas que já têm cobrança (a primeira nasce ao vincular). Sem commit: quem chama decide.
    """
    cursor.execute("SELECT CURRENT_DATE AS hoje")
    hoje = cursor.fetchone()["hoje"]

    cursor.execute("""
        SELECT v.id_vaga, v.id_cliente, v.tipo_veiculo, MAX(cb.competencia_fim) AS ultimo_fim
        FROM vagas v
        JOIN cobrancas_mensalidade cb
            ON cb.id_vaga = v.id_vaga AND cb.id_cliente = v.id_cliente
        WHERE v.tipo_vaga = 'MENSALISTA' AND v.id_cliente IS NOT NULL
        GROUP BY v.id_vaga, v.id_cliente, v.tipo_veiculo
        HAVING MAX(cb.competencia_fim) < CURRENT_DATE
    """)
    for vaga in cursor.fetchall():
        fim = vaga["ultimo_fim"]
        while fim < hoje:
            inicio = fim + timedelta(days=1)
            _, erro = criar_cobranca(cursor, vaga, inicio)
            if erro:  # sem tarifa para o tipo: não dá para gerar agora
                break
            fim = fim_do_periodo(inicio)


def mensagem_em_aberto(cursor, id_vaga, id_cliente):
    """Se a vaga tem cobrança em aberto, devolve a mensagem de bloqueio; senão None."""
    cursor.execute("""
        SELECT COUNT(*) AS qtd, COALESCE(SUM(valor), 0) AS total
        FROM cobrancas_mensalidade
        WHERE id_vaga = %s AND id_cliente = %s AND status = 'ABERTA'
    """, (id_vaga, id_cliente))
    linha = cursor.fetchone()
    if not linha["qtd"]:
        return None
    total = f"R$ {Decimal(str(linha['total'])):.2f}".replace(".", ",")
    return (f"Essa vaga tem {total} em aberto na tela Pagamentos. "
            "Registre o pagamento antes de cancelar o plano.")
