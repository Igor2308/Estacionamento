from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from utils.validators import validar_cep

TIPOS_ENDERECO = ("RESIDENCIAL", "COMERCIAL", "COBRANCA", "OUTRO")
CAMPOS_EDITAVEIS = {
    "tipo_endereco", "cep", "logradouro", "numero", "complemento",
    "bairro", "cidade", "estado", "principal",
}


def _validar_endereco(dados, parcial=False):
    if not isinstance(dados, dict):
        return "Envie os dados do endereço em formato JSON."

    obrigatorios = ("logradouro", "numero", "bairro", "cidade", "estado", "cep")
    if not parcial:
        for campo in obrigatorios:
            valor = dados.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                return f"O campo {campo} é obrigatório."

    if "tipo_endereco" in dados and dados["tipo_endereco"] not in TIPOS_ENDERECO:
        return "Tipo de endereço inválido."

    for campo in obrigatorios:
        if campo in dados and (
            not isinstance(dados[campo], str) or not dados[campo].strip()
        ):
            return f"O campo {campo} não pode ficar vazio."

    if "cep" in dados and isinstance(dados["cep"], str) and dados["cep"].strip() and not validar_cep(dados["cep"]):
        return "CEP inválido. Informe 8 dígitos."

    if "estado" in dados and (
        not isinstance(dados["estado"], str) or len(dados["estado"].strip()) != 2
    ):
        return "O estado deve conter a sigla com 2 letras."

    if "principal" in dados and not isinstance(dados["principal"], bool):
        return "O campo principal deve ser true ou false."

    return None


def inserir_endereco(cursor, id_cliente, dados, principal):
    """INSERT do endereço (sem commit). Usado também pelo cadastro de cliente."""
    cursor.execute("""
        INSERT INTO enderecos (
            id_cliente, tipo_endereco, cep, logradouro, numero,
            complemento, bairro, cidade, estado, principal,
            cadastrado_por, atualizado_por
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        id_cliente,
        dados.get("tipo_endereco", "RESIDENCIAL"),
        dados.get("cep") or None,
        dados["logradouro"].strip(),
        dados["numero"].strip(),
        dados.get("complemento") or None,
        dados.get("bairro") or None,
        dados["cidade"].strip(),
        dados["estado"].strip().upper(),
        principal,
        usuario_atual(),
        usuario_atual(),
    ))
    return cursor.lastrowid


def listar_enderecos(id_cliente=None):
    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT e.*, c.nome AS nome_cliente
            FROM enderecos e
            JOIN clientes c ON c.id_cliente = e.id_cliente
        """
        parametros = ()
        if id_cliente is not None:
            sql += " WHERE e.id_cliente = %s"
            parametros = (id_cliente,)
        sql += " ORDER BY e.id_cliente, e.principal DESC, e.id_endereco"
        cursor.execute(sql, parametros)
        return {"dados": cursor.fetchall()}, 200
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def consultar_endereco(id_endereco):
    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.*, c.nome AS nome_cliente
            FROM enderecos e
            JOIN clientes c ON c.id_cliente = e.id_cliente
            WHERE e.id_endereco = %s
        """, (id_endereco,))
        endereco = cursor.fetchone()
        if not endereco:
            return {"erro": "Endereço não encontrado."}, 404
        return {"dados": endereco}, 200
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def cadastrar_endereco(dados):
    erro = _validar_endereco(dados)
    if erro:
        return {"erro": erro}, 400

    id_cliente = dados.get("id_cliente")
    if isinstance(id_cliente, bool) or not isinstance(id_cliente, int) or id_cliente <= 0:
        return {"erro": "Informe um id_cliente válido."}, 400

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_cliente FROM clientes WHERE id_cliente = %s AND ativo = TRUE",
            (id_cliente,),
        )
        if not cursor.fetchone():
            return {"erro": "Cliente não encontrado ou inativo."}, 404

        principal = dados.get("principal", False)
        if principal:
            cursor.execute(
                "UPDATE enderecos SET principal = FALSE WHERE id_cliente = %s",
                (id_cliente,),
            )

        cursor.close()
        cursor = conexao.cursor()
        id_endereco = inserir_endereco(cursor, id_cliente, dados, principal)
        conexao.commit()
        return {"mensagem": "Endereço cadastrado com sucesso.", "id_endereco": id_endereco}, 201
    except IntegrityError:
        conexao.rollback()
        return {"erro": "Não foi possível cadastrar o endereço por conflito com os dados relacionados."}, 409
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def atualizar_endereco(id_endereco, dados):
    erro = _validar_endereco(dados, parcial=True)
    if erro:
        return {"erro": erro}, 400

    alteracoes = {k: dados[k] for k in CAMPOS_EDITAVEIS if k in dados}
    if not alteracoes:
        return {"erro": "Nenhum campo válido foi informado."}, 400

    for campo in ("logradouro", "numero", "cidade"):
        if campo in alteracoes:
            alteracoes[campo] = alteracoes[campo].strip()
    if "estado" in alteracoes:
        alteracoes["estado"] = alteracoes["estado"].strip().upper()
    for campo in ("cep", "complemento", "bairro"):
        if campo in alteracoes and not alteracoes[campo]:
            alteracoes[campo] = None

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_cliente FROM enderecos WHERE id_endereco = %s FOR UPDATE",
            (id_endereco,),
        )
        endereco = cursor.fetchone()
        if not endereco:
            return {"erro": "Endereço não encontrado."}, 404

        if alteracoes.get("principal") is True:
            cursor.execute(
                "UPDATE enderecos SET principal = FALSE WHERE id_cliente = %s",
                (endereco["id_cliente"],),
            )

        cursor.close()
        cursor = conexao.cursor()
        alteracoes["atualizado_por"] = usuario_atual()
        colunas = ", ".join(f"{campo} = %s" for campo in alteracoes)
        cursor.execute(
            f"UPDATE enderecos SET {colunas} WHERE id_endereco = %s",
            list(alteracoes.values()) + [id_endereco],
        )
        conexao.commit()
        return {"mensagem": "Endereço atualizado com sucesso."}, 200
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def excluir_endereco(id_endereco):
    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM enderecos WHERE id_endereco = %s", (id_endereco,))
        if cursor.rowcount == 0:
            conexao.rollback()
            return {"erro": "Endereço não encontrado."}, 404
        conexao.commit()
        return {"mensagem": "Endereço excluído com sucesso."}, 200
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()
