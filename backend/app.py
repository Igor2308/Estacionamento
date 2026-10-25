
import os
import time

from flask import Flask, jsonify, redirect, request, session
from dotenv import load_dotenv

from config.database import ARQUIVO_ENV
from routes.auth_routes import auth_bp
from routes.clientes_routes import clientes_bp
from routes.enderecos_routes import enderecos_bp
from routes.veiculos_routes import veiculos_bp
from routes.catalogos_routes import catalogos_bp
from routes.tarifas_routes import tarifas_bp
from routes.vagas_routes import vagas_bp
from routes.movimentacoes_routes import movimentacoes_bp
from routes.pagamentos_routes import pagamentos_bp
from routes.dashboard_routes import dashboard_bp


PAGINA_LOGIN = "/app/html/login.html"


def criar_app():
    load_dotenv(ARQUIVO_ENV, override=True)

    pasta_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
    app = Flask(
        __name__,
        static_folder=pasta_frontend,
        static_url_path="/app",
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Configure FLASK_SECRET_KEY no arquivo .env.")

    # Tempo máximo sem usar o sistema (em minutos) antes de pedir login de novo.
    limite_inatividade = int(os.getenv("SESSION_IDLE_MINUTES", "30")) * 60

    @app.before_request
    def controlar_acesso():
        """Todas as telas (HTML) e toda a API, exceto login, exigem usuário logado.

        - sem sessão: a API responde 401 e as telas redirecionam para o login;
        - ficar sem usar o sistema além do limite encerra a sessão;
        - abrir a tela de login (inclusive voltando pela seta do navegador) sempre encerra a sessão,
          então é preciso digitar usuário e senha de novo.
        """
        caminho = request.path.lower()
        e_tela = caminho.startswith("/app/html/")
        e_api = caminho.startswith("/api/")
        if not (e_tela or e_api):
            return None  # CSS/JS/imagens: nada sigiloso

        if session.get("id_usuario"):
            agora = time.time()
            if agora - session.get("ultima_atividade", agora) > limite_inatividade:
                session.clear()
            else:
                session["ultima_atividade"] = agora

        if caminho == PAGINA_LOGIN:
            session.clear()
            return None
        if caminho.startswith("/api/auth/"):
            return None
        if session.get("id_usuario"):
            return None
        if e_api:
            return jsonify({"erro": "Faça login para continuar."}), 401
        return redirect(PAGINA_LOGIN)

    @app.after_request
    def nao_guardar_em_cache(resposta):
        """Telas e API nunca ficam no cache: ao voltar no navegador depois de sair, o servidor decide de novo."""
        caminho = request.path.lower()
        if caminho.startswith("/app/html/") or caminho.startswith("/api/"):
            resposta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resposta.headers["Pragma"] = "no-cache"
            resposta.headers["Expires"] = "0"
        return resposta

    @app.route("/", methods=["GET"])
    def inicio():
        return jsonify({
            "mensagem": "API do Estacionamento funcionando!"
        }), 200

    app.register_blueprint(auth_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(enderecos_bp)
    app.register_blueprint(veiculos_bp)
    app.register_blueprint(catalogos_bp)
    app.register_blueprint(tarifas_bp)
    app.register_blueprint(vagas_bp)
    app.register_blueprint(movimentacoes_bp)
    app.register_blueprint(pagamentos_bp)
    app.register_blueprint(dashboard_bp)

    return app


if __name__ == "__main__":
    app = criar_app()
    app.run(debug=True)
