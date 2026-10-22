"""Busca da tarifa aplicável, usada por saída (horista) e pagamento (mensalidade)."""
from datetime import timedelta

from utils.validators import ROTULO_TIPO

MSG_SEM_TARIFA = "Não existe nenhuma tarifa cadastrada. Cadastre uma na tela Tarifas."


def msg_sem_tarifa(tipo_veiculo):
    """Mensagem de erro quando não há tarifa para o tipo de veículo."""
    rotulo = ROTULO_TIPO.get(tipo_veiculo, tipo_veiculo)
    return f"Não existe tarifa cadastrada para o tipo de veículo '{rotulo}'. Cadastre uma na tela Tarifas."


def buscar_tarifa(cursor, tipo_veiculo="CARRO", data=None):
    """Retorna a tarifa (dict) do tipo de veículo aplicável à data (padrão: hoje) ou None se não houver.

    Ordem de escolha (sempre dentro do mesmo tipo de veículo):
      1. a tarifa vigente na data;
      2. senão, a mais recente que já tinha começado (ex.: a vigência acabou e ninguém cadastrou a nova);
      3. senão, a mais antiga cadastrada (ex.: a data é anterior à primeira tarifa).
    Assim a saída e o pagamento nunca ficam travados enquanto existir ao menos uma tarifa daquele tipo.
    O cursor deve ser do tipo dictionary=True.
    """
    if data is None:
        cursor.execute("SELECT CURRENT_DATE AS hoje")
        data = cursor.fetchone()["hoje"]

    cursor.execute("""
        SELECT * FROM configuracoes_tarifas
        WHERE tipo_veiculo = %s
          AND vigencia_inicio <= %s AND (vigencia_fim IS NULL OR vigencia_fim >= %s)
        ORDER BY vigencia_inicio DESC LIMIT 1
    """, (tipo_veiculo, data, data))
    tarifa = cursor.fetchone()
    if tarifa:
        return tarifa

    cursor.execute("""
        SELECT * FROM configuracoes_tarifas
        WHERE tipo_veiculo = %s AND vigencia_inicio <= %s
        ORDER BY vigencia_inicio DESC LIMIT 1
    """, (tipo_veiculo, data))
    tarifa = cursor.fetchone()
    if tarifa:
        return tarifa

    cursor.execute("""
        SELECT * FROM configuracoes_tarifas
        WHERE tipo_veiculo = %s ORDER BY vigencia_inicio ASC LIMIT 1
    """, (tipo_veiculo,))
    return cursor.fetchone()


def recalcular_vigencias(cursor, tipo_veiculo):
    """Reorganiza o fim de vigência das tarifas de um tipo de veículo.

    Cada tarifa vale até o dia anterior ao início da próxima (do mesmo tipo); a última fica em aberto.
    Assim, cadastrar uma tarifa "no meio" (antes de outra que já está agendada) encerra a nova
    no dia anterior à agendada, e nunca sobram datas de fim erradas. O cursor deve ser dictionary=True.
    """
    cursor.execute("""
        SELECT id_tarifa, vigencia_inicio FROM configuracoes_tarifas
        WHERE tipo_veiculo = %s ORDER BY vigencia_inicio, id_tarifa
    """, (tipo_veiculo,))
    tarifas = cursor.fetchall()
    for i, tarifa in enumerate(tarifas):
        fim = tarifas[i + 1]["vigencia_inicio"] - timedelta(days=1) if i + 1 < len(tarifas) else None
        cursor.execute("UPDATE configuracoes_tarifas SET vigencia_fim = %s WHERE id_tarifa = %s",
                       (fim, tarifa["id_tarifa"]))
