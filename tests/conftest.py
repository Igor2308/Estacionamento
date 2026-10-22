import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND_DIR = RAIZ / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Chave exclusiva para testes; não substitui a chave real do arquivo .env.
os.environ.setdefault("FLASK_SECRET_KEY", "chave-apenas-para-testes")

import pytest
from app import criar_app


@pytest.fixture
def app():
    app = criar_app()
    app.config.update(TESTING=True, SECRET_KEY="chave-apenas-para-testes")
    return app


@pytest.fixture
def client(app):
    return app.test_client()
