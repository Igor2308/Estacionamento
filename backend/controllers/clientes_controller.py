
from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from utils.validators import (
    somente_digitos, validar_cnpj, validar_cpf, validar_email, validar_telefone,
)
from controllers.enderecos_controller import _validar_endereco, inserir_endereco


def _validar_documentos(tipo_pessoa, cpf, cnpj):
    """Normaliza (só dígitos) e valida CPF/CNPJ conforme o tipo de pessoa."""
    cpf = somente_digitos(cpf) or None
    cnpj = somente_digitos(cnpj) or None

    if tipo_pessoa == "FISICA":
        if cnpj:
            return None, None, "Pessoa física não usa CNPJ."
        if not cpf:
            return None, None, "O CPF é obrigatório."
        if not validar_cpf(cpf):
            return None, None, "CPF inválido."
    else:
        if cpf:
            return None, None, "Pessoa jurídica não usa CPF."
        if not cnpj:
            return None, None, "O CNPJ é obrigatório."
        if not validar_cnpj(cnpj):
            return None, None, "CNPJ inválido."

    return cpf, cnpj, None


def listar_clientes():
    """Lista os clientes cadastrados."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT *
            FROM clientes
            ORDER BY nome
        """)
        return {"dados": cursor.fetchall()}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def consultar_cliente(id_cliente):
    """Consulta um cliente pelo identificador."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT *
            FROM clientes
            WHERE id_cliente = %s
        """, (id_cliente,))

        cliente = cursor.fetchone()

        if not cliente:
            return {"erro": "Cliente não encontrado."}, 404

        return {"dados": cliente}, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else ""


def _validar_contato(telefone, email):
    """Telefone é obrigatório; e-mail é opcional (mas, se vier, precisa ser válido)."""
    if not _texto(telefone):
        return "O telefone é obrigatório."
    if not validar_telefone(telefone):
        return "Telefone inválido. Informe o DDD + número (10 ou 11 dígitos)."
    if _texto(email) and not validar_email(email):
        return "E-mail inválido."
    return None


