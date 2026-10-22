def test_api_raiz_responde(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert resposta.get_json()["mensagem"] == "API do Estacionamento funcionando!"


def test_sessao_sem_login_retorna_401(client):
    resposta = client.get("/api/auth/sessao")
    assert resposta.status_code == 401
    assert "erro" in resposta.get_json()


def test_rotas_principais_estao_registradas(app):
    regras = {regra.rule for regra in app.url_map.iter_rules()}
    assert "/api/clientes" in regras
    assert "/api/enderecos" in regras
    assert "/api/veiculos" in regras
    assert "/api/marcas" in regras
    assert "/api/modelos" in regras
    assert "/api/cores" in regras
    assert "/api/tarifas" in regras
    assert "/api/vagas" in regras
    assert "/api/movimentacoes/entrada" in regras
    assert "/api/pagamentos" in regras


# ---------- autenticação por sessão (telas protegidas no servidor) ----------
TELAS_PRIVADAS = ("dashboard", "clientes", "veiculos", "vagas", "movimentacoes", "pagamentos", "tarifas")


def test_telas_exigem_login_e_redirecionam(client):
    for tela in TELAS_PRIVADAS:
        r = client.get(f"/app/html/{tela}.html")
        assert r.status_code == 302 and r.headers["Location"].endswith("/app/html/login.html"), tela
    # maiúsculas/minúsculas não furam a proteção
    assert client.get("/app/html/DASHBOARD.html").status_code == 302


def test_tela_de_login_e_assets_sao_publicos(client):
    r = client.get("/app/html/login.html")
    assert r.status_code == 200 and b"<html" in r.data
    assert client.get("/app/js/main.js").status_code == 200
    assert client.get("/app/css/style.css").status_code == 200


def test_telas_e_api_nao_ficam_em_cache(client):
    for caminho in ("/app/html/login.html", "/api/auth/sessao"):
        assert "no-store" in client.get(caminho).headers["Cache-Control"], caminho


def test_api_sem_login_responde_401(client):
    for rota in ("/api/clientes", "/api/vagas", "/api/tarifas", "/api/pagamentos/cobrancas", "/api/movimentacoes/mensalistas"):
        assert client.get(rota).status_code == 401, rota


def test_abrir_a_tela_de_login_encerra_a_sessao(client):
    with client.session_transaction() as s:  # simula um usuário logado
        s["id_usuario"] = 1
        s["nome_usuario"] = "Teste"
    assert client.get("/app/html/dashboard.html").status_code == 200
    client.get("/app/html/login.html")  # ex.: voltou pela seta do navegador
    assert client.get("/app/html/dashboard.html").status_code == 302
    assert client.get("/api/auth/sessao").status_code == 401


def test_sessao_expira_por_inatividade(client):
    import time
    with client.session_transaction() as s:
        s["id_usuario"] = 1
        s["ultima_atividade"] = time.time() - 24 * 3600
    assert client.get("/app/html/dashboard.html").status_code == 302
    assert client.get("/api/auth/sessao").status_code == 401
