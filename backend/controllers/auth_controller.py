
import time

from flask import session
from werkzeug.security import check_password_hash

from config.database import conectar_banco


def autenticar_usuario(login, senha):
    """Valida as credenciais e inicia a sessão."""
    if not login or not senha:
        return {"erro": "Informe o login e a senha."}, 400

    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_usuario, nome, login, senha_hash, ativo
            FROM usuarios
            WHERE login = %s
            LIMIT 1
        """, (login.strip(),))

        usuario = cursor.fetchone()

        if (
            not usuario
            or not usuario["ativo"]
            or not check_password_hash(usuario["senha_hash"], senha)
        ):
            return {"erro": "Login ou senha inválidos."}, 401

        # Guarda somente os dados necessários na sessão.
        session.clear()
        session["id_usuario"] = usuario["id_usuario"]
        session["nome_usuario"] = usuario["nome"]
        session["ultima_atividade"] = time.time()
        session.permanent = False  # o cookie some quando o navegador é fechado

        return {
            "mensagem": "Login realizado com sucesso.",
            "usuario": {
                "id_usuario": usuario["id_usuario"],
                "nome": usuario["nome"],
                "login": usuario["login"],
            },
        }, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()


def encerrar_sessao():
    """Encerra a sessão do usuário atual."""
    session.clear()
    return {"mensagem": "Sessão encerrada com sucesso."}, 200


def consultar_sessao():
    """Retorna os dados básicos do usuário autenticado."""
    id_usuario = session.get("id_usuario")

    if not id_usuario:
        return {"erro": "Usuário não autenticado."}, 401

    return {
        "usuario": {
            "id_usuario": id_usuario,
            "nome": session.get("nome_usuario"),
        }
    }, 200
