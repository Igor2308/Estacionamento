
from flask import Blueprint, jsonify, request

from controllers.movimentacoes_controller import (
    listar_movimentacoes,
    listar_mensalistas,
    listar_movimentacoes_abertas,
    registrar_saida_mensalista,
    registrar_entrada,
    registrar_saida,
)

movimentacoes_bp = Blueprint(
    "movimentacoes", __name__, url_prefix="/api/movimentacoes"
)


@movimentacoes_bp.route("", methods=["GET"])
def listar():
    resultado, status = listar_movimentacoes()
    return jsonify(resultado), status


@movimentacoes_bp.route("/abertas", methods=["GET"])
def listar_abertas():
    resultado, status = listar_movimentacoes_abertas()
    return jsonify(resultado), status


@movimentacoes_bp.route("/entrada", methods=["POST"])
def entrada():
    dados = request.get_json(silent=True) or {}
    resultado, status = registrar_entrada(dados)
    return jsonify(resultado), status


@movimentacoes_bp.route("/<int:id_movimentacao>/saida", methods=["POST"])
def saida(id_movimentacao):
    resultado, status = registrar_saida(id_movimentacao)
    return jsonify(resultado), status


@movimentacoes_bp.route("/mensalistas", methods=["GET"])
def mensalistas():
    resultado, status = listar_mensalistas()
    return jsonify(resultado), status


@movimentacoes_bp.route("/mensalistas/vagas/<int:id_vaga>/saida", methods=["POST"])
def saida_mensalista(id_vaga):
    resultado, status = registrar_saida_mensalista(id_vaga)
    return jsonify(resultado), status
