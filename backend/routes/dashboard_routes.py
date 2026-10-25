from flask import Blueprint, jsonify

from controllers.dashboard_controller import resumo_painel

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/resumo", methods=["GET"])
def resumo():
    resultado, status = resumo_painel()
    return jsonify(resultado), status
