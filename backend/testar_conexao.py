
from config.database import conectar_banco

try:
    conexao = conectar_banco()

    if conexao.is_connected():
        print("Conexão com o MySQL realizada com sucesso!")

except Exception as erro:
    print(f"Erro ao conectar com o banco: {erro}")

finally:
    if "conexao" in locals() and conexao.is_connected():
        conexao.close()
        print("Conexão encerrada.")