def cadastrar_cliente(dados):
    """Cadastra o cliente JUNTO com o endereço principal (tudo ou nada).

    Obrigatórios: nome, tipo, CPF/CNPJ, telefone, modalidade e endereço completo
    (tipo, CEP, logradouro, número, bairro, cidade e UF). Só e-mail e complemento são opcionais.
    """
    nome = dados.get("nome")
    tipo_pessoa = dados.get("tipo_pessoa", "FISICA")
    modalidade = dados.get("modalidade")

    if not _texto(nome):
        return {"erro": "O nome é obrigatório."}, 400

    if tipo_pessoa not in ("FISICA", "JURIDICA"):
        return {"erro": "Tipo de pessoa inválido."}, 400

    if modalidade not in ("MENSALISTA", "HORISTA"):
        return {"erro": "Informe a modalidade (mensalista ou horista)."}, 400

    cpf, cnpj, erro_doc = _validar_documentos(
        tipo_pessoa, dados.get("cpf"), dados.get("cnpj")
    )
    if erro_doc:
        return {"erro": erro_doc}, 400

    erro_contato = _validar_contato(dados.get("telefone"), dados.get("email"))
    if erro_contato:
        return {"erro": erro_contato}, 400

    endereco = dados.get("endereco")
    if not isinstance(endereco, dict):
        return {"erro": "Informe o endereço do cliente."}, 400
    erro_endereco = _validar_endereco(endereco)
    if erro_endereco:
        return {"erro": erro_endereco}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            INSERT INTO clientes (
                nome, tipo_pessoa, cpf, cnpj,
                telefone, email, modalidade,
                cadastrado_por, atualizado_por
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            nome.strip(),
            tipo_pessoa,
            cpf,
            cnpj,
            dados["telefone"].strip(),
            _texto(dados.get("email")) or None,
            modalidade,
            usuario_atual(),
            usuario_atual(),
        ))
        id_cliente = cursor.lastrowid

        # O primeiro endereço do cliente é sempre o principal.
        id_endereco = inserir_endereco(cursor, id_cliente, endereco, True)

        conexao.commit()

        return {
            "mensagem": "Cliente e endereço cadastrados com sucesso.",
            "id_cliente": id_cliente,
            "id_endereco": id_endereco,
        }, 201

    except IntegrityError:
        conexao.rollback()
        return {
            "erro": "Não foi possível cadastrar. Verifique se o CPF ou CNPJ já está em uso."
        }, 409

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def atualizar_cliente(id_cliente, dados):
    """Atualiza os dados permitidos de um cliente."""
    campos_permitidos = {
        "nome", "tipo_pessoa", "cpf", "cnpj",
        "telefone", "email", "modalidade",
    }

    alteracoes = {
        campo: dados[campo]
        for campo in campos_permitidos
        if campo in dados
    }

    if not alteracoes:
        return {"erro": "Nenhum campo válido foi informado."}, 400

    if "nome" in alteracoes and (
        not isinstance(alteracoes["nome"], str)
        or not alteracoes["nome"].strip()
    ):
        return {"erro": "O nome não pode ficar vazio."}, 400

    if "tipo_pessoa" in alteracoes and alteracoes["tipo_pessoa"] not in (
        "FISICA", "JURIDICA"
    ):
        return {"erro": "Tipo de pessoa inválido."}, 400

    if "modalidade" in alteracoes and alteracoes["modalidade"] not in (
        "MENSALISTA", "HORISTA"
    ):
        return {"erro": "Modalidade inválida."}, 400

    if "nome" in alteracoes:
        alteracoes["nome"] = alteracoes["nome"].strip()

    if "telefone" in alteracoes:
        if not _texto(alteracoes["telefone"]):
            return {"erro": "O telefone é obrigatório."}, 400
        if not validar_telefone(alteracoes["telefone"]):
            return {"erro": "Telefone inválido. Informe o DDD + número (10 ou 11 dígitos)."}, 400
        alteracoes["telefone"] = alteracoes["telefone"].strip()

    if "email" in alteracoes:
        if _texto(alteracoes["email"]) and not validar_email(alteracoes["email"]):
            return {"erro": "E-mail inválido."}, 400
        alteracoes["email"] = _texto(alteracoes["email"]) or None

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_cliente, tipo_pessoa, cpf, cnpj "
            "FROM clientes WHERE id_cliente = %s FOR UPDATE",
            (id_cliente,),
        )
        atual = cursor.fetchone()

        if not atual:
            return {"erro": "Cliente não encontrado."}, 404

        if {"tipo_pessoa", "cpf", "cnpj"} & set(alteracoes):
            efetivo = {**atual, **alteracoes}
            cpf, cnpj, erro_doc = _validar_documentos(
                efetivo["tipo_pessoa"], efetivo["cpf"], efetivo["cnpj"]
            )
            if erro_doc:
                return {"erro": erro_doc}, 400
            if "cpf" in alteracoes:
                alteracoes["cpf"] = cpf
            if "cnpj" in alteracoes:
                alteracoes["cnpj"] = cnpj

        cursor.close()
        cursor = conexao.cursor()

        alteracoes["atualizado_por"] = usuario_atual()

        colunas = ", ".join(f"{campo} = %s" for campo in alteracoes)
        valores = list(alteracoes.values()) + [id_cliente]

        cursor.execute(
            f"UPDATE clientes SET {colunas} WHERE id_cliente = %s",
            valores,
        )
        conexao.commit()

        return {"mensagem": "Cliente atualizado com sucesso."}, 200

    except IntegrityError:
        conexao.rollback()
        return {"erro": "CPF ou CNPJ já cadastrado."}, 409

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def desativar_cliente(id_cliente):
    """Desativa o cliente sem apagar seu histórico."""
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM movimentacoes
                  WHERE id_cliente = %s AND saida_em IS NULL) AS abertas,
                (SELECT COUNT(*) FROM vagas
                  WHERE id_cliente = %s) AS vagas
        """, (id_cliente, id_cliente))
        uso = cursor.fetchone()

        if uso["abertas"] > 0:
            return {"erro": "O cliente possui veículo no estacionamento."}, 409

        if uso["vagas"] > 0:
            return {"erro": "Desvincule as vagas do cliente antes de desativá-lo."}, 409

        cursor.close()
        cursor = conexao.cursor()
        cursor.execute("""
            UPDATE clientes
            SET ativo = FALSE, atualizado_por = %s
            WHERE id_cliente = %s AND ativo = TRUE
        """, (usuario_atual(), id_cliente))

        if cursor.rowcount == 0:
            conexao.rollback()
            return {"erro": "Cliente não encontrado ou já desativado."}, 404

        conexao.commit()
        return {"mensagem": "Cliente desativado com sucesso."}, 200

    except Exception:
        conexao.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        conexao.close()
