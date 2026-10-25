
from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from utils.paginacao import executar_paginado, padrao_busca
from utils.validators import (
    so_formatacao, somente_digitos, validar_cnpj, validar_cpf, validar_email,
    validar_somente_letras, validar_telefone,
)
from controllers.enderecos_controller import _validar_endereco, inserir_endereco
from controllers.vagas_controller import vincular_na_transacao

import re

_NOME_EMPRESA = re.compile(r"^(?=.*[^\W\d_])[\w &.,'/\-]{3,150}$", re.UNICODE)


def _validar_nome(nome, tipo_pessoa):
    """Pessoa física: só letras (sem números). Pessoa jurídica: aceita números e & . , - /"""
    nome = " ".join(nome.split())
    if tipo_pessoa == "JURIDICA":
        if not _NOME_EMPRESA.match(nome):
            return "Nome inválido (3 a 150 caracteres, com pelo menos uma letra)."
    elif not validar_somente_letras(nome, 3, 150):
        return "Nome inválido. Use somente letras (3 a 150 caracteres), sem números."
    return None


def _validar_documentos(tipo_pessoa, cpf, cnpj):
    """Normaliza (só dígitos) e valida CPF/CNPJ conforme o tipo de pessoa."""
    if (cpf and not so_formatacao(str(cpf))) or (cnpj and not so_formatacao(str(cnpj))):
        return None, None, "Documento inválido: use somente números."
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


def listar_clientes(pagina=None, busca=None, modalidade=None, ativo=None):
    """Lista os clientes. Com `pagina` traz só os 50 daquela página (o resto carrega sob demanda).

    busca: parte do nome ou do CPF/CNPJ (a busca por documento ignora pontos e traços).
    """
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        sql = "SELECT * FROM clientes WHERE 1 = 1"
        params = []
        texto, digitos = padrao_busca(busca)
        if texto:
            if digitos:
                sql += " AND (nome LIKE %s OR cpf LIKE %s OR cnpj LIKE %s)"
                params += [texto, digitos, digitos]
            else:
                sql += " AND nome LIKE %s"
                params.append(texto)
        if modalidade in ("MENSALISTA", "HORISTA"):
            sql += " AND modalidade = %s"
            params.append(modalidade)
        if ativo is not None:
            sql += " AND ativo = %s"
            params.append(bool(ativo))
        return executar_paginado(cursor, sql, tuple(params), "nome, id_cliente", pagina), 200

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

    erro_nome = _validar_nome(nome, tipo_pessoa)
    if erro_nome:
        return {"erro": erro_nome}, 400

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

    # Vagas mensalistas escolhidas já no cadastro (quantas o cliente contratar): cliente, endereço
    # e vagas entram juntos, ou nada entra. Aceita `id_vagas` (lista) ou `id_vaga` (uma só).
    ids_vagas = dados.get("id_vagas")
    if ids_vagas is None and dados.get("id_vaga") not in (None, ""):
        ids_vagas = [dados.get("id_vaga")]
    ids_vagas = ids_vagas if ids_vagas is not None else []
    if not isinstance(ids_vagas, list) or len(ids_vagas) > 20 or any(
        isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in ids_vagas
    ):
        return {"erro": "Vagas inválidas."}, 400
    if len(set(ids_vagas)) != len(ids_vagas):
        return {"erro": "A mesma vaga foi escolhida mais de uma vez."}, 400
    if ids_vagas and modalidade != "MENSALISTA":
        return {"erro": "Só clientes mensalistas podem ter vaga vinculada."}, 400

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
            " ".join(nome.split()),
            tipo_pessoa,
            cpf,
            cnpj,
            somente_digitos(dados["telefone"]),
            _texto(dados.get("email")) or None,
            modalidade,
            usuario_atual(),
            usuario_atual(),
        ))
        id_cliente = cursor.lastrowid

        # O primeiro endereço do cliente é sempre o principal.
        id_endereco = inserir_endereco(cursor, id_cliente, endereco, True)

        mensagem = "Cliente e endereço cadastrados com sucesso."
        if ids_vagas:
            cursor_vaga = conexao.cursor(dictionary=True)
            try:
                for id_vaga in ids_vagas:
                    erro, status = vincular_na_transacao(cursor_vaga, id_vaga, id_cliente)
                    if erro:
                        conexao.rollback()
                        return {"erro": erro}, status
            finally:
                cursor_vaga.close()
            mensagem = (
                f"Cliente, endereço e {len(ids_vagas)} vaga(s) cadastrados. "
                "A mensalidade já está em aberto na tela Pagamentos."
            )

        conexao.commit()

        return {
            "mensagem": mensagem,
            "id_cliente": id_cliente,
            "id_endereco": id_endereco,
            "id_vagas": ids_vagas,
            "id_vaga": ids_vagas[0] if ids_vagas else None,
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
    # CPF/CNPJ e tipo de pessoa não mudam por aqui (se precisar, só direto no banco).
    # Se o pedido trouxer esses campos, eles são conferidos mais abaixo: iguais aos atuais são ignorados.
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
        alteracoes["nome"] = " ".join(alteracoes["nome"].split())

    if "telefone" in alteracoes:
        if not _texto(alteracoes["telefone"]):
            return {"erro": "O telefone é obrigatório."}, 400
        if not validar_telefone(alteracoes["telefone"]):
            return {"erro": "Telefone inválido. Informe o DDD + número (10 ou 11 dígitos)."}, 400
        alteracoes["telefone"] = somente_digitos(alteracoes["telefone"])

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

        if "nome" in alteracoes:
            erro_nome = _validar_nome(alteracoes["nome"], atual["tipo_pessoa"])
            if erro_nome:
                return {"erro": erro_nome}, 400

        if {"tipo_pessoa", "cpf", "cnpj"} & set(alteracoes):
            # Documento e tipo de pessoa são imutáveis: só passam se forem iguais ao que já está salvo.
            for campo in ("cpf", "cnpj"):
                if campo in alteracoes:
                    novo = somente_digitos(str(alteracoes[campo] or "")) or None
                    if novo != atual[campo]:
                        return {"erro": "O CPF/CNPJ do cliente não pode ser alterado."}, 400
                    del alteracoes[campo]
            if "tipo_pessoa" in alteracoes:
                if alteracoes["tipo_pessoa"] != atual["tipo_pessoa"]:
                    return {"erro": "O tipo de pessoa do cliente não pode ser alterado."}, 400
                del alteracoes["tipo_pessoa"]
            if not alteracoes:
                return {"mensagem": "Nada a atualizar."}, 200

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
