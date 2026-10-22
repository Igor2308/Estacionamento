"""Cria (ou redefine a senha de) um usuário do sistema.

Uso (dentro da pasta backend):  python criar_usuario.py admin "Nome do Operador"
A senha é pedida no terminal e guardada como hash.
"""
import getpass
import sys

from werkzeug.security import generate_password_hash

from config.database import conectar_banco


def main():
    if len(sys.argv) < 3:
        sys.exit('Uso: python criar_usuario.py <login> "<nome>"')
    login, nome = sys.argv[1].strip(), sys.argv[2].strip()
    senha = getpass.getpass("Senha: ")
    if len(senha) < 6 or senha != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas devem ser iguais e ter ao menos 6 caracteres.")

    con = conectar_banco()
    cur = con.cursor()
    cur.execute(
        """INSERT INTO usuarios (nome, login, senha_hash) VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE nome = VALUES(nome), senha_hash = VALUES(senha_hash), ativo = TRUE""",
        (nome, login, generate_password_hash(senha)),
    )
    con.commit()
    cur.close()
    con.close()
    print(f"Usuário '{login}' salvo.")


if __name__ == "__main__":
    main()
