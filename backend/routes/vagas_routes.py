
from flask import Blueprint, jsonify, request

from controllers.vagas_controller import (
    listar_vagas,
    cadastrar_vaga,
    vincular_vaga_cliente,
    desvincular_vaga_cliente,
    atualizar_status_vaga,
)

vagas_bp = Blueprint("vagas", __name__, url_prefix="/api/vagas")


@vagas_bp.route("", methods=["GET"])
def listar():
    resultado, status = listar_vagas()
    return jsonify(resultado), status


@vagas_bp.route("", methods=["POST"])
def cadastrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = cadastrar_vaga(dados)
    return jsonify(resultado), status


@vagas_bp.route("/<int:id_vaga>/vincular", methods=["POST"])
def vincular(id_vaga):
    dados = request.get_json(silent=True) or {}
    id_cliente = dados.get("id_cliente")

    if id_cliente is None:
        return jsonify({"erro": "Informe o id_cliente."}), 400

    resultado, status = vincular_vaga_cliente(id_vaga, id_cliente)
    return jsonify(resultado), status


@vagas_bp.route("/<int:id_vaga>/desvincular", methods=["POST"])
def desvincular(id_vaga):
    resultado, status = desvincular_vaga_cliente(id_vaga)
    return jsonify(resultado), status


@vagas_bp.route("/<int:id_vaga>/status", methods=["PATCH"])
def atualizar_status(id_vaga):
    dados = request.get_json(silent=True) or {}

    if "ativa" not in dados or not isinstance(dados["ativa"], bool):
        return jsonify({"erro": "Informe 'ativa' como true ou false."}), 400

    resultado, status = atualizar_status_vaga(id_vaga, dados["ativa"])
    return jsonify(resultado), status
