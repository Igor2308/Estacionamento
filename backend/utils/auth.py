from flask import session


def usuario_atual():
    """Id do usuário logado (None fora de uma requisição ou sem login)."""
    try:
        return session.get("id_usuario")
    except RuntimeError:
        return None
