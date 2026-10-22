
from flask import Blueprint, jsonify, request

from controllers.pagamentos_controller import (
    listar_cobrancas,
    listar_pagamentos,
    registrar_pagamento,
)

pagamentos_bp = Blueprint(
    "pagamentos", __name__, url_prefix="/api/pagamentos"
)


@pagamentos_bp.route("", methods=["GET"])
def listar():
    resultado, status = listar_pagamentos()
    return jsonify(resultado), status


@pagamentos_bp.route("", methods=["POST"])
def registrar():
    dados = request.get_json(silent=True) or {}
    resultado, status = registrar_pagamento(dados)
    return jsonify(resultado), status


@pagamentos_bp.route("/cobrancas", methods=["GET"])
def cobrancas():
    resultado, status = listar_cobrancas(request.args.get("status"))
    return jsonify(resultado), status
