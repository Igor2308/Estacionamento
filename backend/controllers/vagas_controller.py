
from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from services.mensalidades_service import criar_cobranca, gerar_cobrancas_em_atraso, mensagem_em_aberto
from services.ocupacao_service import mensagem_se_faltar_vaga
from utils.paginacao import executar_paginado, escapar_like
from utils.validators import TIPOS_VEICULO

import re

_CODIGO_VAGA = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,19}$")
_SETOR = re.compile(r"^[^\W_][\w \-./]{0,49}$", re.UNICODE)


def listar_vagas(pagina=None, busca=None, tipo_vaga=None, livres=False, ativa=None):
    """Lista as vagas e seus clientes vinculados (paginado quando `pagina` é informada).

    busca: código, setor ou nome do cliente · livres: só mensalistas ativas sem cliente.
    """
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT
                v.*,
                c.nome AS nome_cliente,
                uc.nome AS cadastrado_por_nome,
                ua.nome AS atualizado_por_nome
            FROM vagas v
            LEFT JOIN clientes c ON c.id_cliente = v.id_cliente
            LEFT JOIN usuarios uc ON uc.id_usuario = v.cadastrado_por
            LEFT JOIN usuarios ua ON ua.id_usuario = v.atualizado_por
            WHERE 1 = 1
        """
        params = []
        if busca and busca.strip():
            like = f"%{escapar_like(' '.join(busca.split()))}%"
            sql += " AND (v.codigo LIKE %s OR v.setor LIKE %s OR c.nome LIKE %s)"
            params += [like, like, like]
        if tipo_vaga in ("MENSALISTA", "ROTATIVA"):
            sql += " AND v.tipo_vaga = %s"
            params.append(tipo_vaga)
        if livres:
            sql += " AND v.tipo_vaga = 'MENSALISTA' AND v.ativa = TRUE AND v.id_cliente IS NULL"
        if ativa is not None:
            sql += " AND v.ativa = %s"
            params.append(bool(ativa))
        return executar_paginado(cursor, sql, tuple(params), "v.codigo", pagina), 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def cadastrar_vaga(dados):
    """Cadastra uma vaga mensalista ou rotativa, definindo para qual tipo de veículo ela serve."""
    codigo = dados.get("codigo")
    tipo_vaga = dados.get("tipo_vaga", "ROTATIVA")

    if not isinstance(codigo, str) or not codigo.strip():
        return {"erro": "O código da vaga é obrigatório."}, 400

    if not _CODIGO_VAGA.match(codigo.strip().upper()):
        return {"erro": "Código inválido. Use letras, números e hífen (até 20 caracteres)."}, 400

    setor = dados.get("setor")
    if setor is not None and not isinstance(setor, str):
        return {"erro": "Setor inválido."}, 400
    setor = " ".join((setor or "").split()) or None
    if setor and not _SETOR.match(setor):
        return {"erro": "Setor inválido (até 50 caracteres, sem símbolos especiais)."}, 400

    if tipo_vaga not in ("MENSALISTA", "ROTATIVA"):
        return {"erro": "Tipo de vaga inválido."}, 400

    tipo_veiculo = dados.get("tipo_veiculo")
    if tipo_veiculo not in TIPOS_VEICULO:
        return {"erro": "Selecione o tipo de veículo da vaga (carro, moto, caminhão...)."}, 400

    # Uma vaga mensalista começa sem cliente e precisa ser vinculada depois.
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            INSERT INTO vagas (
                codigo, setor, tipo_vaga, tipo_veiculo, cadastrado_por, atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            codigo.strip().upper(),
            setor,
            tipo_vaga,
            tipo_veiculo,
            usuario_atual(),
            usuario_atual(),
        ))

        conexao.commit()
        return {
            "mensagem": "Vaga cadastrada com sucesso.",
            "id_vaga": cursor.lastrowid,
        }, 201

    except IntegrityError:
        conexao.rollback()
        return {"erro": "Já existe uma vaga com esse código."}, 409

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def vincular_na_transacao(cursor, id_vaga, id_cliente):
    """Vincula a vaga ao cliente mensalista e gera a 1ª mensalidade. NÃO faz commit/rollback.

    `cursor` precisa ser dictionary=True. Devolve (None, None) se deu certo ou (mensagem, status) se não.
    Também é usada pelo cadastro de cliente (cliente e vaga entram juntos, ou nada entra).
    """
    cursor.execute("""
        SELECT id_vaga, tipo_vaga, tipo_veiculo, id_cliente, ativa
        FROM vagas
        WHERE id_vaga = %s
        FOR UPDATE
    """, (id_vaga,))
    vaga = cursor.fetchone()

    if not vaga:
        return "Vaga não encontrada.", 404

    if not vaga["ativa"]:
        return "Não é possível vincular uma vaga inativa.", 400

    if vaga["tipo_vaga"] != "MENSALISTA":
        return "Somente vagas mensalistas podem ser vinculadas.", 400

    if vaga["id_cliente"] is not None:
        return "Essa vaga já está vinculada a um cliente.", 409

    cursor.execute("""
        SELECT id_cliente, modalidade
        FROM clientes
        WHERE id_cliente = %s AND ativo = TRUE
        FOR UPDATE
    """, (id_cliente,))
    cliente = cursor.fetchone()

    if not cliente:
        return "Cliente não encontrado ou inativo.", 404

    if cliente["modalidade"] != "MENSALISTA":
        return "A vaga só pode ser vinculada a um cliente mensalista.", 400

    cursor.execute("""
        UPDATE vagas
        SET id_cliente = %s, vinculada_em = CURRENT_TIMESTAMP,
            atualizado_por = %s
        WHERE id_vaga = %s
    """, (id_cliente, usuario_atual(), id_vaga))

    # A mensalidade do primeiro período já nasce em aberto, para ser paga na tela Pagamentos.
    cursor.execute("SELECT CURRENT_DATE AS hoje")
    hoje = cursor.fetchone()["hoje"]
    _, erro = criar_cobranca(
        cursor,
        {"id_vaga": id_vaga, "id_cliente": id_cliente, "tipo_veiculo": vaga["tipo_veiculo"]},
        hoje,
    )
    if erro:
        return erro, 409
    return None, None


def vincular_vaga_cliente(id_vaga, id_cliente):
    """Vincula uma vaga mensalista a um cliente mensalista ativo e gera a mensalidade a pagar."""
    if not id_cliente:
        return {"erro": "Informe o cliente."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        erro, status = vincular_na_transacao(cursor, id_vaga, id_cliente)
        if erro:
            conexao.rollback()
            return {"erro": erro}, status

        conexao.commit()
        return {"mensagem": "Vaga vinculada. A mensalidade foi gerada na tela Pagamentos."}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def desvincular_vaga_cliente(id_vaga):
    """Libera uma vaga mensalista para nova vinculação."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_vaga, tipo_vaga, tipo_veiculo, id_cliente
            FROM vagas
            WHERE id_vaga = %s
            FOR UPDATE
        """, (id_vaga,))
        vaga = cursor.fetchone()

        if not vaga:
            return {"erro": "Vaga não encontrada."}, 404

        if vaga["tipo_vaga"] != "MENSALISTA":
            return {"erro": "A vaga informada não é mensalista."}, 400

        if vaga["id_cliente"] is None:
            return {"erro": "Essa vaga já está livre."}, 409

        falta = mensagem_se_faltar_vaga(cursor, vaga["id_cliente"], vaga["tipo_veiculo"], id_vaga)
        if falta:
            return {"erro": falta}, 409

        gerar_cobrancas_em_atraso(cursor)
        bloqueio = mensagem_em_aberto(cursor, id_vaga, vaga["id_cliente"])
        if bloqueio:
            conexao.commit()  # mantém as cobranças em atraso que acabaram de ser geradas
            return {"erro": bloqueio}, 409

        cursor.execute("""
            UPDATE vagas
            SET id_cliente = NULL, vinculada_em = NULL, atualizado_por = %s
            WHERE id_vaga = %s
        """, (usuario_atual(), id_vaga))

        conexao.commit()
        return {"mensagem": "Vaga desvinculada com sucesso."}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def atualizar_status_vaga(id_vaga, ativa):
    """Ativa ou desativa uma vaga."""
    if not isinstance(ativa, bool):
        return {"erro": "O campo ativa deve ser verdadeiro ou falso."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_vaga, tipo_vaga, id_cliente
            FROM vagas
            WHERE id_vaga = %s
            FOR UPDATE
        """, (id_vaga,))
        vaga = cursor.fetchone()

        if not vaga:
            return {"erro": "Vaga não encontrada."}, 404

        if not ativa and vaga["tipo_vaga"] == "MENSALISTA" and vaga["id_cliente"]:
            return {
                "erro": "Desvincule a vaga do cliente antes de desativá-la."
            }, 409

        cursor.execute(
            "UPDATE vagas SET ativa = %s, atualizado_por = %s WHERE id_vaga = %s",
            (ativa, usuario_atual(), id_vaga),
        )
        conexao.commit()

        return {
            "mensagem": "Vaga ativada com sucesso."
            if ativa else "Vaga desativada com sucesso."
        }, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
