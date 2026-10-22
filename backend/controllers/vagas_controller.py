
from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from services.mensalidades_service import criar_cobranca, gerar_cobrancas_em_atraso, mensagem_em_aberto
from utils.validators import TIPOS_VEICULO


def listar_vagas():
    """Lista as vagas e seus clientes vinculados."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                v.*,
                c.nome AS nome_cliente
            FROM vagas v
            LEFT JOIN clientes c ON c.id_cliente = v.id_cliente
            ORDER BY v.codigo
        """)
        return {"dados": cursor.fetchall()}, 200

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
            dados.get("setor") or None,
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


def vincular_vaga_cliente(id_vaga, id_cliente):
    """Vincula uma vaga mensalista a um cliente mensalista ativo e gera a mensalidade a pagar."""
    if not id_cliente:
        return {"erro": "Informe o cliente."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_vaga, tipo_vaga, tipo_veiculo, id_cliente, ativa
            FROM vagas
            WHERE id_vaga = %s
            FOR UPDATE
        """, (id_vaga,))
        vaga = cursor.fetchone()

        if not vaga:
            return {"erro": "Vaga não encontrada."}, 404

        if not vaga["ativa"]:
            return {"erro": "Não é possível vincular uma vaga inativa."}, 400

        if vaga["tipo_vaga"] != "MENSALISTA":
            return {"erro": "Somente vagas mensalistas podem ser vinculadas."}, 400

        if vaga["id_cliente"] is not None:
            return {"erro": "Essa vaga já está vinculada a um cliente."}, 409

        cursor.execute("""
            SELECT id_cliente, modalidade
            FROM clientes
            WHERE id_cliente = %s AND ativo = TRUE
            FOR UPDATE
        """, (id_cliente,))
        cliente = cursor.fetchone()

        if not cliente:
            return {"erro": "Cliente não encontrado ou inativo."}, 404

        if cliente["modalidade"] != "MENSALISTA":
            return {
                "erro": "A vaga só pode ser vinculada a um cliente mensalista."
            }, 400

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
            conexao.rollback()
            return {"erro": erro}, 409

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
            SELECT id_vaga, tipo_vaga, id_cliente
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
