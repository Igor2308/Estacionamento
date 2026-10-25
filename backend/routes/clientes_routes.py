from flask import Blueprint, jsonify, request

from utils.paginacao import ler_pagina

from controllers.clientes_controller import (
    listar_clientes,
    consultar_cliente,
    cadastrar_cliente,
    atualizar_cliente,
    desativar_cliente,
)

clientes_bp = Blueprint("clientes", __name__, url_prefix="/api/clientes")


@clientes_bp.route("", methods=["GET"])
def listar():
    ativo = request.args.get("ativo")
    resultado, status = listar_clientes(
        pagina=ler_pagina(request.args.get("pagina")),
        busca=request.args.get("busca"),
        modalidade=request.args.get("modalidade"),
        ativo=None if ativo is None else ativo in ("1", "true", "True"),
    )
    return jsonify(resultado), status


@clientes_bp.route("/<int:id_cliente>", methods=["GET"])
def consultar(id_cliente):
    resultado, status = consultar_cliente(id_cliente)
    return jsonify(resultado), status


@clientes_bp.route("", methods=["POST"])
def cadastrar():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400
    resultado, status = cadastrar_cliente(dados)
    return jsonify(resultado), status


@clientes_bp.route("/<int:id_cliente>", methods=["PUT"])
def atualizar(id_cliente):
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400
    resultado, status = atualizar_cliente(id_cliente, dados)
    return jsonify(resultado), status


@clientes_bp.route("/<int:id_cliente>", methods=["DELETE"])
def desativar(id_cliente):
    resultado, status = desativar_cliente(id_cliente)
    return jsonify(resultado), status
