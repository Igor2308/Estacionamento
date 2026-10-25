
from decimal import Decimal, InvalidOperation

from config.database import conectar_banco
from services.mensalidades_service import gerar_cobrancas_em_atraso
from utils.auth import usuario_atual
from utils.paginacao import escapar_like, executar_paginado, padrao_busca
from utils.validators import normalizar_placa

CENTAVOS = Decimal("0.01")
VALOR_MAXIMO = Decimal("99999999.99")


def _dinheiro(valor):
    """Converte o texto/número em Decimal com no máximo 2 casas (aceita vírgula). None se for inválido."""
    try:
        v = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not v.is_finite() or v != v.quantize(CENTAVOS) or abs(v) > VALOR_MAXIMO:
        return None
    return v.quantize(CENTAVOS)


FORMAS_PAGAMENTO = (
    "DINHEIRO",
    "PIX",
    "CARTAO_CREDITO",
    "CARTAO_DEBITO",
    "TRANSFERENCIA",
    "OUTRO",
)


def listar_pagamentos(pagina=None, busca=None):
    """Lista os pagamentos registrados (paginado quando `pagina` é informada).

    busca: nome do cliente, CPF/CNPJ ou placa. Traz também quem registrou (e quando),
    o valor recebido e o troco dos pagamentos em dinheiro.
    """
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT
                p.*,
                c.nome AS nome_cliente,
                m.placa_registrada,
                uc.nome AS cadastrado_por_nome
            FROM pagamentos p
            LEFT JOIN clientes c ON c.id_cliente = p.id_cliente
            LEFT JOIN movimentacoes m
                ON m.id_movimentacao = p.id_movimentacao
            LEFT JOIN usuarios uc ON uc.id_usuario = p.cadastrado_por
            WHERE 1 = 1
        """
        params = []
        texto, digitos = padrao_busca(busca)
        if texto:
            placa = f"%{escapar_like(normalizar_placa(busca))}%"
            if digitos:
                sql += " AND (c.nome LIKE %s OR c.cpf LIKE %s OR c.cnpj LIKE %s OR m.placa_registrada LIKE %s)"
                params += [texto, digitos, digitos, placa]
            else:
                sql += " AND (c.nome LIKE %s OR m.placa_registrada LIKE %s)"
                params += [texto, placa]
        return executar_paginado(cursor, sql, tuple(params), "p.pago_em DESC, p.id_pagamento DESC", pagina), 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_saidas_pendentes(pagina=None, busca=None, id_movimentacao=None):
    """Saídas de horistas com valor a cobrar e ainda sem pagamento registrado."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT
                m.id_movimentacao, m.placa_registrada, m.valor_total, m.saida_em,
                c.nome AS nome_cliente
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            WHERE m.saida_em IS NOT NULL
              AND m.valor_total > 0
              AND (c.modalidade IS NULL OR c.modalidade <> 'MENSALISTA')
              AND NOT EXISTS (SELECT 1 FROM pagamentos pg WHERE pg.id_movimentacao = m.id_movimentacao)
        """
        params = []
        if id_movimentacao:
            sql += " AND m.id_movimentacao = %s"
            params.append(id_movimentacao)
        texto, _ = padrao_busca(busca)
        if texto:
            placa = f"%{escapar_like(normalizar_placa(busca))}%"
            sql += " AND (m.placa_registrada LIKE %s OR c.nome LIKE %s)"
            params += [placa, texto]
        return executar_paginado(cursor, sql, tuple(params), "m.saida_em DESC, m.id_movimentacao DESC", pagina), 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def resumo_dinheiro(data=None):
    """Controle do dinheiro físico do dia: quanto entrou (recebido), quanto saiu de troco e o saldo líquido."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        filtro = "DATE(pago_em) = CURRENT_DATE" if not data else "DATE(pago_em) = %s"
        cursor.execute(f"""
            SELECT
                COUNT(*) AS quantidade,
                COALESCE(SUM(COALESCE(valor_recebido, valor_pago)), 0) AS recebido,
                COALESCE(SUM(COALESCE(troco, 0)), 0) AS troco,
                COALESCE(SUM(valor_pago), 0) AS liquido
            FROM pagamentos
            WHERE forma_pagamento = 'DINHEIRO' AND {filtro}
        """, (data,) if data else ())
        r = cursor.fetchone()
        return {
            "quantidade": r["quantidade"],
            "recebido": str(r["recebido"]),
            "troco": str(r["troco"]),
            "liquido": str(r["liquido"]),
        }, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def registrar_pagamento(dados):
    """Registra um pagamento recebido e calcula os valores aplicáveis."""
    tipo_pagamento = dados.get("tipo_pagamento")
    forma_pagamento = dados.get("forma_pagamento")

    if tipo_pagamento not in ("MENSALIDADE", "HORISTA", "OUTRO"):
        return {"erro": "Tipo de pagamento inválido."}, 400

    if forma_pagamento not in FORMAS_PAGAMENTO:
        return {"erro": "Forma de pagamento inválida."}, 400

    id_cliente = dados.get("id_cliente")
    id_movimentacao = dados.get("id_movimentacao")
    id_cobranca = None
    ids_cobrancas = []
    competencia_inicio = None
    competencia_fim = None

    quantidade_vagas = None
    valor_unitario = None

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)

        if tipo_pagamento == "MENSALIDADE":
            # Paga uma mensalidade em aberto (gerada ao vincular a vaga ou a cada novo mês).
            id_cobranca = dados.get("id_cobranca")
            if isinstance(id_cobranca, bool) or not isinstance(id_cobranca, int) or id_cobranca <= 0:
                return {
                    "erro": "Selecione a mensalidade em aberto que será paga."
                }, 400

            cursor.execute("""
                SELECT id_cobranca, id_cliente, competencia_inicio, competencia_fim, valor, status
                FROM cobrancas_mensalidade
                WHERE id_cobranca = %s
                FOR UPDATE
            """, (id_cobranca,))
            cobranca = cursor.fetchone()

            if not cobranca:
                return {"erro": "Mensalidade não encontrada."}, 404

            if cobranca["status"] != "ABERTA":
                return {"erro": "Essa mensalidade já foi paga."}, 409

            id_cliente = cobranca["id_cliente"]
            competencia_inicio = cobranca["competencia_inicio"]
            competencia_fim = cobranca["competencia_fim"]

            # O cliente paga de uma vez as mensalidades de todas as vagas do mesmo período.
            cursor.execute("""
                SELECT id_cobranca, valor
                FROM cobrancas_mensalidade
                WHERE id_cliente = %s AND competencia_inicio = %s AND status = 'ABERTA'
                ORDER BY id_cobranca
                FOR UPDATE
            """, (id_cliente, competencia_inicio))
            do_periodo = cursor.fetchall()
            ids_cobrancas = [c["id_cobranca"] for c in do_periodo]
            valores = [Decimal(str(c["valor"])) for c in do_periodo]
            quantidade_vagas = len(valores)
            valor_pago = sum(valores, Decimal("0.00"))
            valor_unitario = valores[0] if len(set(valores)) == 1 else None

        elif tipo_pagamento == "HORISTA":
            if not id_movimentacao:
                return {
                    "erro": "Informe a movimentação horista."
                }, 400

            cursor.execute("""
                SELECT
                    m.id_movimentacao,
                    m.id_cliente,
                    m.saida_em,
                    m.valor_total,
                    m.placa_registrada,
                    c.modalidade
                FROM movimentacoes m
                LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
                WHERE m.id_movimentacao = %s
                FOR UPDATE
            """, (id_movimentacao,))
            movimentacao = cursor.fetchone()

            if not movimentacao:
                return {"erro": "Movimentação não encontrada."}, 404

            if movimentacao["saida_em"] is None:
                return {
                    "erro": "A movimentação ainda está aberta."
                }, 409

            if movimentacao["modalidade"] == "MENSALISTA":
                return {
                    "erro": "Essa movimentação pertence a um mensalista."
                }, 400

            if movimentacao["valor_total"] is None:
                return {
                    "erro": "A movimentação ainda não possui valor calculado."
                }, 409

            id_cliente = movimentacao["id_cliente"]
            valor_pago = Decimal(str(movimentacao["valor_total"]))

            if valor_pago <= 0:
                return {
                    "erro": "O valor da movimentação deve ser maior que zero."
                }, 400

            # Impede registrar mais de um pagamento para a mesma movimentação.
            cursor.execute("""
                SELECT id_pagamento
                FROM pagamentos
                WHERE id_movimentacao = %s
                LIMIT 1
            """, (id_movimentacao,))

            if cursor.fetchone():
                return {
                    "erro": "Essa movimentação já possui um pagamento registrado."
                }, 409

        else:
            # OUTRO: permite registrar outro recebimento informado pelo operador.
            valor_pago = _dinheiro(dados.get("valor_pago", ""))
            if valor_pago is None:
                return {"erro": "Informe um valor válido (até 2 casas decimais)."}, 400

            if valor_pago <= 0:
                return {
                    "erro": "O valor pago deve ser maior que zero."
                }, 400

            if id_cliente:
                cursor.execute("""
                    SELECT id_cliente
                    FROM clientes
                    WHERE id_cliente = %s
                """, (id_cliente,))

                if not cursor.fetchone():
                    return {"erro": "Cliente não encontrado."}, 404

        # Dinheiro: precisa informar quanto o cliente entregou; o troco é calculado aqui.
        valor_recebido = None
        troco = None
        if forma_pagamento == "DINHEIRO":
            valor_recebido = _dinheiro(dados.get("valor_recebido", ""))
            if valor_recebido is None:
                return {"erro": "Informe quanto o cliente entregou em dinheiro (valor válido)."}, 400
            if valor_recebido < valor_pago:
                return {
                    "erro": "O valor recebido é menor que o valor a pagar."
                }, 400
            troco = valor_recebido - valor_pago

        observacao = dados.get("observacao")
        if observacao is not None and not isinstance(observacao, str):
            return {"erro": "Observação inválida."}, 400
        observacao = (observacao or "").strip() or None
        if observacao and len(observacao) > 255:
            return {"erro": "A observação deve ter no máximo 255 caracteres."}, 400

        # O pagamento só é gravado depois de todas as validações.
        cursor.close()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO pagamentos (
                id_cliente,
                id_movimentacao,
                tipo_pagamento,
                competencia_inicio,
                competencia_fim,
                quantidade_vagas_cobradas,
                valor_unitario_aplicado,
                valor_pago,
                forma_pagamento,
                valor_recebido,
                troco,
                observacao,
                cadastrado_por,
                atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            id_cliente,
            id_movimentacao if tipo_pagamento == "HORISTA" else None,
            tipo_pagamento,
            competencia_inicio if tipo_pagamento == "MENSALIDADE" else None,
            competencia_fim if tipo_pagamento == "MENSALIDADE" else None,
            quantidade_vagas,
            valor_unitario,
            valor_pago,
            forma_pagamento,
            valor_recebido,
            troco,
            observacao,
            usuario_atual(),
            usuario_atual(),
        ))

        id_pagamento = cursor.lastrowid

        if tipo_pagamento == "MENSALIDADE":
            marcas = ", ".join(["%s"] * len(ids_cobrancas))
            cursor.execute(f"""
                UPDATE cobrancas_mensalidade
                SET status = 'PAGA', id_pagamento = %s
                WHERE id_cobranca IN ({marcas}) AND status = 'ABERTA'
            """, (id_pagamento, *ids_cobrancas))

        conexao.commit()

        return {
            "mensagem": "Pagamento registrado com sucesso.",
            "id_pagamento": id_pagamento,
            "valor_pago": str(valor_pago),
            "valor_recebido": str(valor_recebido) if valor_recebido is not None else None,
            "troco": str(troco) if troco is not None else None,
            "quantidade_vagas_cobradas": quantidade_vagas,
        }, 201

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_cobrancas(status=None, pagina=None, busca=None, agrupar=False):
    """Lista as mensalidades geradas (por padrão todas; status='ABERTA' traz só as pendentes).

    Antes de listar, gera as mensalidades dos meses que já começaram.
    Paginado quando `pagina` é informada; busca: cliente, CPF/CNPJ ou código da vaga.
    """
    if status not in (None, "ABERTA", "PAGA"):
        return {"erro": "Status inválido."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        gerar_cobrancas_em_atraso(cursor)
        conexao.commit()

        # agrupar: uma linha por cliente e período, somando as vagas (é assim que o cliente paga).
        if agrupar:
            sql = """
                SELECT
                    MIN(cb.id_cobranca) AS id_cobranca,
                    cb.id_cliente,
                    c.nome AS nome_cliente,
                    cb.competencia_inicio,
                    MIN(cb.competencia_fim) AS competencia_fim,
                    SUM(cb.valor) AS valor,
                    COUNT(*) AS quantidade_vagas,
                    GROUP_CONCAT(v.codigo ORDER BY v.codigo SEPARATOR ', ') AS codigo_vaga
                FROM cobrancas_mensalidade cb
                JOIN clientes c ON c.id_cliente = cb.id_cliente
                JOIN vagas v ON v.id_vaga = cb.id_vaga
                WHERE 1 = 1
            """
        else:
            sql = """
                SELECT
                    cb.*,
                    c.nome AS nome_cliente,
                    v.codigo AS codigo_vaga
                FROM cobrancas_mensalidade cb
                JOIN clientes c ON c.id_cliente = cb.id_cliente
                JOIN vagas v ON v.id_vaga = cb.id_vaga
                WHERE 1 = 1
            """
        params = []
        if status:
            sql += " AND cb.status = %s"
            params.append(status)
        texto, digitos = padrao_busca(busca)
        if texto:
            if digitos:
                sql += " AND (c.nome LIKE %s OR v.codigo LIKE %s OR c.cpf LIKE %s OR c.cnpj LIKE %s)"
                params += [texto, texto, digitos, digitos]
            else:
                sql += " AND (c.nome LIKE %s OR v.codigo LIKE %s)"
                params += [texto, texto]
        if agrupar:
            sql += " GROUP BY cb.id_cliente, c.nome, cb.competencia_inicio"
            return executar_paginado(
                cursor, sql, tuple(params), "cb.competencia_inicio, c.nome", pagina), 200
        return executar_paginado(
            cursor, sql, tuple(params), "cb.competencia_inicio, c.nome, v.codigo", pagina), 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
