
from flask import Blueprint, jsonify, request

from controllers.veiculos_controller import (
    listar_veiculos,
    consultar_veiculo,
    cadastrar_veiculo,
    atualizar_veiculo,
    desativar_veiculo,
)

veiculos_bp = Blueprint("veiculos", __name__, url_prefix="/api/veiculos")


@veiculos_bp.route("", methods=["GET"])
def listar():
    id_cliente = request.args.get("id_cliente", type=int)
    resultado, status = listar_veiculos(id_cliente)
    return jsonify(resultado), status


@veiculos_bp.route("/<int:id_veiculo>", methods=["GET"])
def consultar(id_veiculo):
    resultado, status = consultar_veiculo(id_veiculo)
    return jsonify(resultado), status


@veiculos_bp.route("", methods=["POST"])
def cadastrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = cadastrar_veiculo(dados)
    return jsonify(resultado), status


@veiculos_bp.route("/<int:id_veiculo>", methods=["PUT"])
def atualizar(id_veiculo):
    dados = request.get_json(silent=True) or {}
    resultado, status = atualizar_veiculo(id_veiculo, dados)
    return jsonify(resultado), status


@veiculos_bp.route("/<int:id_veiculo>", methods=["DELETE"])
def desativar(id_veiculo):
    resultado, status = desativar_veiculo(id_veiculo)
    return jsonify(resultado), status
