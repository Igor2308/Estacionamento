"""Números do painel calculados no banco (o painel não precisa baixar todas as listas)."""
from config.database import conectar_banco
from utils.validators import TIPOS_VEICULO


def resumo_painel():
    conexao = conectar_banco()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS n FROM clientes WHERE ativo = TRUE")
        clientes_ativos = cursor.fetchone()["n"]

        cursor.execute("""
            SELECT tipo_veiculo,
                   SUM(tipo_vaga = 'ROTATIVA') AS rotativas,
                   SUM(tipo_vaga = 'MENSALISTA') AS mensalistas,
                   SUM(tipo_vaga = 'MENSALISTA' AND id_cliente IS NOT NULL) AS mensalistas_ocupadas
            FROM vagas
            WHERE ativa = TRUE
            GROUP BY tipo_veiculo
        """)
        vagas = {l["tipo_veiculo"]: l for l in cursor.fetchall()}

        cursor.execute("""
            SELECT COALESCE(ve.tipo_veiculo, 'CARRO') AS tipo_veiculo, COUNT(*) AS n
            FROM movimentacoes m
            LEFT JOIN clientes c ON c.id_cliente = m.id_cliente
            LEFT JOIN veiculos ve ON ve.id_veiculo = m.id_veiculo
            WHERE m.saida_em IS NULL AND (c.modalidade IS NULL OR c.modalidade <> 'MENSALISTA')
            GROUP BY COALESCE(ve.tipo_veiculo, 'CARRO')
        """)
        horistas = {l["tipo_veiculo"]: l["n"] for l in cursor.fetchall()}

        cursor.execute("""
            SELECT ve.tipo_veiculo, COUNT(*) AS n
            FROM movimentacoes m
            JOIN clientes c ON c.id_cliente = m.id_cliente AND c.modalidade = 'MENSALISTA'
            JOIN veiculos ve ON ve.id_veiculo = m.id_veiculo
            WHERE m.saida_em IS NULL
            GROUP BY ve.tipo_veiculo
        """)
        mensalistas_dentro = {l["tipo_veiculo"]: l["n"] for l in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) AS n FROM movimentacoes WHERE saida_em IS NULL")
        no_patio = cursor.fetchone()["n"]

        cursor.execute("""
            SELECT COALESCE(SUM(valor_pago), 0) AS total
            FROM pagamentos WHERE DATE(pago_em) = CURRENT_DATE
        """)
        recebido_hoje = cursor.fetchone()["total"]

        por_tipo = []
        for tipo in TIPOS_VEICULO:
            v = vagas.get(tipo) or {}
            rot = int(v.get("rotativas") or 0)
            men = int(v.get("mensalistas") or 0)
            reservadas = int(v.get("mensalistas_ocupadas") or 0)   # vagas vinculadas a algum cliente
            men_ocup = min(men, int(mensalistas_dentro.get(tipo, 0)))  # só conta quando há carro dentro
            rot_ocup = min(rot, int(horistas.get(tipo, 0)))
            por_tipo.append({
                "tipo": tipo, "total": rot + men, "rotativas": rot, "mensalistas": men,
                "mensalistas_vinculadas": reservadas, "mensalistas_ocupadas": men_ocup,
                "ocupadas": men_ocup + rot_ocup,
            })

        # Tarifa atual de cada tipo: a vigente; senão a mais recente que já começou; senão a mais antiga.
        cursor.execute("""
            SELECT *, (vigencia_inicio <= CURRENT_DATE
                       AND (vigencia_fim IS NULL OR vigencia_fim >= CURRENT_DATE)) AS vigente,
                   (vigencia_inicio <= CURRENT_DATE) AS ja_comecou
            FROM configuracoes_tarifas
            ORDER BY vigencia_inicio DESC, id_tarifa DESC
        """)
        todas = cursor.fetchall()
        tarifas = {}
        for tipo in TIPOS_VEICULO:
            ts = [t for t in todas if t["tipo_veiculo"] == tipo]
            escolhida = (next((t for t in ts if t["vigente"]), None)
                         or next((t for t in ts if t["ja_comecou"]), None)
                         or (ts[-1] if ts else None))
            if escolhida:
                tarifas[tipo] = {
                    "valor_periodo_30_min": str(escolhida["valor_periodo_30_min"]),
                    "mensalidade_por_vaga": str(escolhida["mensalidade_por_vaga"]),
                }

        return {
            "clientes_ativos": clientes_ativos,
            "veiculos_no_patio": no_patio,
            "recebido_hoje": str(recebido_hoje),
            "por_tipo": por_tipo,
            "tarifas": tarifas,
        }, 200

    finally:
        if cursor:
            cursor.close()
        conexao.close()
