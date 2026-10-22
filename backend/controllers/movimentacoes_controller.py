
from decimal import Decimal
from math import ceil

from config.database import conectar_banco
from services.mensalidades_service import gerar_cobrancas_em_atraso, mensagem_em_aberto
from services.tarifas_service import buscar_tarifa, msg_sem_tarifa
from utils.auth import usuario_atual
from utils.validators import ROTULO_TIPO, normalizar_placa, validar_placa


def listar_movimentacoes():
    """Lista as movimentações mais recentes."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                m.*,
                c.nome AS nome_cliente,
                c.modalidade,
                v.placa AS placa_cadastrada,
                v.tipo_veiculo
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos v ON v.id_veiculo = m.id_veiculo
            ORDER BY m.entrada_em DESC
        """)
        return {"dados": cursor.fetchall()}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_movimentacoes_abertas():
    """Lista veículos que ainda estão no estacionamento."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                m.*,
                c.nome AS nome_cliente,
                c.modalidade,
                v.tipo_veiculo,
                TIMESTAMPDIFF(SECOND, m.entrada_em, CURRENT_TIMESTAMP) AS segundos_no_patio
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos v ON v.id_veiculo = m.id_veiculo
            WHERE m.saida_em IS NULL
            ORDER BY m.entrada_em
        """)
        return {"dados": cursor.fetchall()}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def registrar_entrada(dados):
    """Registra a entrada (somente de placas cadastradas) e verifica a capacidade disponível."""
    placa = dados.get("placa")

    if not isinstance(placa, str) or not placa.strip():
        return {"erro": "Informe a placa do veículo."}, 400

    placa = normalizar_placa(placa)
    if not validar_placa(placa):
        return {"erro": "Placa inválida. Use o formato ABC1234 ou ABC1D23."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)

        # Entradas passam uma por vez. Sem isso, duas requisições simultâneas
        # podem ultrapassar a capacidade ou causar deadlock no MySQL.
        # O lock é liberado automaticamente quando a conexão é fechada.
        cursor.execute("SELECT GET_LOCK('estacionamento_entrada', 10) AS ok")
        if cursor.fetchone()["ok"] != 1:
            return {"erro": "Sistema ocupado. Tente novamente."}, 503

        # A placa precisa estar cadastrada (cliente + endereço + veículo).
        cursor.execute("""
            SELECT
                v.id_veiculo,
                v.id_cliente,
                v.placa,
                v.tipo_veiculo,
                v.ativo AS veiculo_ativo,
                c.modalidade,
                c.ativo AS cliente_ativo
            FROM veiculos v
            JOIN clientes c ON c.id_cliente = v.id_cliente
            WHERE v.placa = %s
            LIMIT 1
            FOR UPDATE
        """, (placa,))
        veiculo = cursor.fetchone()

        if not veiculo:
            return {
                "erro": "Placa não cadastrada. Cadastre o cliente, o endereço e o "
                        "veículo antes de registrar a entrada."
            }, 404

        if not veiculo["veiculo_ativo"] or not veiculo["cliente_ativo"]:
            return {
                "erro": "O veículo ou seu cliente está inativo."
            }, 400

        id_veiculo = veiculo["id_veiculo"]
        id_cliente = veiculo["id_cliente"]
        modalidade = veiculo["modalidade"]

        # Não permite duas entradas abertas para a mesma placa.
        cursor.execute("""
            SELECT id_movimentacao
            FROM movimentacoes
            WHERE placa_registrada = %s AND saida_em IS NULL
            LIMIT 1
            FOR UPDATE
        """, (placa,))

        if cursor.fetchone():
            return {
                "erro": "Esse veículo já possui uma entrada sem saída registrada."
            }, 409

        # Mensalista usa a vaga como quiser: não registra entrada/saída de cada dia.
        # Encerrar o plano é feito em Entradas e saídas > Saída de mensalistas.
        if modalidade == "MENSALISTA":
            return {
                "erro": "Mensalistas não registram entrada: a vaga é deles para usar como quiserem. "
                        "Para encerrar o plano, use a saída de mensalistas."
            }, 409

        # Horista: só conta as vagas rotativas ativas do MESMO tipo de veículo.
        # FOR UPDATE: entradas simultâneas de horistas passam uma por vez.
        tipo_veiculo = veiculo["tipo_veiculo"]
        cursor.execute("""
            SELECT id_vaga
            FROM vagas
            WHERE tipo_vaga = 'ROTATIVA' AND ativa = TRUE AND tipo_veiculo = %s
            FOR UPDATE
        """, (tipo_veiculo,))
        total_vagas = len(cursor.fetchall())

        cursor.execute("""
            SELECT COUNT(*) AS total_veiculos
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos ve ON ve.id_veiculo = m.id_veiculo
            WHERE m.saida_em IS NULL
              AND (m.id_cliente IS NULL OR c.modalidade = 'HORISTA')
              AND ve.tipo_veiculo = %s
        """, (tipo_veiculo,))
        veiculos_dentro = cursor.fetchone()["total_veiculos"]

        if veiculos_dentro >= total_vagas:
            return {
                "erro": f"Não há vagas rotativas disponíveis para {ROTULO_TIPO.get(tipo_veiculo, tipo_veiculo)}."
            }, 409

        cursor.close()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO movimentacoes (
                id_veiculo,
                id_cliente,
                placa_registrada,
                cadastrado_por,
                atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (id_veiculo, id_cliente, placa, usuario_atual(), usuario_atual()))

        id_movimentacao = cursor.lastrowid
        conexao.commit()

        return {
            "mensagem": "Entrada registrada com sucesso.",
            "id_movimentacao": id_movimentacao,
            "placa": placa,
            "modalidade": modalidade,
        }, 201

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def registrar_saida(id_movimentacao):
    """Registra a saída de um horista e calcula o valor da permanência (tarifa do tipo do veículo)."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                m.*,
                c.modalidade,
                ve.tipo_veiculo
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos ve ON ve.id_veiculo = m.id_veiculo
            WHERE m.id_movimentacao = %s
            FOR UPDATE
        """, (id_movimentacao,))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            return {"erro": "Movimentação não encontrada."}, 404

        if movimentacao["saida_em"] is not None:
            return {"erro": "Essa movimentação já possui saída registrada."}, 409

        # Movimentações antigas sem cliente (de quando aceitava avulso) são cobradas como horista.
        modalidade = movimentacao["modalidade"] or "HORISTA"
        valor_periodo = Decimal("0.00")
        periodos = 0
        valor_total = Decimal("0.00")

        if modalidade == "HORISTA":
            tipo_veiculo = movimentacao["tipo_veiculo"] or "CARRO"  # movimentação antiga, sem veículo
            tarifa = buscar_tarifa(cursor, tipo_veiculo)

            if not tarifa:
                return {"erro": msg_sem_tarifa(tipo_veiculo)}, 409

            valor_periodo = Decimal(str(tarifa["valor_periodo_30_min"]))

            # Conta cada período iniciado de 30 minutos.
            cursor.execute("""
                SELECT TIMESTAMPDIFF(
                    SECOND, entrada_em, CURRENT_TIMESTAMP
                ) AS segundos
                FROM movimentacoes
                WHERE id_movimentacao = %s
            """, (id_movimentacao,))

            segundos = max(0, cursor.fetchone()["segundos"])
            periodos = max(1, ceil(segundos / 1800))
            valor_total = valor_periodo * periodos

        cursor.close()
        cursor = conexao.cursor()

        cursor.execute("""
            UPDATE movimentacoes
            SET
                saida_em = CURRENT_TIMESTAMP,
                valor_periodo_aplicado = %s,
                periodos_cobrados = %s,
                valor_total = %s,
                atualizado_por = %s
            WHERE id_movimentacao = %s AND saida_em IS NULL
        """, (
            valor_periodo,
            periodos,
            valor_total,
            usuario_atual(),
            id_movimentacao,
        ))

        conexao.commit()

        return {
            "mensagem": "Saída registrada com sucesso.",
            "id_movimentacao": id_movimentacao,
            "periodos_cobrados": periodos,
            "valor_periodo_aplicado": str(valor_periodo),
            "valor_total": str(valor_total),
        }, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_mensalistas():
    """Lista as vagas mensalistas vinculadas (uma linha por vaga) com o valor em aberto de cada uma."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        gerar_cobrancas_em_atraso(cursor)
        conexao.commit()

        cursor.execute("""
            SELECT
                v.id_vaga,
                v.codigo,
                v.tipo_veiculo,
                c.id_cliente,
                c.nome,
                (
                    SELECT COALESCE(SUM(cb.valor), 0)
                    FROM cobrancas_mensalidade cb
                    WHERE cb.id_vaga = v.id_vaga
                      AND cb.id_cliente = v.id_cliente
                      AND cb.status = 'ABERTA'
                ) AS valor_em_aberto
            FROM vagas v
            JOIN clientes c ON c.id_cliente = v.id_cliente
            WHERE v.tipo_vaga = 'MENSALISTA' AND c.ativo = TRUE
            ORDER BY c.nome, v.codigo
        """)
        return {"dados": cursor.fetchall()}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def registrar_saida_mensalista(id_vaga):
    """Saída de mensalista = cancelamento do plano de UMA vaga.

    Só é possível se a vaga não tiver mensalidade em aberto. Quando o cliente fica sem nenhuma
    vaga, ele passa a horista (e qualquer movimentação antiga em aberto é encerrada, sem cobrança).
    """
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_vaga, codigo, tipo_vaga, id_cliente
            FROM vagas
            WHERE id_vaga = %s
            FOR UPDATE
        """, (id_vaga,))
        vaga = cursor.fetchone()

        if not vaga:
            return {"erro": "Vaga não encontrada."}, 404

        if vaga["tipo_vaga"] != "MENSALISTA":
            return {"erro": "A vaga informada não é mensalista."}, 400

        id_cliente = vaga["id_cliente"]
        if id_cliente is None:
            return {"erro": "Essa vaga não está vinculada a nenhum mensalista."}, 409

        cursor.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s FOR UPDATE", (id_cliente,))
        cursor.fetchone()

        # Primeiro conta os meses que já começaram; só cancela se nada estiver em aberto.
        gerar_cobrancas_em_atraso(cursor)
        bloqueio = mensagem_em_aberto(cursor, id_vaga, id_cliente)
        if bloqueio:
            conexao.commit()  # mantém as cobranças em atraso que acabaram de ser geradas
            return {"erro": bloqueio}, 409

        cursor.execute("""
            UPDATE vagas
            SET id_cliente = NULL, vinculada_em = NULL, atualizado_por = %s
            WHERE id_vaga = %s
        """, (usuario_atual(), id_vaga))

        cursor.execute("""
            SELECT COUNT(*) AS restantes
            FROM vagas
            WHERE id_cliente = %s AND tipo_vaga = 'MENSALISTA'
        """, (id_cliente,))
        restantes = cursor.fetchone()["restantes"]

        plano_encerrado = restantes == 0
        if plano_encerrado:
            cursor.execute("""
                UPDATE movimentacoes
                SET saida_em = CURRENT_TIMESTAMP,
                    valor_periodo_aplicado = 0,
                    periodos_cobrados = 0,
                    valor_total = 0,
                    atualizado_por = %s
                WHERE id_cliente = %s AND saida_em IS NULL
            """, (usuario_atual(), id_cliente))
            cursor.execute("""
                UPDATE clientes
                SET modalidade = 'HORISTA', atualizado_por = %s
                WHERE id_cliente = %s
            """, (usuario_atual(), id_cliente))

        conexao.commit()

        mensagem = f"Vaga {vaga['codigo']} cancelada."
        if plano_encerrado:
            mensagem += " Era a última vaga do cliente: ele agora é horista."
        return {
            "mensagem": mensagem,
            "id_vaga": id_vaga,
            "id_cliente": id_cliente,
            "plano_encerrado": plano_encerrado,
        }, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
