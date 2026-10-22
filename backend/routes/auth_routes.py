
from flask import Blueprint, jsonify, request

from controllers.auth_controller import (
    autenticar_usuario,
    encerrar_sessao,
    consultar_sessao,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True) or {}
    resultado, status = autenticar_usuario(
        dados.get("login"),
        dados.get("senha"),
    )
    return jsonify(resultado), status


@auth_bp.route("/logout", methods=["POST"])
def logout():
    resultado, status = encerrar_sessao()
    return jsonify(resultado), status


@auth_bp.route("/sessao", methods=["GET"])
def sessao():
    resultado, status = consultar_sessao()
    return jsonify(resultado), status
