"""Paginação das listas: 50 registros por página, carregados sob demanda (só a página pedida vai ao banco)."""
import re

POR_PAGINA = 50


def ler_pagina(valor):
    """Converte o parâmetro ?pagina= em inteiro >= 1. Sem o parâmetro (None) a lista não é paginada."""
    if valor in (None, ""):
        return None
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


def escapar_like(texto):
    """Escapa % e _ para a busca não tratar o que o usuário digitou como curinga."""
    return re.sub(r"([\\%_])", r"\\\1", texto or "")


def padrao_busca(busca):
    """Devolve (texto_com_curinga, digitos_com_curinga|None) para buscar por nome/código e por documento."""
    busca = " ".join((busca or "").split())
    if not busca:
        return None, None
    # Só procura em CPF/CNPJ quando a busca parece um documento (números e . - /); com letras, é busca por nome.
    digitos = re.sub(r"\D", "", busca) if re.fullmatch(r"[\d.\-/\s]+", busca) else ""
    return f"%{escapar_like(busca)}%", (f"%{digitos}%" if digitos else None)


def executar_paginado(cursor, sql_base, parametros, ordem, pagina, sql_total=None):
    """Executa a consulta. Com `pagina` traz só os 50 registros dela e o total; sem, traz tudo.

    `sql_base` termina antes do ORDER BY; `sql_total` (opcional) é um SELECT COUNT(*) equivalente
    (quando omitido, conta envolvendo `sql_base` em uma subconsulta).
    """
    if pagina is None:
        cursor.execute(f"{sql_base} ORDER BY {ordem}", parametros)
        return {"dados": cursor.fetchall()}

    if sql_total:
        cursor.execute(sql_total, parametros)
    else:
        cursor.execute(f"SELECT COUNT(*) AS total FROM ({sql_base}) AS t", parametros)
    total = cursor.fetchone()["total"]
    total_paginas = max(1, -(-total // POR_PAGINA))
    pagina = min(pagina, total_paginas)

    cursor.execute(
        f"{sql_base} ORDER BY {ordem} LIMIT %s OFFSET %s",
        tuple(parametros) + (POR_PAGINA, (pagina - 1) * POR_PAGINA),
    )
    return {
        "dados": cursor.fetchall(),
        "pagina": pagina,
        "por_pagina": POR_PAGINA,
        "total": total,
        "total_paginas": total_paginas,
    }
