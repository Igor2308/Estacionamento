from flask import Blueprint, jsonify, request

from controllers.tarifas_controller import cadastrar_tarifa, listar_tarifas

tarifas_bp = Blueprint("tarifas", __name__, url_prefix="/api/tarifas")


@tarifas_bp.route("", methods=["GET"])
def listar():
    resultado, status = listar_tarifas()
    return jsonify(resultado), status


@tarifas_bp.route("", methods=["POST"])
def cadastrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = cadastrar_tarifa(dados)
    return jsonify(resultado), status
