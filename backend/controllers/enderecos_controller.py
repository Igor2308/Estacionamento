from mysql.connector import IntegrityError

from config.database import conectar_banco
from utils.auth import usuario_atual
from utils.validators import (
    formatar_cep, validar_cep, validar_somente_letras, validar_uf,
)
import re

TIPOS_ENDERECO = ("RESIDENCIAL", "COMERCIAL", "COBRANCA", "OUTRO")
CAMPOS_EDITAVEIS = {
    "tipo_endereco", "cep", "logradouro", "numero", "complemento",
    "bairro", "cidade", "estado", "pais", "principal",
}
_NUMERO = re.compile(r"^(?=.*[0-9A-Za-z])[0-9A-Za-z/\-\s]{1,10}$")
_CEP_ESTRANGEIRO = re.compile(r"^(?=.*[0-9A-Za-z])[0-9A-Za-z\- ]{3,9}$")


def _e_brasil(pais):
    return " ".join(str(pais or "Brasil").split()).lower() in ("brasil", "brazil")


def _validar_endereco_campos(dados, parcial, pais_atual=None):
    """Regras de formato de cada campo do endereço (a mesma regra vale na tela e aqui)."""
    pais = dados.get("pais", pais_atual if parcial else "Brasil")
    brasil = _e_brasil(pais)

    if "pais" in dados and not validar_somente_letras(dados["pais"], 2, 60):
        return "País inválido. Use somente letras (2 a 60 caracteres)."

    if "cep" in dados and isinstance(dados["cep"], str) and dados["cep"].strip():
        if brasil and not validar_cep(dados["cep"]):
            return "CEP inválido. Informe 8 dígitos, somente números."
        if not brasil and not _CEP_ESTRANGEIRO.match(dados["cep"].strip()):
            return "Código postal inválido (3 a 9 caracteres)."

    if "logradouro" in dados and not (3 <= len(dados["logradouro"].strip()) <= 150):
        return "O logradouro deve ter de 3 a 150 caracteres."

    if "numero" in dados and not _NUMERO.match(dados["numero"].strip()):
        return "Número inválido (até 10 caracteres: números, letras, / ou -)."

    if dados.get("complemento") and len(str(dados["complemento"]).strip()) > 100:
        return "O complemento deve ter no máximo 100 caracteres."

    if "bairro" in dados and not (2 <= len(dados["bairro"].strip()) <= 100):
        return "O bairro deve ter de 2 a 100 caracteres."

    if "cidade" in dados and not validar_somente_letras(dados["cidade"], 2, 100):
        return "Cidade inválida. Use somente letras."

    if "estado" in dados and isinstance(dados["estado"], str):
        uf = dados["estado"].strip()
        if not re.fullmatch(r"[A-Za-z]{2}", uf):
            return "O estado deve conter a sigla com 2 letras."
        if brasil and not validar_uf(uf):
            return "UF inválida. Use a sigla de um estado brasileiro (ex.: SP)."
    return None


def _validar_endereco(dados, parcial=False, pais_atual=None):
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

    if "estado" in dados and (
        not isinstance(dados["estado"], str) or len(dados["estado"].strip()) != 2
    ):
        return "O estado deve conter a sigla com 2 letras."

    if "principal" in dados and not isinstance(dados["principal"], bool):
        return "O campo principal deve ser true ou false."

    return _validar_endereco_campos(dados, parcial, pais_atual)


def _cep_para_gravar(cep, pais):
    cep = (cep or "").strip()
    if not cep:
        return None
    return formatar_cep(cep) if _e_brasil(pais) else cep.upper()


def inserir_endereco(cursor, id_cliente, dados, principal):
    """INSERT do endereço (sem commit). Usado também pelo cadastro de cliente."""
    cursor.execute("""
        INSERT INTO enderecos (
            id_cliente, tipo_endereco, cep, logradouro, numero,
            complemento, bairro, cidade, estado, pais, principal,
            cadastrado_por, atualizado_por
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        id_cliente,
        dados.get("tipo_endereco", "RESIDENCIAL"),
        _cep_para_gravar(dados.get("cep"), dados.get("pais")),
        dados["logradouro"].strip(),
        dados["numero"].strip(),
        (dados.get("complemento") or "").strip() or None,
        dados.get("bairro") or None,
        " ".join(dados["cidade"].split()),
        dados["estado"].strip().upper(),
        " ".join((dados.get("pais") or "Brasil").split()),
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
    # Sem o país no pedido, a checagem por país (CEP/UF) só acontece depois de ler o endereço salvo.
    erro = _validar_endereco(dados, parcial=True, pais_atual="(desconhecido)")
    if erro:
        return {"erro": erro}, 400

    alteracoes = {k: dados[k] for k in CAMPOS_EDITAVEIS if k in dados}
    if not alteracoes:
        return {"erro": "Nenhum campo válido foi informado."}, 400

    for campo in ("logradouro", "numero"):
        if campo in alteracoes:
            alteracoes[campo] = alteracoes[campo].strip()
    for campo in ("cidade", "pais"):
        if campo in alteracoes:
            alteracoes[campo] = " ".join(alteracoes[campo].split())
    if "estado" in alteracoes:
        alteracoes["estado"] = alteracoes["estado"].strip().upper()
    for campo in ("cep", "complemento", "bairro"):
        if campo in alteracoes:
            alteracoes[campo] = (alteracoes[campo] or "").strip() or None

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_cliente, pais, cep, estado FROM enderecos WHERE id_endereco = %s FOR UPDATE",
            (id_endereco,),
        )
        endereco = cursor.fetchone()
        if not endereco:
            return {"erro": "Endereço não encontrado."}, 404

        # Revalida CEP e UF com o país final (se só o país mudou, o CEP/UF salvos precisam servir para ele).
        pais_efetivo = alteracoes.get("pais", endereco["pais"])
        efetivo = {"cep": endereco["cep"] or "", "estado": endereco["estado"], **alteracoes, "pais": pais_efetivo}
        erro = _validar_endereco_campos(efetivo, True, pais_efetivo)
        if erro:
            return {"erro": erro}, 400
        if "cep" in alteracoes and alteracoes["cep"]:
            alteracoes["cep"] = _cep_para_gravar(alteracoes["cep"], pais_efetivo)

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
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_cliente, principal FROM enderecos WHERE id_endereco = %s FOR UPDATE",
            (id_endereco,),
        )
        endereco = cursor.fetchone()
        if not endereco:
            return {"erro": "Endereço não encontrado."}, 404

        cursor.execute(
            "SELECT id_endereco FROM enderecos WHERE id_cliente = %s AND id_endereco <> %s ORDER BY id_endereco",
            (endereco["id_cliente"], id_endereco),
        )
        outros = cursor.fetchall()
        if not outros:
            return {"erro": "O cliente precisa ter pelo menos um endereço. Cadastre outro antes de excluir este."}, 409

        cursor.execute("DELETE FROM enderecos WHERE id_endereco = %s", (id_endereco,))
        if endereco["principal"]:
            cursor.execute(
                "UPDATE enderecos SET principal = TRUE, atualizado_por = %s WHERE id_endereco = %s",
                (usuario_atual(), outros[0]["id_endereco"]),
            )
        conexao.commit()
        return {"mensagem": "Endereço excluído com sucesso."}, 200
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()
