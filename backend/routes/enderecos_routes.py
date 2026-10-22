
from flask import Blueprint, jsonify, request

from controllers.enderecos_controller import (
    listar_enderecos,
    consultar_endereco,
    cadastrar_endereco,
    atualizar_endereco,
    excluir_endereco,
)

enderecos_bp = Blueprint(
    "enderecos", __name__, url_prefix="/api/enderecos"
)


@enderecos_bp.route("", methods=["GET"])
def listar():
    id_cliente = request.args.get("id_cliente", type=int)
    resultado, status = listar_enderecos(id_cliente)
    return jsonify(resultado), status


@enderecos_bp.route("/<int:id_endereco>", methods=["GET"])
def consultar(id_endereco):
    resultado, status = consultar_endereco(id_endereco)
    return jsonify(resultado), status


@enderecos_bp.route("", methods=["POST"])
def cadastrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = cadastrar_endereco(dados)
    return jsonify(resultado), status


@enderecos_bp.route("/<int:id_endereco>", methods=["PUT"])
def atualizar(id_endereco):
    dados = request.get_json(silent=True) or {}
    resultado, status = atualizar_endereco(id_endereco, dados)
    return jsonify(resultado), status


@enderecos_bp.route("/<int:id_endereco>", methods=["DELETE"])
def excluir(id_endereco):
    resultado, status = excluir_endereco(id_endereco)
    return jsonify(resultado), status
