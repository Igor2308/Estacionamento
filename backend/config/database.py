import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

# Raiz do projeto: Projeto_Estacionamento/
RAIZ_PROJETO = Path(__file__).resolve().parents[2]
ARQUIVO_ENV = RAIZ_PROJETO / ".env"
load_dotenv(ARQUIVO_ENV, override=True)


def conectar_banco():
    """Abre e retorna uma conexão com o MySQL."""
    # DB_NAME_TESTE só existe nos testes de integração (nunca no .env real).
    banco = os.getenv("DB_NAME_TESTE") or os.getenv("DB_NAME")
    usuario = os.getenv("DB_USER")
    if not banco or not usuario:
        raise RuntimeError(
            "Configure DB_NAME e DB_USER no arquivo .env antes de conectar ao MySQL."
        )

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=banco,
        user=usuario,
        password=os.getenv("DB_PASSWORD", ""),
    )
