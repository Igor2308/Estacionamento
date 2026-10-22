from datetime import timedelta
from decimal import Decimal, InvalidOperation

from config.database import conectar_banco
from services.tarifas_service import recalcular_vigencias
from utils.auth import usuario_atual
from utils.validators import TIPOS_VEICULO, validar_data


def listar_tarifas():
    """Lista as tarifas, da mais recente para a mais antiga."""
    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT *, (vigencia_inicio <= CURRENT_DATE
                       AND (vigencia_fim IS NULL OR vigencia_fim >= CURRENT_DATE)) AS vigente
            FROM configuracoes_tarifas
            ORDER BY vigencia_inicio DESC, tipo_veiculo, id_tarifa DESC
        """)
        return {"dados": cursor.fetchall()}, 200
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def _valor(dados, campo):
    try:
        v = Decimal(str(dados.get(campo, "")).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return v if v.is_finite() and v >= 0 else None


def cadastrar_tarifa(dados):
    """Cadastra uma nova tarifa para um tipo de veículo e acerta as vigências das tarifas desse tipo."""
    tipo_veiculo = dados.get("tipo_veiculo")
    if tipo_veiculo not in TIPOS_VEICULO:
        return {"erro": "Selecione o tipo de veículo da tarifa."}, 400

    mensalidade = _valor(dados, "mensalidade_por_vaga")
    periodo = _valor(dados, "valor_periodo_30_min")
    if mensalidade is None or periodo is None:
        return {"erro": "Informe valores válidos (zero ou maior) para a mensalidade e para o período de 30 min."}, 400

    inicio = validar_data(dados.get("vigencia_inicio"))
    if not inicio:
        return {"erro": "Informe a data de início da vigência (AAAA-MM-DD)."}, 400

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("SELECT id_tarifa FROM configuracoes_tarifas WHERE tipo_veiculo = %s AND vigencia_inicio = %s LIMIT 1",
                       (tipo_veiculo, inicio))
        if cursor.fetchone():
            return {"erro": "Já existe uma tarifa desse tipo de veículo começando nessa data."}, 409

        cursor.execute("""
            INSERT INTO configuracoes_tarifas
                (tipo_veiculo, mensalidade_por_vaga, valor_periodo_30_min, vigencia_inicio, cadastrado_por, atualizado_por)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (tipo_veiculo, mensalidade, periodo, inicio, usuario_atual(), usuario_atual()))
        id_tarifa = cursor.lastrowid

        # Acerta os fins de vigência do tipo (a anterior termina na véspera; a nova termina na véspera da próxima agendada).
        recalcular_vigencias(cursor, tipo_veiculo)
        conexao.commit()
        return {"mensagem": "Tarifa cadastrada com sucesso.", "id_tarifa": id_tarifa}, 201
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()
