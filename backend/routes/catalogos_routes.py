from flask import Blueprint, jsonify, request

from controllers.catalogos_controller import (
    cadastrar_cor, cadastrar_marca, cadastrar_modelo,
    listar_cores, listar_marcas, listar_modelos,
)

catalogos_bp = Blueprint("catalogos", __name__, url_prefix="/api")


@catalogos_bp.route("/marcas", methods=["GET"])
def marcas():
    resultado, status = listar_marcas()
    return jsonify(resultado), status


@catalogos_bp.route("/marcas", methods=["POST"])
def nova_marca():
    resultado, status = cadastrar_marca(request.get_json(silent=True) or {})
    return jsonify(resultado), status


@catalogos_bp.route("/modelos", methods=["GET"])
def modelos():
    resultado, status = listar_modelos(request.args.get("id_marca", type=int))
    return jsonify(resultado), status


@catalogos_bp.route("/modelos", methods=["POST"])
def novo_modelo():
    resultado, status = cadastrar_modelo(request.get_json(silent=True) or {})
    return jsonify(resultado), status


@catalogos_bp.route("/cores", methods=["GET"])
def cores():
    resultado, status = listar_cores()
    return jsonify(resultado), status


@catalogos_bp.route("/cores", methods=["POST"])
def nova_cor():
    resultado, status = cadastrar_cor(request.get_json(silent=True) or {})
    return jsonify(resultado), status
