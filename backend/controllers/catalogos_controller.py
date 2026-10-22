"""Listas controladas de marcas, modelos e cores de veículos.

O usuário cadastra cada item uma única vez e depois só seleciona. O banco ignora
maiúsculas/minúsculas e acentos, então "verde", "Verde" e "VERDE" são o mesmo item.
Se o item já existe, devolvemos o existente (para a tela apenas selecioná-lo).
"""
from config.database import conectar_banco
from utils.auth import usuario_atual

# nome da tabela -> (coluna id, tamanho máximo do nome)
_CATALOGOS = {
    "marcas": ("id_marca", 60),
    "cores": ("id_cor", 40),
}


def _limpar(nome, maximo):
    if not isinstance(nome, str):
        return None
    nome = " ".join(nome.split())  # tira espaços sobrando
    return nome if nome and len(nome) <= maximo else None


def _listar(tabela, filtro_marca=None):
    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        if tabela == "modelos":
            sql = "SELECT id_modelo, id_marca, nome FROM modelos"
            if filtro_marca is not None:
                cursor.execute(sql + " WHERE id_marca = %s ORDER BY nome", (filtro_marca,))
            else:
                cursor.execute(sql + " ORDER BY nome")
        else:
            col = _CATALOGOS[tabela][0]
            cursor.execute(f"SELECT {col}, nome FROM {tabela} ORDER BY nome")
        return {"dados": cursor.fetchall()}, 200
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def listar_marcas():
    return _listar("marcas")


def listar_cores():
    return _listar("cores")


def listar_modelos(id_marca=None):
    return _listar("modelos", id_marca)


def _cadastrar_simples(tabela, dados, rotulo):
    col, maximo = _CATALOGOS[tabela]
    nome = _limpar((dados or {}).get("nome"), maximo)
    if not nome:
        return {"erro": f"Informe o nome da {rotulo} (até {maximo} caracteres)."}, 400

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(f"SELECT {col}, nome FROM {tabela} WHERE nome = %s", (nome,))
        existente = cursor.fetchone()
        if existente:
            return {"mensagem": f"Essa {rotulo} já estava cadastrada.", col: existente[col],
                    "nome": existente["nome"], "ja_existia": True}, 200

        cursor.execute(f"INSERT INTO {tabela} (nome, cadastrado_por) VALUES (%s, %s)", (nome, usuario_atual()))
        novo = cursor.lastrowid
        conexao.commit()
        return {"mensagem": f"{rotulo.capitalize()} cadastrada.", col: novo, "nome": nome, "ja_existia": False}, 201
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()


def cadastrar_marca(dados):
    return _cadastrar_simples("marcas", dados, "marca")


def cadastrar_cor(dados):
    return _cadastrar_simples("cores", dados, "cor")


def cadastrar_modelo(dados):
    dados = dados or {}
    id_marca = dados.get("id_marca")
    if isinstance(id_marca, bool) or not isinstance(id_marca, int) or id_marca <= 0:
        return {"erro": "Escolha a marca antes de cadastrar o modelo."}, 400
    nome = _limpar(dados.get("nome"), 80)
    if not nome:
        return {"erro": "Informe o nome do modelo (até 80 caracteres)."}, 400

    conexao = conectar_banco()
    cursor = None
    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("SELECT id_marca FROM marcas WHERE id_marca = %s", (id_marca,))
        if not cursor.fetchone():
            return {"erro": "Marca não encontrada."}, 404

        cursor.execute("SELECT id_modelo, nome FROM modelos WHERE id_marca = %s AND nome = %s", (id_marca, nome))
        existente = cursor.fetchone()
        if existente:
            return {"mensagem": "Esse modelo já estava cadastrado.", "id_modelo": existente["id_modelo"],
                    "nome": existente["nome"], "ja_existia": True}, 200

        cursor.execute("INSERT INTO modelos (id_marca, nome, cadastrado_por) VALUES (%s, %s, %s)",
                       (id_marca, nome, usuario_atual()))
        novo = cursor.lastrowid
        conexao.commit()
        return {"mensagem": "Modelo cadastrado.", "id_modelo": novo, "nome": nome, "ja_existia": False}, 201
    except Exception:
        conexao.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        conexao.close()
