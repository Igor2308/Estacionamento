from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from utils.validators import TIPOS_VEICULO, normalizar_placa, validar_placa

# Colunas devolvidas nas consultas (nomes de marca/modelo/cor vêm das listas cadastradas).
_SELECT = """
    SELECT
        v.*,
        c.nome AS nome_cliente,
        c.modalidade AS modalidade_cliente,
        ma.nome AS marca,
        mo.nome AS modelo,
        co.nome AS cor
    FROM veiculos v
    JOIN clientes c ON c.id_cliente = v.id_cliente
    LEFT JOIN marcas ma ON ma.id_marca = v.id_marca
    LEFT JOIN modelos mo ON mo.id_modelo = v.id_modelo
    LEFT JOIN cores co ON co.id_cor = v.id_cor
"""


def _id_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _validar_marca_modelo_cor(cursor, id_marca, id_modelo, id_cor):
    """Confere se marca, modelo e cor existem e se o modelo pertence à marca. Retorna erro ou None."""
    if not _id_valido(id_marca):
        return "Selecione a marca."
    if not _id_valido(id_modelo):
        return "Selecione o modelo."
    if not _id_valido(id_cor):
        return "Selecione a cor."

    cursor.execute("SELECT id_marca FROM marcas WHERE id_marca = %s", (id_marca,))
    if not cursor.fetchone():
        return "Marca não encontrada. Selecione uma marca da lista."
    cursor.execute("SELECT id_marca FROM modelos WHERE id_modelo = %s", (id_modelo,))
    modelo = cursor.fetchone()
    if not modelo:
        return "Modelo não encontrado. Selecione um modelo da lista."
    if modelo["id_marca"] != id_marca:
        return "O modelo escolhido não pertence a essa marca."
    cursor.execute("SELECT id_cor FROM cores WHERE id_cor = %s", (id_cor,))
    if not cursor.fetchone():
        return "Cor não encontrada. Selecione uma cor da lista."
    return None


def listar_veiculos(id_cliente=None):
    """Lista os veículos junto com os nomes dos clientes, opcionalmente filtrados."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        if id_cliente is not None:
            cursor.execute(_SELECT + " WHERE v.id_cliente = %s ORDER BY v.placa", (id_cliente,))
        else:
            cursor.execute(_SELECT + " ORDER BY v.placa")
        return {"dados": cursor.fetchall()}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def consultar_veiculo(id_veiculo):
    """Consulta um veículo pelo identificador."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(_SELECT + " WHERE v.id_veiculo = %s", (id_veiculo,))
        veiculo = cursor.fetchone()

        if not veiculo:
            return {"erro": "Veículo não encontrado."}, 404

        return {"dados": veiculo}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def cadastrar_veiculo(dados):
    """Cadastra um veículo vinculado a um cliente ativo, com marca/modelo/cor das listas."""
    placa = dados.get("placa")
    id_cliente = dados.get("id_cliente")

    if not id_cliente:
        return {"erro": "Informe o cliente do veículo."}, 400

    if not isinstance(placa, str) or not placa.strip():
        return {"erro": "A placa é obrigatória."}, 400

    tipo_veiculo = dados.get("tipo_veiculo", "CARRO")
    if tipo_veiculo not in TIPOS_VEICULO:
        return {"erro": "Tipo de veículo inválido."}, 400

    placa = normalizar_placa(placa)
    if not validar_placa(placa):
        return {"erro": "Placa inválida. Use o formato ABC1234 ou ABC1D23."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_cliente
            FROM clientes
            WHERE id_cliente = %s AND ativo = TRUE
        """, (id_cliente,))

        if not cursor.fetchone():
            return {"erro": "Cliente não encontrado ou inativo."}, 404

        erro = _validar_marca_modelo_cor(
            cursor, dados.get("id_marca"), dados.get("id_modelo"), dados.get("id_cor"))
        if erro:
            return {"erro": erro}, 400

        cursor.close()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO veiculos (
                id_cliente, placa, id_marca, id_modelo, id_cor, tipo_veiculo,
                cadastrado_por, atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            id_cliente,
            placa,
            dados["id_marca"],
            dados["id_modelo"],
            dados["id_cor"],
            tipo_veiculo,
            usuario_atual(),
            usuario_atual(),
        ))

        conexao.commit()

        return {
            "mensagem": "Veículo cadastrado com sucesso.",
            "id_veiculo": cursor.lastrowid,
        }, 201

    except IntegrityError:
        conexao.rollback()
        return {"erro": "Essa placa já está cadastrada."}, 409

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def atualizar_veiculo(id_veiculo, dados):
    """Atualiza os dados cadastrais de um veículo (o cliente dono não muda por aqui)."""
    campos_permitidos = {"placa", "id_marca", "id_modelo", "id_cor", "tipo_veiculo", "ativo"}

    alteracoes = {
        campo: dados[campo]
        for campo in campos_permitidos
        if campo in dados
    }

    if not alteracoes:
        return {"erro": "Nenhum campo válido foi informado."}, 400

    if "placa" in alteracoes:
        if not isinstance(alteracoes["placa"], str) or not alteracoes["placa"].strip():
            return {"erro": "A placa não pode ficar vazia."}, 400
        alteracoes["placa"] = normalizar_placa(alteracoes["placa"])
        if not validar_placa(alteracoes["placa"]):
            return {"erro": "Placa inválida. Use o formato ABC1234 ou ABC1D23."}, 400

    if "tipo_veiculo" in alteracoes and alteracoes["tipo_veiculo"] not in TIPOS_VEICULO:
        return {"erro": "Tipo de veículo inválido."}, 400

    if "ativo" in alteracoes and not isinstance(alteracoes["ativo"], bool):
        return {"erro": "O campo ativo deve ser true ou false."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_marca, id_modelo, id_cor FROM veiculos WHERE id_veiculo = %s FOR UPDATE",
            (id_veiculo,),
        )
        atual = cursor.fetchone()
        if not atual:
            return {"erro": "Veículo não encontrado."}, 404

        if {"id_marca", "id_modelo", "id_cor"} & set(alteracoes):
            efetivo = {**atual, **alteracoes}
            erro = _validar_marca_modelo_cor(
                cursor, efetivo["id_marca"], efetivo["id_modelo"], efetivo["id_cor"])
            if erro:
                return {"erro": erro}, 400

        cursor.close()
        cursor = conexao.cursor()
        alteracoes["atualizado_por"] = usuario_atual()
        colunas = ", ".join(f"{campo} = %s" for campo in alteracoes)

        cursor.execute(
            f"UPDATE veiculos SET {colunas} WHERE id_veiculo = %s",
            list(alteracoes.values()) + [id_veiculo],
        )

        conexao.commit()
        return {"mensagem": "Veículo atualizado com sucesso."}, 200

    except IntegrityError:
        conexao.rollback()
        return {"erro": "Essa placa já está cadastrada."}, 409

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def desativar_veiculo(id_veiculo):
    """Desativa um veículo sem apagar suas movimentações."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            UPDATE veiculos
            SET ativo = FALSE, atualizado_por = %s
            WHERE id_veiculo = %s AND ativo = TRUE
        """, (usuario_atual(), id_veiculo))

        if cursor.rowcount == 0:
            conexao.rollback()
            return {
                "erro": "Veículo não encontrado ou já desativado."
            }, 404

        conexao.commit()
        return {"mensagem": "Veículo desativado com sucesso."}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
