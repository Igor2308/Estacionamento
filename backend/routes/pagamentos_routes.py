
from flask import Blueprint, jsonify, request

from utils.paginacao import ler_pagina

from controllers.pagamentos_controller import (
    listar_cobrancas,
    listar_pagamentos,
    listar_saidas_pendentes,
    registrar_pagamento,
    resumo_dinheiro,
)

pagamentos_bp = Blueprint(
    "pagamentos", __name__, url_prefix="/api/pagamentos"
)


@pagamentos_bp.route("", methods=["GET"])
def listar():
    resultado, status = listar_pagamentos(
        pagina=ler_pagina(request.args.get("pagina")),
        busca=request.args.get("busca"),
    )
    return jsonify(resultado), status


@pagamentos_bp.route("", methods=["POST"])
def registrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = registrar_pagamento(dados)
    return jsonify(resultado), status


@pagamentos_bp.route("/cobrancas", methods=["GET"])
def cobrancas():
    resultado, status = listar_cobrancas(
        request.args.get("status"),
        pagina=ler_pagina(request.args.get("pagina")),
        busca=request.args.get("busca"),
        agrupar=request.args.get("agrupar") in ("1", "true", "True"),
    )
    return jsonify(resultado), status


@pagamentos_bp.route("/pendentes", methods=["GET"])
def pendentes():
    resultado, status = listar_saidas_pendentes(
        pagina=ler_pagina(request.args.get("pagina")),
        busca=request.args.get("busca"),
        id_movimentacao=request.args.get("id_movimentacao", type=int),
    )
    return jsonify(resultado), status


@pagamentos_bp.route("/resumo-dinheiro", methods=["GET"])
def dinheiro():
    resultado, status = resumo_dinheiro(request.args.get("data"))
    return jsonify(resultado), status
