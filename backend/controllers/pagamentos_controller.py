
from decimal import Decimal, InvalidOperation

from config.database import conectar_banco
from services.mensalidades_service import gerar_cobrancas_em_atraso
from utils.auth import usuario_atual


FORMAS_PAGAMENTO = (
    "DINHEIRO",
    "PIX",
    "CARTAO_CREDITO",
    "CARTAO_DEBITO",
    "TRANSFERENCIA",
    "OUTRO",
)


def listar_pagamentos():
    """Lista os pagamentos registrados."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                p.*,
                c.nome AS nome_cliente,
                m.placa_registrada
            FROM pagamentos p
            LEFT JOIN clientes c ON c.id_cliente = p.id_cliente
            LEFT JOIN movimentacoes m
                ON m.id_movimentacao = p.id_movimentacao
            ORDER BY p.pago_em DESC, p.id_pagamento DESC
        """)
        return {"dados": cursor.fetchall()}, 200

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
            quantidade_vagas = 1
            valor_unitario = Decimal(str(cobranca["valor"]))
            valor_pago = valor_unitario

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
            try:
                valor_pago = Decimal(str(dados.get("valor_pago", "")))
            except (InvalidOperation, ValueError):
                return {"erro": "Informe um valor válido."}, 400

            if not valor_pago.is_finite() or valor_pago <= 0:
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
                observacao,
                cadastrado_por,
                atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            dados.get("observacao") or None,
            usuario_atual(),
            usuario_atual(),
        ))

        id_pagamento = cursor.lastrowid

        if tipo_pagamento == "MENSALIDADE":
            cursor.execute("""
                UPDATE cobrancas_mensalidade
                SET status = 'PAGA', id_pagamento = %s
                WHERE id_cobranca = %s AND status = 'ABERTA'
            """, (id_pagamento, id_cobranca))

        conexao.commit()

        return {
            "mensagem": "Pagamento registrado com sucesso.",
            "id_pagamento": id_pagamento,
            "valor_pago": str(valor_pago),
            "quantidade_vagas_cobradas": quantidade_vagas,
        }, 201

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_cobrancas(status=None):
    """Lista as mensalidades geradas (por padrão todas; status='ABERTA' traz só as pendentes).

    Antes de listar, gera as mensalidades dos meses que já começaram.
    """
    if status not in (None, "ABERTA", "PAGA"):
        return {"erro": "Status inválido."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        gerar_cobrancas_em_atraso(cursor)
        conexao.commit()

        sql = """
            SELECT
                cb.*,
                c.nome AS nome_cliente,
                v.codigo AS codigo_vaga
            FROM cobrancas_mensalidade cb
            JOIN clientes c ON c.id_cliente = cb.id_cliente
            JOIN vagas v ON v.id_vaga = cb.id_vaga
        """
        parametros = ()
        if status:
            sql += " WHERE cb.status = %s"
            parametros = (status,)
        sql += " ORDER BY cb.competencia_inicio, c.nome, v.codigo"
        cursor.execute(sql, parametros)
        return {"dados": cursor.fetchall()}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
