
from decimal import Decimal
from math import ceil

from config.database import conectar_banco
from services.mensalidades_service import gerar_cobrancas_em_atraso, mensagem_em_aberto
from services.tarifas_service import buscar_tarifa, msg_sem_tarifa
from utils.auth import usuario_atual
from services.ocupacao_service import mensagem_se_faltar_vaga, vagas_do_cliente, veiculos_dentro
from utils.paginacao import escapar_like, executar_paginado, padrao_busca
from utils.validators import ROTULO_TIPO, normalizar_placa, validar_placa


def _filtro_busca(busca, params):
    """Trecho SQL da busca por placa, nome do cliente ou CPF/CNPJ (acrescenta os parâmetros em `params`)."""
    texto, digitos = padrao_busca(busca)
    if not texto:
        return ""
    placa = f"%{escapar_like(normalizar_placa(busca))}%"
    if digitos:
        params += [placa, texto, digitos, digitos]
        return " AND (m.placa_registrada LIKE %s OR c.nome LIKE %s OR c.cpf LIKE %s OR c.cnpj LIKE %s)"
    params += [placa, texto]
    return " AND (m.placa_registrada LIKE %s OR c.nome LIKE %s)"


def listar_movimentacoes(pagina=None, busca=None, fechadas=False):
    """Lista as movimentações mais recentes (paginado quando `pagina` é informada).

    fechadas: só as que já têm saída (histórico). Mostra quem registrou a entrada e quem registrou a saída.
    """
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT
                m.*,
                c.nome AS nome_cliente,
                c.modalidade,
                v.placa AS placa_cadastrada,
                v.tipo_veiculo,
                ue.nome AS entrada_por_nome,
                us.nome AS saida_por_nome
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos v ON v.id_veiculo = m.id_veiculo
            LEFT JOIN usuarios ue ON ue.id_usuario = m.cadastrado_por
            LEFT JOIN usuarios us ON us.id_usuario = m.atualizado_por
            WHERE 1 = 1
        """
        params = []
        if fechadas:
            sql += " AND m.saida_em IS NOT NULL"
        sql += _filtro_busca(busca, params)
        return executar_paginado(
            cursor, sql, tuple(params), "m.entrada_em DESC, m.id_movimentacao DESC", pagina), 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_movimentacoes_abertas(pagina=None, busca=None, apenas_horistas=False, apenas_mensalistas=False):
    """Lista veículos que ainda estão no estacionamento (paginado quando `pagina` é informada)."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT
                m.*,
                c.nome AS nome_cliente,
                c.modalidade,
                v.tipo_veiculo,
                ue.nome AS entrada_por_nome,
                TIMESTAMPDIFF(SECOND, m.entrada_em, CURRENT_TIMESTAMP) AS segundos_no_patio
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos v ON v.id_veiculo = m.id_veiculo
            LEFT JOIN usuarios ue ON ue.id_usuario = m.cadastrado_por
            WHERE m.saida_em IS NULL
        """
        params = []
        if apenas_horistas:
            sql += " AND (c.modalidade IS NULL OR c.modalidade <> 'MENSALISTA')"
        if apenas_mensalistas:
            sql += " AND c.modalidade = 'MENSALISTA'"
        sql += _filtro_busca(busca, params)
        return executar_paginado(cursor, sql, tuple(params), "m.entrada_em, m.id_movimentacao", pagina), 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def _gravar_entrada(conexao, cursor, id_veiculo, id_cliente, placa, modalidade):
    """Grava a entrada já validada (o cursor dictionary é fechado aqui e substituído por um comum)."""
    cursor.close()
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO movimentacoes (id_veiculo, id_cliente, placa_registrada, cadastrado_por, atualizado_por)
        VALUES (%s, %s, %s, %s, %s)
    """, (id_veiculo, id_cliente, placa, usuario_atual(), usuario_atual()))
    id_movimentacao = cursor.lastrowid
    conexao.commit()
    cursor.close()
    return {
        "mensagem": "Entrada registrada com sucesso.",
        "id_movimentacao": id_movimentacao,
        "placa": placa,
        "modalidade": modalidade,
    }, 201


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

        # Mensalista: precisa ter vaga vinculada para o tipo do veículo, e cada vaga comporta
        # um veículo dele por vez. Não usa as vagas rotativas e não gera cobrança por entrada.
        if modalidade == "MENSALISTA":
            tipo = veiculo["tipo_veiculo"]
            rotulo = ROTULO_TIPO.get(tipo, tipo)
            vagas = vagas_do_cliente(cursor, id_cliente, tipo)
            if vagas == 0:
                cursor.execute("""
                    SELECT COUNT(*) AS n FROM vagas
                    WHERE id_cliente = %s AND tipo_vaga = 'MENSALISTA' AND ativa = TRUE
                """, (id_cliente,))
                if cursor.fetchone()["n"] == 0:
                    return {"erro": "Esse mensalista não tem vaga vinculada. Vincule uma vaga "
                                    "(tela Vagas) antes de registrar a entrada."}, 409
                return {"erro": f"Esse mensalista não tem vaga vinculada para {rotulo}. "
                                "As vagas dele são de outro tipo de veículo."}, 409
            dentro, placas = veiculos_dentro(cursor, id_cliente, tipo)
            if dentro >= vagas:
                return {"erro": f"Todas as {vagas} vaga(s) de {rotulo} deste cliente já estão em uso "
                                f"({placas}). Registre a saída de um veículo antes de entrar com outro."}, 409
            return _gravar_entrada(conexao, cursor, id_veiculo, id_cliente, placa, modalidade)

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
        qtd_horistas_dentro = cursor.fetchone()["total_veiculos"]

        if qtd_horistas_dentro >= total_vagas:
            return {
                "erro": f"Não há vagas rotativas disponíveis para {ROTULO_TIPO.get(tipo_veiculo, tipo_veiculo)}."
            }, 409

        return _gravar_entrada(conexao, cursor, id_veiculo, id_cliente, placa, modalidade)

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


def listar_mensalistas(pagina=None, busca=None):
    """Lista as vagas mensalistas vinculadas (uma linha por vaga) com o valor em aberto de cada uma."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        gerar_cobrancas_em_atraso(cursor)
        conexao.commit()

        sql = """
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
        """
        params = []
        texto, digitos = padrao_busca(busca)
        if texto:
            if digitos:
                sql += " AND (c.nome LIKE %s OR v.codigo LIKE %s OR c.cpf LIKE %s OR c.cnpj LIKE %s)"
                params += [texto, texto, digitos, digitos]
            else:
                sql += " AND (c.nome LIKE %s OR v.codigo LIKE %s)"
                params += [texto, texto]
        return executar_paginado(cursor, sql, tuple(params), "c.nome, v.codigo", pagina), 200

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
            SELECT id_vaga, codigo, tipo_vaga, tipo_veiculo, id_cliente
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

        falta = mensagem_se_faltar_vaga(cursor, id_cliente, vaga["tipo_veiculo"], id_vaga)
        if falta:
            conexao.commit()
            return {"erro": falta}, 409

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
