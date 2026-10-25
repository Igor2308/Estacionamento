"""Testes de integração: exigem MySQL com o schema carregado em um banco *_teste.

Rodar:  DB_NAME_TESTE=banco_estacionamento_teste DB_USER=... DB_PASSWORD=... pytest tests/test_integracao.py
"""
import itertools
import os
import threading

import pytest
from werkzeug.security import generate_password_hash

from config.database import conectar_banco
from app import criar_app
from utils.validators import _digito

NOME_BANCO = os.getenv("DB_NAME_TESTE", "")
pytestmark = pytest.mark.skipif(
    not NOME_BANCO.endswith("_teste"),
    reason="Defina DB_NAME_TESTE com um banco que termine em _teste.",
)

CPF_OK = "529.982.247-25"
CNPJ_OK = "11.222.333/0001-81"


def sql(comando, params=(), fetch=False):
    con = conectar_banco()
    cur = con.cursor(dictionary=True)
    cur.execute(comando, params)
    linhas = cur.fetchall() if fetch else None
    con.commit()
    cur.close()
    con.close()
    return linhas


@pytest.fixture(autouse=True)
def banco_limpo():
    con = conectar_banco()
    cur = con.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for tabela in ("cobrancas_mensalidade", "pagamentos", "movimentacoes", "vagas", "veiculos", "modelos", "marcas", "cores",
                   "enderecos", "clientes", "configuracoes_tarifas", "usuarios"):
        cur.execute(f"TRUNCATE TABLE {tabela}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    cur.execute(
        "INSERT INTO usuarios (nome, login, senha_hash) VALUES (%s, %s, %s)",
        ("Operador", "admin", generate_password_hash("senha123")),
    )
    cur.execute(
        "INSERT INTO configuracoes_tarifas "
        "(mensalidade_por_vaga, valor_periodo_30_min, vigencia_inicio, vigencia_fim) "
        "VALUES (300.00, 5.00, '2020-01-01', NULL)"
    )
    con.commit()
    cur.close()
    con.close()


def novo_cliente_http(app):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"login": "admin", "senha": "senha123"}).status_code == 200
    return c


@pytest.fixture
def api(app):
    return novo_cliente_http(app)


_seq = itertools.count(100000001)


def cpf_novo():
    """CPF válido e único para cada chamada."""
    base = f"{next(_seq):09d}"
    d1 = _digito(base, range(10, 1, -1))
    d2 = _digito(base + d1, range(11, 1, -1))
    return base + d1 + d2


ENDERECO = {"tipo_endereco": "RESIDENCIAL", "cep": "01001-000", "logradouro": "Rua A", "numero": "1",
            "bairro": "Centro", "cidade": "SP", "estado": "sp"}


def dados_cliente(**extra):
    """Cadastro de cliente completo (todos os obrigatórios + endereço)."""
    return {"nome": "Maria", "tipo_pessoa": "FISICA", "cpf": cpf_novo(), "telefone": "(11) 91234-5678",
            "modalidade": "HORISTA", "endereco": dict(ENDERECO), **extra}


def criar_cliente(api, **extra):
    r = api.post("/api/clientes", json=dados_cliente(**extra))
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id_cliente"]


def catalogo(api, marca="Fiat", modelo="Uno", cor="Verde"):
    """Cadastra (ou reaproveita) marca/modelo/cor e devolve os ids."""
    m = api.post("/api/marcas", json={"nome": marca}).get_json()["id_marca"]
    mo = api.post("/api/modelos", json={"id_marca": m, "nome": modelo}).get_json()["id_modelo"]
    c = api.post("/api/cores", json={"nome": cor}).get_json()["id_cor"]
    return {"id_marca": m, "id_modelo": mo, "id_cor": c}


def criar_veiculo(api, cid, placa, **extra):
    r = api.post("/api/veiculos", json={"id_cliente": cid, "placa": placa, **catalogo(api), **extra})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id_veiculo"]


def cliente_com_veiculo(api, placa, **extra):
    cid = criar_cliente(api, **extra)
    criar_veiculo(api, cid, placa)
    return cid


# ---------- segurança ----------
def test_api_exige_login(client):
    for rota in ("/api/clientes", "/api/vagas", "/api/pagamentos", "/api/movimentacoes"):
        assert client.get(rota).status_code == 401


def test_login_invalido_e_logout(client):
    assert client.post("/api/auth/login", json={"login": "admin", "senha": "errada"}).status_code == 401
    client.post("/api/auth/login", json={"login": "admin", "senha": "senha123"})
    assert client.get("/api/clientes").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/clientes").status_code == 401


# ---------- clientes / auditoria ----------
def test_cliente_registra_usuario_responsavel(api):
    id_cliente = criar_cliente(api, cpf=CPF_OK)
    linha = sql("SELECT cpf, cadastrado_por, atualizado_por FROM clientes WHERE id_cliente=%s",
                (id_cliente,), fetch=True)[0]
    assert linha["cpf"] == "52998224725"
    assert linha["cadastrado_por"] is not None and linha["atualizado_por"] is not None


def test_cpf_cnpj_invalidos(api):
    assert api.post("/api/clientes", json=dados_cliente(cpf="111.111.111-11")).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(tipo_pessoa="JURIDICA", cpf=None, cnpj="12.345.678/0001-00")).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(cnpj=CNPJ_OK)).status_code == 400  # PF não usa CNPJ
    assert api.post("/api/clientes", json=dados_cliente(nome="Empresa", tipo_pessoa="JURIDICA", cpf=None, cnpj=CNPJ_OK)).status_code == 201


def test_cpf_duplicado_retorna_409(api):
    criar_cliente(api, cpf=CPF_OK)
    r = api.post("/api/clientes", json=dados_cliente(nome="Outro", cpf=CPF_OK))
    assert r.status_code == 409


def test_cliente_exige_todos_os_campos_menos_email(api):
    sem_email = dados_cliente()
    assert api.post("/api/clientes", json=sem_email).status_code == 201  # e-mail é opcional
    for campo in ("nome", "cpf", "telefone", "modalidade", "endereco"):
        d = dados_cliente()
        d.pop(campo)
        r = api.post("/api/clientes", json=d)
        assert r.status_code == 400, (campo, r.get_json())
    for campo in ("cep", "logradouro", "numero", "bairro", "cidade", "estado"):
        d = dados_cliente()
        d["endereco"].pop(campo)
        r = api.post("/api/clientes", json=d)
        assert r.status_code == 400, (campo, r.get_json())
    d = dados_cliente(telefone="123")
    assert api.post("/api/clientes", json=d).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(email="sem-arroba")).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(email="a@b.com")).status_code == 201
    # complemento continua opcional
    assert api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "complemento": "ap 2"})).status_code == 201


def test_cliente_salva_com_endereco_principal_em_uma_so_operacao(api):
    cid = criar_cliente(api)
    ends = sql("SELECT principal, estado FROM enderecos WHERE id_cliente=%s", (cid,), fetch=True)
    assert len(ends) == 1 and ends[0]["principal"] == 1 and ends[0]["estado"] == "SP"


def test_endereco_invalido_nao_deixa_cliente_pela_metade(api):
    r = api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "estado": "Sao Paulo"}))
    assert r.status_code == 400
    assert sql("SELECT COUNT(*) n FROM clientes", fetch=True)[0]["n"] == 0


def test_editar_cliente_nao_aceita_apagar_campos_obrigatorios(api):
    cid = criar_cliente(api)
    assert api.put(f"/api/clientes/{cid}", json={"telefone": ""}).status_code == 400
    assert api.put(f"/api/clientes/{cid}", json={"cpf": ""}).status_code == 400
    assert api.put(f"/api/clientes/{cid}", json={"email": ""}).status_code == 200  # e-mail pode ficar vazio


# ---------- endereços ----------
def test_endereco_principal_unico(api):
    cid = criar_cliente(api)
    base = {**ENDERECO, "id_cliente": cid}
    a = api.post("/api/enderecos", json={**base, "principal": True}).get_json()["id_endereco"]
    b = api.post("/api/enderecos", json={**base, "numero": "2", "principal": True}).get_json()["id_endereco"]
    linhas = {l["id_endereco"]: l["principal"] for l in
              sql("SELECT id_endereco, principal FROM enderecos WHERE id_cliente=%s", (cid,), fetch=True)}
    assert linhas[a] == 0 and linhas[b] == 1  # o do cadastro do cliente também deixou de ser principal


# ---------- marcas / modelos / cores ----------
def test_catalogo_nao_duplica_nem_aceita_grafia_diferente(api):
    a = api.post("/api/cores", json={"nome": "Verde"})
    b = api.post("/api/cores", json={"nome": "  verde "})
    assert a.status_code == 201 and b.status_code == 200 and b.get_json()["ja_existia"] is True
    assert a.get_json()["id_cor"] == b.get_json()["id_cor"]
    assert len(api.get("/api/cores").get_json()["dados"]) == 1
    assert api.post("/api/cores", json={"nome": "   "}).status_code == 400
    assert api.post("/api/marcas", json={}).status_code == 400


def test_modelo_pertence_a_uma_marca(api):
    fiat = api.post("/api/marcas", json={"nome": "Fiat"}).get_json()["id_marca"]
    ford = api.post("/api/marcas", json={"nome": "Ford"}).get_json()["id_marca"]
    assert api.post("/api/modelos", json={"nome": "Uno"}).status_code == 400  # sem marca
    api.post("/api/modelos", json={"id_marca": fiat, "nome": "Uno"})
    api.post("/api/modelos", json={"id_marca": ford, "nome": "Ka"})
    assert [m["nome"] for m in api.get(f"/api/modelos?id_marca={fiat}").get_json()["dados"]] == ["Uno"]
    assert [m["nome"] for m in api.get(f"/api/modelos?id_marca={ford}").get_json()["dados"]] == ["Ka"]


# ---------- veículos ----------
def test_placa_validada_e_normalizada(api):
    cid = criar_cliente(api)
    cat = catalogo(api)
    assert api.post("/api/veiculos", json={"id_cliente": cid, "placa": "XXX", **cat}).status_code == 400
    r = api.post("/api/veiculos", json={"id_cliente": cid, "placa": "abc-1d23", "tipo_veiculo": "MOTO", **cat})
    assert r.status_code == 201
    assert sql("SELECT placa FROM veiculos", fetch=True)[0]["placa"] == "ABC1D23"
    assert api.post("/api/veiculos", json={"id_cliente": cid, "placa": "ABC1D23", **cat}).status_code == 409


def test_veiculo_exige_cliente_marca_modelo_e_cor_das_listas(api):
    cid = criar_cliente(api)
    cat = catalogo(api)
    assert api.post("/api/veiculos", json={"placa": "ABC1234", **cat}).status_code == 400  # sem cliente
    for campo in ("id_marca", "id_modelo", "id_cor"):
        d = {"id_cliente": cid, "placa": "ABC1234", **cat}
        d.pop(campo)
        assert api.post("/api/veiculos", json=d).status_code == 400, campo
    # texto livre / id inexistente não vale
    assert api.post("/api/veiculos", json={"id_cliente": cid, "placa": "ABC1234", **{**cat, "id_cor": 9999}}).status_code == 400
    assert api.post("/api/veiculos", json={"id_cliente": cid, "placa": "ABC1234", **{**cat, "id_cor": "verde"}}).status_code == 400
    # modelo de outra marca
    ford = api.post("/api/marcas", json={"nome": "Ford"}).get_json()["id_marca"]
    assert api.post("/api/veiculos", json={"id_cliente": cid, "placa": "ABC1234", **{**cat, "id_marca": ford}}).status_code == 400


def test_listagem_de_veiculos_traz_nomes_das_listas(api):
    cid = cliente_com_veiculo(api, "ABC1234")
    v = api.get(f"/api/veiculos?id_cliente={cid}").get_json()["dados"][0]
    assert (v["marca"], v["modelo"], v["cor"]) == ("Fiat", "Uno", "Verde")


def test_editar_veiculo_aceita_van_e_caminhao(api):
    cid = criar_cliente(api)
    vid = criar_veiculo(api, cid, "ABC1234")
    for tipo in ("VAN", "CAMINHAO"):
        assert api.put(f"/api/veiculos/{vid}", json={"tipo_veiculo": tipo}).status_code == 200
    assert api.put(f"/api/veiculos/{vid}", json={"tipo_veiculo": "BARCO"}).status_code == 400


def test_desativar_e_reativar_veiculo(api):
    cid = criar_cliente(api)
    vid = criar_veiculo(api, cid, "ABC1234")
    assert api.delete(f"/api/veiculos/{vid}").status_code == 200
    assert api.put(f"/api/veiculos/{vid}", json={"ativo": True}).status_code == 200


# ---------- vagas / mensalista ----------
def test_mensalista_sem_vaga_vinculada_nao_entra(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    criar_veiculo(api, cid, "AAA1111")
    r = api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"})
    assert r.status_code == 409 and "não tem vaga vinculada" in r.get_json()["erro"]
    assert sql("SELECT COUNT(*) n FROM movimentacoes", fetch=True)[0]["n"] == 0


def _vaga_vinculada(api, cid, codigo="M1", tipo="CARRO"):
    vid = api.post("/api/vagas", json={"codigo": codigo, "tipo_vaga": "MENSALISTA", "tipo_veiculo": tipo}).get_json()["id_vaga"]
    r = api.post(f"/api/vagas/{vid}/vincular", json={"id_cliente": cid})
    assert r.status_code == 200, r.get_json()
    return vid


def _abertas(api):
    return api.get("/api/pagamentos/cobrancas?status=ABERTA").get_json()["dados"]


def _pagar_abertas(api):
    # pagar uma mensalidade quita as do mesmo cliente e período; repete até não sobrar nada
    while _abertas(api):
        cb = _abertas(api)[0]
        r = api.post("/api/pagamentos", json={"tipo_pagamento": "MENSALIDADE", "forma_pagamento": "PIX",
                                              "id_cobranca": cb["id_cobranca"]})
        assert r.status_code == 201, r.get_json()


def test_vincular_vaga_gera_mensalidade_em_aberto(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    _vaga_vinculada(api, cid)
    abertas = _abertas(api)
    assert len(abertas) == 1 and abertas[0]["valor"] == "300.00" and abertas[0]["id_cliente"] == cid
    pg = {"tipo_pagamento": "MENSALIDADE", "forma_pagamento": "PIX", "id_cobranca": abertas[0]["id_cobranca"]}
    r = api.post("/api/pagamentos", json=pg)
    assert r.status_code == 201 and r.get_json()["valor_pago"] == "300.00"
    assert api.post("/api/pagamentos", json=pg).status_code == 409  # já paga
    assert _abertas(api) == []
    assert api.post("/api/pagamentos", json={**pg, "id_cobranca": None}).status_code == 400


def test_vincular_sem_tarifa_do_tipo_recusa(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    vid = api.post("/api/vagas", json={"codigo": "M1", "tipo_vaga": "MENSALISTA", "tipo_veiculo": "CAMINHAO"}).get_json()["id_vaga"]
    r = api.post(f"/api/vagas/{vid}/vincular", json={"id_cliente": cid})
    assert r.status_code == 409 and "caminhão" in r.get_json()["erro"]
    assert sql("SELECT id_cliente FROM vagas WHERE id_vaga=%s", (vid,), fetch=True)[0]["id_cliente"] is None


def test_cancelar_vaga_mensalista_e_por_vaga_e_exige_quitacao(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    v1 = _vaga_vinculada(api, cid, "M1")
    v2 = _vaga_vinculada(api, cid, "M2")
    lista = api.get("/api/movimentacoes/mensalistas").get_json()["dados"]
    assert {x["id_vaga"] for x in lista} == {v1, v2} and all(x["valor_em_aberto"] == "300.00" for x in lista)
    # com valor em aberto não cancela (nem pela saída, nem pelo botão desvincular da tela de vagas)
    r = api.post(f"/api/movimentacoes/mensalistas/vagas/{v1}/saida")
    assert r.status_code == 409 and "em aberto" in r.get_json()["erro"]
    assert api.post(f"/api/vagas/{v1}/desvincular").status_code == 409
    _pagar_abertas(api)
    # cancela só a vaga 1: a vaga 2 e a condição de mensalista continuam
    r = api.post(f"/api/movimentacoes/mensalistas/vagas/{v1}/saida")
    assert r.status_code == 200 and r.get_json()["plano_encerrado"] is False
    assert sql("SELECT id_cliente FROM vagas WHERE id_vaga=%s", (v1,), fetch=True)[0]["id_cliente"] is None
    assert sql("SELECT id_cliente FROM vagas WHERE id_vaga=%s", (v2,), fetch=True)[0]["id_cliente"] == cid
    assert sql("SELECT modalidade FROM clientes WHERE id_cliente=%s", (cid,), fetch=True)[0]["modalidade"] == "MENSALISTA"
    # cancelar a última vaga encerra o plano e o cliente vira horista
    r = api.post(f"/api/movimentacoes/mensalistas/vagas/{v2}/saida")
    assert r.status_code == 200 and r.get_json()["plano_encerrado"] is True
    assert sql("SELECT modalidade FROM clientes WHERE id_cliente=%s", (cid,), fetch=True)[0]["modalidade"] == "HORISTA"
    assert api.get("/api/movimentacoes/mensalistas").get_json()["dados"] == []
    assert api.post(f"/api/movimentacoes/mensalistas/vagas/{v2}/saida").status_code == 409  # já livre
    assert api.post("/api/movimentacoes/mensalistas/vagas/999999/saida").status_code == 404


def test_mes_novo_gera_nova_mensalidade_em_aberto(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    vid = _vaga_vinculada(api, cid)
    _pagar_abertas(api)
    # simula que o período pago terminou há 10 dias
    sql("UPDATE cobrancas_mensalidade SET competencia_inicio = CURRENT_DATE - INTERVAL 40 DAY, "
        "competencia_fim = CURRENT_DATE - INTERVAL 10 DAY")
    abertas = _abertas(api)
    assert len(abertas) == 1 and abertas[0]["id_vaga"] == vid
    assert api.post(f"/api/movimentacoes/mensalistas/vagas/{vid}/saida").status_code == 409
    _pagar_abertas(api)
    assert api.post(f"/api/movimentacoes/mensalistas/vagas/{vid}/saida").status_code == 200


def test_vaga_exige_tipo_de_veiculo(api):
    assert api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA"}).status_code == 400
    assert api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "BARCO"}).status_code == 400
    assert api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "MOTO"}).status_code == 201
    assert sql("SELECT tipo_veiculo FROM vagas WHERE codigo='R1'", fetch=True)[0]["tipo_veiculo"] == "MOTO"


def test_entrada_respeita_o_tipo_de_veiculo_da_vaga(api):
    cid = criar_cliente(api)
    criar_veiculo(api, cid, "MOT1A23", tipo_veiculo="MOTO")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    r = api.post("/api/movimentacoes/entrada", json={"placa": "MOT1A23"})  # só existe vaga de carro
    assert r.status_code == 409 and "moto" in r.get_json()["erro"]
    api.post("/api/vagas", json={"codigo": "R2", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "MOTO"})
    assert api.post("/api/movimentacoes/entrada", json={"placa": "MOT1A23"}).status_code == 201


def test_vaga_rotativa_nao_vincula_e_horista_nao_usa_mensalista(api):
    cid = cliente_com_veiculo(api, "ZZZ9999")
    rot = api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"}).get_json()["id_vaga"]
    assert api.post(f"/api/vagas/{rot}/vincular", json={"id_cliente": cid}).status_code == 400
    api.post("/api/vagas", json={"codigo": "M1", "tipo_vaga": "MENSALISTA", "tipo_veiculo": "CARRO"})
    # só existe vaga mensalista livre -> horista não pode ocupá-la
    api.post(f"/api/vagas/{rot}/status", json={"ativa": False})
    api.patch(f"/api/vagas/{rot}/status", json={"ativa": False})
    assert api.post("/api/movimentacoes/entrada", json={"placa": "ZZZ9999"}).status_code == 409


# ---------- horista: entrada, saída, cobrança, pagamento ----------
def test_horista_cobranca_por_periodo_iniciado(api):
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    r = api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"})
    assert r.status_code == 201
    mid = r.get_json()["id_movimentacao"]
    assert api.post("/api/movimentacoes/entrada", json={"placa": "abc-1234"}).status_code == 409  # duplicada
    sql("UPDATE movimentacoes SET entrada_em = NOW() - INTERVAL 31 MINUTE WHERE id_movimentacao=%s", (mid,))
    s = api.post(f"/api/movimentacoes/{mid}/saida").get_json()
    assert s["periodos_cobrados"] == 2 and s["valor_total"] == "10.00"
    assert api.post(f"/api/movimentacoes/{mid}/saida").status_code == 409
    pg = {"tipo_pagamento": "HORISTA", "forma_pagamento": "PIX", "id_movimentacao": mid}
    assert api.post("/api/pagamentos", json=pg).status_code == 201
    assert api.post("/api/pagamentos", json=pg).status_code == 409  # duplicado


def test_saida_funciona_no_ultimo_dia_da_vigencia(api):
    """Regressão: vigencia_fim = hoje não pode derrubar a tarifa."""
    sql("UPDATE configuracoes_tarifas SET vigencia_fim = CURRENT_DATE")
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    mid = api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"}).get_json()["id_movimentacao"]
    assert api.post(f"/api/movimentacoes/{mid}/saida").status_code == 200


def test_entrada_com_placa_invalida(api):
    assert api.post("/api/movimentacoes/entrada", json={"placa": "123"}).status_code == 400


def test_entrada_so_aceita_placa_cadastrada(api):
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    r = api.post("/api/movimentacoes/entrada", json={"placa": "QWE1R23"})  # válida, mas ninguém cadastrou
    assert r.status_code == 404 and "não cadastrada" in r.get_json()["erro"]
    assert sql("SELECT COUNT(*) n FROM movimentacoes", fetch=True)[0]["n"] == 0
    cliente_com_veiculo(api, "QWE1R23")
    assert api.post("/api/movimentacoes/entrada", json={"placa": "qwe-1r23"}).status_code == 201


def test_entrada_recusa_veiculo_inativo(api):
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    cid = criar_cliente(api)
    vid = criar_veiculo(api, cid, "ABC1234")
    api.delete(f"/api/veiculos/{vid}")
    assert api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"}).status_code == 400


# ---------- tarifas (regressão do "não existe tarifa horista vigente") ----------
def _saida_apos_um_dia(api):
    """Entrada há ~24h (23h45 = 48 períodos de 30 min, com folga para não depender de segundos)."""
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    mid = api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"}).get_json()["id_movimentacao"]
    sql("UPDATE movimentacoes SET entrada_em = NOW() - INTERVAL 1425 MINUTE WHERE id_movimentacao=%s", (mid,))
    return mid


def test_saida_com_tarifa_que_comecou_hoje_apos_entrada_de_ontem(api):
    sql("UPDATE configuracoes_tarifas SET vigencia_inicio = CURRENT_DATE")
    mid = _saida_apos_um_dia(api)
    r = api.post(f"/api/movimentacoes/{mid}/saida")
    assert r.status_code == 200 and r.get_json()["periodos_cobrados"] == 48


def test_saida_usa_ultima_tarifa_se_a_vigencia_acabou(api):
    sql("UPDATE configuracoes_tarifas SET vigencia_fim = '2020-12-31'")
    mid = _saida_apos_um_dia(api)
    assert api.post(f"/api/movimentacoes/{mid}/saida").status_code == 200


def test_saida_sem_nenhuma_tarifa_orienta_a_cadastrar(api):
    sql("TRUNCATE TABLE configuracoes_tarifas")
    mid = _saida_apos_um_dia(api)
    r = api.post(f"/api/movimentacoes/{mid}/saida")
    assert r.status_code == 409 and "Tarifas" in r.get_json()["erro"]
    assert api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "4,00", "mensalidade_por_vaga": "250",
                                          "vigencia_inicio": "2026-01-01"}).status_code == 201
    r = api.post(f"/api/movimentacoes/{mid}/saida")
    assert r.status_code == 200 and r.get_json()["valor_total"] == "192.00"  # 48 x 4,00


def test_nova_tarifa_encerra_a_anterior_e_valida_dados(api):
    r = api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "6", "mensalidade_por_vaga": "350", "vigencia_inicio": "2026-06-01"})
    assert r.status_code == 201
    linhas = sql("SELECT vigencia_inicio, vigencia_fim FROM configuracoes_tarifas ORDER BY vigencia_inicio", fetch=True)
    assert str(linhas[0]["vigencia_fim"]) == "2026-05-31" and linhas[1]["vigencia_fim"] is None
    assert api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "6", "mensalidade_por_vaga": "350", "vigencia_inicio": "2026-06-01"}).status_code == 409
    assert api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "abc", "mensalidade_por_vaga": "350", "vigencia_inicio": "2026-07-01"}).status_code == 400
    assert api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "6", "mensalidade_por_vaga": "350", "vigencia_inicio": "x"}).status_code == 400
    assert len(api.get("/api/tarifas").get_json()["dados"]) == 2


def test_tarifa_por_tipo_de_veiculo(api):
    r = api.post("/api/tarifas", json={"tipo_veiculo": "MOTO", "valor_periodo_30_min": "2", "mensalidade_por_vaga": "100",
                                       "vigencia_inicio": "2026-06-01"})
    assert r.status_code == 201
    # a tarifa de carro (2020, em aberto) NÃO é encerrada pela de moto
    carro = sql("SELECT vigencia_fim FROM configuracoes_tarifas WHERE tipo_veiculo='CARRO'", fetch=True)[0]
    assert carro["vigencia_fim"] is None
    assert api.post("/api/tarifas", json={"valor_periodo_30_min": "2", "mensalidade_por_vaga": "100",
                                          "vigencia_inicio": "2026-07-01"}).status_code == 400  # sem tipo
    # moto cobra pela tarifa de moto
    cid = criar_cliente(api)
    criar_veiculo(api, cid, "MOT1A23", tipo_veiculo="MOTO")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "MOTO"})
    mid = api.post("/api/movimentacoes/entrada", json={"placa": "MOT1A23"}).get_json()["id_movimentacao"]
    s = api.post(f"/api/movimentacoes/{mid}/saida").get_json()
    assert s["valor_periodo_aplicado"] == "2.00"


def test_saida_de_tipo_sem_tarifa_orienta_a_cadastrar(api):
    cid = criar_cliente(api)
    criar_veiculo(api, cid, "CAM1A23", tipo_veiculo="CAMINHAO")  # só existe tarifa de carro
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CAMINHAO"})
    mid = api.post("/api/movimentacoes/entrada", json={"placa": "CAM1A23"}).get_json()["id_movimentacao"]
    r = api.post(f"/api/movimentacoes/{mid}/saida")
    assert r.status_code == 409 and "caminhão" in r.get_json()["erro"]


def test_corrida_na_entrada_nao_ultrapassa_capacidade(app):
    sql("INSERT INTO vagas (codigo, tipo_vaga) VALUES ('R1', 'ROTATIVA')")
    clientes = [novo_cliente_http(app) for _ in range(8)]
    resultados = []

    def entrar(c, placa):
        resultados.append(c.post("/api/movimentacoes/entrada", json={"placa": placa}).status_code)

    placas = [f"AAA{i}{i}{i}{i}" for i in range(8)]
    for p in placas:
        cliente_com_veiculo(clientes[0], p)
    threads = [threading.Thread(target=entrar, args=(c, p)) for c, p in zip(clientes, placas)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(resultados) == 8, "alguma requisição quebrou (erro/deadlock)"
    assert all(r in (201, 409) for r in resultados), resultados
    assert resultados.count(201) == 1, resultados
    assert sql("SELECT COUNT(*) n FROM movimentacoes WHERE saida_em IS NULL", fetch=True)[0]["n"] == 1


# ---------- mensalidade ----------
def test_mensalidade_de_cada_vaga_usa_a_tarifa_do_tipo(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    sql("INSERT INTO configuracoes_tarifas (tipo_veiculo, mensalidade_por_vaga, valor_periodo_30_min, vigencia_inicio) "
        "VALUES ('MOTO', 100.00, 2.00, '2020-01-01')")
    _vaga_vinculada(api, cid, "M1", "CARRO")
    _vaga_vinculada(api, cid, "M2", "MOTO")
    assert sorted(x["valor"] for x in _abertas(api)) == ["100.00", "300.00"]


def test_nao_desativa_cliente_com_veiculo_dentro_ou_vaga(api):
    cid = criar_cliente(api, modalidade="MENSALISTA")
    criar_veiculo(api, cid, "AAA1111")
    vid = _vaga_vinculada(api, cid, "M1")
    assert api.delete(f"/api/clientes/{cid}").status_code == 409
    _pagar_abertas(api)
    api.post(f"/api/vagas/{vid}/desvincular")
    assert api.delete(f"/api/clientes/{cid}").status_code == 200


def test_vigencia_de_tarifa_cadastrada_antes_de_outra_agendada(api):
    """Regressão: tarifa do dia 24 cadastrada depois da do dia 25 deve terminar no dia 24."""
    def nova(inicio):
        r = api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "valor_periodo_30_min": "6",
                                           "mensalidade_por_vaga": "350", "vigencia_inicio": inicio})
        assert r.status_code == 201, r.get_json()
    nova("2026-12-25")
    nova("2026-12-24")
    linhas = sql("SELECT vigencia_inicio, vigencia_fim FROM configuracoes_tarifas "
                 "WHERE tipo_veiculo='CARRO' ORDER BY vigencia_inicio", fetch=True)
    fins = [str(x["vigencia_fim"]) if x["vigencia_fim"] else None for x in linhas]
    assert fins == ["2026-12-23", "2026-12-24", None], fins


def test_horista_abertas_traz_tempo_em_segundos_do_servidor(api):
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"})
    abertas = api.get("/api/movimentacoes/abertas").get_json()["dados"]
    assert len(abertas) == 1 and 0 <= abertas[0]["segundos_no_patio"] <= 10  # não começa em 3 horas


def test_paginas_do_frontend_sao_servidas(api):
    """Logado, todas as telas abrem; os scripts continuam públicos."""
    # a tela de login encerra a sessão ao abrir, então ela é a última
    for pagina in ("dashboard", "clientes", "veiculos", "vagas", "movimentacoes", "pagamentos", "tarifas", "login"):
        r = api.get(f"/app/html/{pagina}.html")
        assert r.status_code == 200 and b"<html" in r.data, pagina
    for arq in ("main", "ui", "clientes", "veiculos", "vagas", "movimentacoes", "pagamentos", "dashboard", "tarifas"):
        assert api.get(f"/app/js/{arq}.js").status_code == 200, arq


def test_logout_e_voltar_para_o_login_exigem_novo_login(api):
    assert api.get("/api/clientes").status_code == 200
    api.get("/app/html/login.html")  # voltou pela seta do navegador: não pode continuar logado
    assert api.get("/api/clientes").status_code == 401
    assert api.get("/app/html/dashboard.html").status_code == 302
    assert api.post("/api/auth/login", json={"login": "admin", "senha": "senha123"}).status_code == 200
    assert api.get("/app/html/dashboard.html").status_code == 200
    api.post("/api/auth/logout")
    assert api.get("/app/html/dashboard.html").status_code == 302


# =====================================================================================
# Novidades: validações, paginação/busca, vaga no cadastro, país, troco e "quem registrou"
# =====================================================================================
def test_validacoes_de_formato_no_cadastro_do_cliente(api):
    assert api.post("/api/clientes", json=dados_cliente(telefone="(11) 9abcd-5678")).status_code == 400  # letras
    assert api.post("/api/clientes", json=dados_cliente(cpf="529.982.247-2a")).status_code == 400          # letra no CPF
    assert api.post("/api/clientes", json=dados_cliente(nome="Maria 123")).status_code == 400              # número no nome
    assert api.post("/api/clientes", json=dados_cliente(telefone="(11) 51234-5678")).status_code == 400   # celular sem 9
    assert api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "estado": "XX"})).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "estado": "S1"})).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "cep": "0100100a"})).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(endereco={**ENDERECO, "cidade": "S4o Paulo"})).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente()).status_code == 201


def test_telefone_e_cep_sao_guardados_normalizados(api):
    cid = criar_cliente(api, endereco={**ENDERECO, "cep": "01001000"})
    c = sql("SELECT telefone FROM clientes WHERE id_cliente=%s", (cid,), fetch=True)[0]
    e = sql("SELECT cep, pais FROM enderecos WHERE id_cliente=%s", (cid,), fetch=True)[0]
    assert c["telefone"] == "11912345678"
    assert e["cep"] == "01001-000" and e["pais"] == "Brasil"


def test_endereco_com_pais_estrangeiro(api):
    cid = criar_cliente(api)
    base = {**ENDERECO, "id_cliente": cid, "pais": "Portugal", "cep": "1100-148", "estado": "LX", "cidade": "Lisboa"}
    assert api.post("/api/enderecos", json=base).status_code == 201
    assert api.post("/api/enderecos", json={**base, "pais": "Portugal 2"}).status_code == 400
    # no Brasil o CEP precisa ter 8 dígitos e a UF precisa existir
    assert api.post("/api/enderecos", json={**base, "pais": "Brasil"}).status_code == 400
    ends = api.get(f"/api/enderecos?id_cliente={cid}").get_json()["dados"]
    assert sorted(e["pais"] for e in ends) == ["Brasil", "Portugal"]
    # atualizar só o CEP de um endereço estrangeiro usa a regra do país já salvo
    id_pt = [e["id_endereco"] for e in ends if e["pais"] == "Portugal"][0]
    assert api.put(f"/api/enderecos/{id_pt}", json={"cep": "4000-001"}).status_code == 200
    assert api.put(f"/api/enderecos/{id_pt}", json={"pais": "Brasil"}).status_code == 400


def test_nao_deixa_excluir_o_ultimo_endereco_e_promove_outro_principal(api):
    cid = criar_cliente(api)
    unico = api.get(f"/api/enderecos?id_cliente={cid}").get_json()["dados"][0]["id_endereco"]
    assert api.delete(f"/api/enderecos/{unico}").status_code == 409
    outro = api.post("/api/enderecos", json={**ENDERECO, "id_cliente": cid, "numero": "2"}).get_json()["id_endereco"]
    assert api.delete(f"/api/enderecos/{unico}").status_code == 200
    restante = sql("SELECT id_endereco, principal FROM enderecos WHERE id_cliente=%s", (cid,), fetch=True)
    assert restante[0]["id_endereco"] == outro and restante[0]["principal"] == 1


def test_cpf_cnpj_e_tipo_nao_podem_ser_alterados(api):
    cid = criar_cliente(api, cpf=CPF_OK)
    assert api.put(f"/api/clientes/{cid}", json={"cpf": cpf_novo()}).status_code == 400
    assert api.put(f"/api/clientes/{cid}", json={"tipo_pessoa": "JURIDICA"}).status_code == 400
    # mandar o mesmo CPF (como a tela pode fazer) é ignorado e o resto é salvo
    r = api.put(f"/api/clientes/{cid}", json={"cpf": "529.982.247-25", "nome": "Maria Souza"})
    assert r.status_code == 200
    linha = sql("SELECT cpf, nome FROM clientes WHERE id_cliente=%s", (cid,), fetch=True)[0]
    assert linha["cpf"] == "52998224725" and linha["nome"] == "Maria Souza"


def test_listas_paginadas_50_por_pagina_e_busca_por_nome_ou_cpf(api):
    con = conectar_banco(); cur = con.cursor()
    for i in range(120):
        cur.execute("INSERT INTO clientes (nome, tipo_pessoa, cpf, telefone, modalidade) VALUES (%s,'FISICA',%s,'11912345678','HORISTA')",
                    (f"Cliente {i:03d}", cpf_novo()))
    con.commit(); cur.close(); con.close()

    p1 = api.get("/api/clientes?pagina=1").get_json()
    assert len(p1["dados"]) == 50 and p1["total"] == 120 and p1["total_paginas"] == 3 and p1["pagina"] == 1
    p3 = api.get("/api/clientes?pagina=3").get_json()
    assert len(p3["dados"]) == 20 and p3["dados"][0]["nome"] == "Cliente 100"
    assert api.get("/api/clientes?pagina=99").get_json()["pagina"] == 3          # página inexistente vai para a última
    assert len(api.get("/api/clientes").get_json()["dados"]) == 120              # sem pagina: lista completa (compatível)

    por_nome = api.get("/api/clientes?pagina=1&busca=cliente 05").get_json()
    assert por_nome["total"] == 10 and all("Cliente 05" in c["nome"] for c in por_nome["dados"])
    cpf = api.get("/api/clientes?pagina=2").get_json()["dados"][0]["cpf"]
    formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    por_cpf = api.get(f"/api/clientes?pagina=1&busca={formatado}").get_json()
    assert por_cpf["total"] == 1 and por_cpf["dados"][0]["cpf"] == cpf
    assert api.get("/api/clientes?pagina=1&busca=%25").get_json()["total"] == 0   # % não vira curinga


def test_busca_de_veiculos_por_placa_e_cliente(api):
    cliente_com_veiculo(api, "ABC1234", nome="Joana Lima")
    cliente_com_veiculo(api, "XYZ9A87", nome="Pedro Alves")
    r = api.get("/api/veiculos?pagina=1&busca=xyz").get_json()
    assert r["total"] == 1 and r["dados"][0]["placa"] == "XYZ9A87"
    r = api.get("/api/veiculos?pagina=1&busca=joana").get_json()
    assert r["total"] == 1 and r["dados"][0]["placa"] == "ABC1234"
    assert api.get("/api/veiculos?pagina=1&ativo=1&modalidade=HORISTA").get_json()["total"] == 2


def test_cadastro_de_mensalista_ja_vincula_a_vaga_escolhida(api):
    vid = api.post("/api/vagas", json={"codigo": "M1", "tipo_vaga": "MENSALISTA", "tipo_veiculo": "CARRO"}).get_json()["id_vaga"]
    livres = api.get("/api/vagas?livres=1&pagina=1").get_json()
    assert livres["total"] == 1
    r = api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vaga=vid))
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["id_cliente"]
    assert sql("SELECT id_cliente FROM vagas WHERE id_vaga=%s", (vid,), fetch=True)[0]["id_cliente"] == cid
    assert len(api.get("/api/pagamentos/cobrancas?status=ABERTA").get_json()["dados"]) == 1  # mensalidade já gerada
    assert api.get("/api/vagas?livres=1&pagina=1").get_json()["total"] == 0


def test_cadastro_com_vaga_invalida_nao_deixa_cliente_pela_metade(api):
    vid = api.post("/api/vagas", json={"codigo": "M1", "tipo_vaga": "MENSALISTA", "tipo_veiculo": "CARRO"}).get_json()["id_vaga"]
    assert api.post("/api/clientes", json=dados_cliente(modalidade="HORISTA", id_vaga=vid)).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vaga=999999)).status_code == 404
    rot = api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"}).get_json()["id_vaga"]
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vaga=rot)).status_code == 400
    assert sql("SELECT COUNT(*) n FROM clientes", fetch=True)[0]["n"] == 0
    assert sql("SELECT COUNT(*) n FROM enderecos", fetch=True)[0]["n"] == 0
    # vaga já ocupada
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vaga=vid)).status_code == 201
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vaga=vid)).status_code == 409
    assert sql("SELECT COUNT(*) n FROM clientes", fetch=True)[0]["n"] == 1


def test_vagas_validam_codigo_e_setor(api):
    assert api.post("/api/vagas", json={"codigo": "A 1!", "tipo_veiculo": "CARRO"}).status_code == 400
    assert api.post("/api/vagas", json={"codigo": "A1", "setor": "@@", "tipo_veiculo": "CARRO"}).status_code == 400
    assert api.post("/api/vagas", json={"codigo": "a-1", "setor": "Bloco A", "tipo_veiculo": "CARRO"}).status_code == 201
    assert api.get("/api/vagas?pagina=1&busca=bloco").get_json()["total"] == 1


def test_telas_mostram_quem_registrou_e_quando(api):
    cid = criar_cliente(api)
    criar_veiculo(api, cid, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    api.post("/api/tarifas", json={"tipo_veiculo": "CARRO", "mensalidade_por_vaga": "310", "valor_periodo_30_min": "6", "vigencia_inicio": "2031-01-01"})
    ent = api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"}).get_json()["id_movimentacao"]
    api.post(f"/api/movimentacoes/{ent}/saida")
    for rota in ("/api/veiculos", "/api/vagas", "/api/tarifas"):
        linha = api.get(rota + "?pagina=1").get_json()["dados"][0]
        assert linha["cadastrado_por_nome"] == "Operador" and linha["cadastrado_em"], rota
    mov = api.get("/api/movimentacoes?fechadas=1&pagina=1").get_json()["dados"][0]
    assert mov["entrada_por_nome"] == "Operador" and mov["saida_por_nome"] == "Operador"
    api.post("/api/pagamentos", json={"tipo_pagamento": "OUTRO", "valor_pago": "10", "forma_pagamento": "PIX"})
    assert api.get("/api/pagamentos?pagina=1").get_json()["dados"][0]["cadastrado_por_nome"] == "Operador"


def test_pagamento_em_dinheiro_exige_valor_recebido_e_calcula_troco(api):
    base = {"tipo_pagamento": "OUTRO", "valor_pago": "37,50", "forma_pagamento": "DINHEIRO"}
    assert api.post("/api/pagamentos", json=base).status_code == 400                                  # sem valor recebido
    assert api.post("/api/pagamentos", json={**base, "valor_recebido": "30"}).status_code == 400     # entregou menos
    assert api.post("/api/pagamentos", json={**base, "valor_recebido": "abc"}).status_code == 400
    r = api.post("/api/pagamentos", json={**base, "valor_recebido": "50,00"})
    assert r.status_code == 201 and r.get_json()["troco"] == "12.50"
    linha = sql("SELECT valor_pago, valor_recebido, troco FROM pagamentos", fetch=True)[0]
    assert (float(linha["valor_pago"]), float(linha["valor_recebido"]), float(linha["troco"])) == (37.5, 50.0, 12.5)
    # outras formas não guardam recebido/troco
    r = api.post("/api/pagamentos", json={"tipo_pagamento": "OUTRO", "valor_pago": "5", "forma_pagamento": "PIX", "valor_recebido": "99"})
    assert r.status_code == 201 and r.get_json()["troco"] is None


def test_resumo_do_dinheiro_fisico_do_dia(api):
    api.post("/api/pagamentos", json={"tipo_pagamento": "OUTRO", "valor_pago": "37,50", "forma_pagamento": "DINHEIRO", "valor_recebido": "50"})
    api.post("/api/pagamentos", json={"tipo_pagamento": "OUTRO", "valor_pago": "10", "forma_pagamento": "DINHEIRO", "valor_recebido": "10"})
    api.post("/api/pagamentos", json={"tipo_pagamento": "OUTRO", "valor_pago": "99", "forma_pagamento": "PIX"})
    r = api.get("/api/pagamentos/resumo-dinheiro").get_json()
    assert (r["quantidade"], float(r["recebido"]), float(r["troco"]), float(r["liquido"])) == (2, 60.0, 12.5, 47.5)


def test_pagamento_horista_em_dinheiro_e_lista_de_pendentes(api):
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    ent = api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"}).get_json()["id_movimentacao"]
    api.post(f"/api/movimentacoes/{ent}/saida")
    pend = api.get("/api/pagamentos/pendentes?pagina=1&busca=abc").get_json()
    assert pend["total"] == 1 and pend["dados"][0]["id_movimentacao"] == ent
    assert api.get(f"/api/pagamentos/pendentes?id_movimentacao={ent}").get_json()["dados"][0]["placa_registrada"] == "ABC1234"
    r = api.post("/api/pagamentos", json={"tipo_pagamento": "HORISTA", "id_movimentacao": ent, "forma_pagamento": "DINHEIRO", "valor_recebido": "20"})
    assert r.status_code == 201 and r.get_json()["troco"] == "15.00"      # 1 período de R$ 5,00
    assert api.get("/api/pagamentos/pendentes?pagina=1").get_json()["total"] == 0


def test_resumo_do_painel_vem_pronto_do_servidor(api):
    cliente_com_veiculo(api, "ABC1234")
    api.post("/api/vagas", json={"codigo": "R1", "tipo_vaga": "ROTATIVA", "tipo_veiculo": "CARRO"})
    api.post("/api/movimentacoes/entrada", json={"placa": "ABC1234"})
    r = api.get("/api/dashboard/resumo").get_json()
    carro = [t for t in r["por_tipo"] if t["tipo"] == "CARRO"][0]
    assert r["clientes_ativos"] == 1 and r["veiculos_no_patio"] == 1
    assert carro["total"] == 1 and carro["ocupadas"] == 1 and r["tarifas"]["CARRO"]["valor_periodo_30_min"] == "5.00"


# =====================================================================================
# Mensalista: várias vagas no cadastro, cobrança somada e entrada/saída controlada por vaga
# =====================================================================================
def _vaga(api, codigo, tipo="CARRO", tipo_vaga="MENSALISTA"):
    r = api.post("/api/vagas", json={"codigo": codigo, "tipo_vaga": tipo_vaga, "tipo_veiculo": tipo})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id_vaga"]


def _mensalista_com_vagas(api, placas, n_vagas, tipo="CARRO"):
    vagas = [_vaga(api, f"M{i + 1}", tipo) for i in range(n_vagas)]
    r = api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vagas=vagas))
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["id_cliente"]
    for placa in placas:
        criar_veiculo(api, cid, placa, tipo_veiculo=tipo)
    return cid, vagas


def test_cadastro_de_mensalista_com_varias_vagas_gera_o_valor_de_todas(api):
    cid, vagas = _mensalista_com_vagas(api, [], 2)
    donos = sql("SELECT id_cliente FROM vagas", fetch=True)
    assert [d["id_cliente"] for d in donos] == [cid, cid]
    assert len(_abertas(api)) == 2                                   # uma cobrança por vaga...
    grupo = api.get("/api/pagamentos/cobrancas?status=ABERTA&agrupar=1&pagina=1").get_json()["dados"]
    assert len(grupo) == 1 and grupo[0]["quantidade_vagas"] == 2     # ...mas o cliente vê uma linha só
    assert grupo[0]["valor"] == "600.00" and grupo[0]["codigo_vaga"] == "M1, M2"
    r = api.post("/api/pagamentos", json={"tipo_pagamento": "MENSALIDADE", "forma_pagamento": "PIX",
                                          "id_cobranca": grupo[0]["id_cobranca"]})
    assert r.status_code == 201 and r.get_json()["valor_pago"] == "600.00" and r.get_json()["quantidade_vagas_cobradas"] == 2
    assert _abertas(api) == []
    p = sql("SELECT quantidade_vagas_cobradas, valor_unitario_aplicado, valor_pago FROM pagamentos", fetch=True)[0]
    assert p["quantidade_vagas_cobradas"] == 2 and float(p["valor_unitario_aplicado"]) == 300.0


def test_cadastro_com_varias_vagas_e_tudo_ou_nada(api):
    v1, v2 = _vaga(api, "M1"), _vaga(api, "M2")
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vagas=[v1, v1])).status_code == 400
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vagas=[v1, 999999])).status_code == 404
    assert api.post("/api/clientes", json=dados_cliente(modalidade="HORISTA", id_vagas=[v1])).status_code == 400
    assert sql("SELECT COUNT(*) n FROM clientes", fetch=True)[0]["n"] == 0
    assert sql("SELECT COUNT(*) n FROM vagas WHERE id_cliente IS NOT NULL", fetch=True)[0]["n"] == 0
    assert api.post("/api/clientes", json=dados_cliente(modalidade="MENSALISTA", id_vagas=[v1, v2])).status_code == 201


def test_mensalista_entra_e_sai_sem_cobranca_por_entrada(api):
    cid, _ = _mensalista_com_vagas(api, ["AAA1111"], 1)
    r = api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"})
    assert r.status_code == 201 and r.get_json()["modalidade"] == "MENSALISTA"
    mid = r.get_json()["id_movimentacao"]
    dentro = api.get("/api/movimentacoes/abertas?apenas_mensalistas=1&pagina=1").get_json()
    assert dentro["total"] == 1 and api.get("/api/movimentacoes/abertas?apenas_horistas=1&pagina=1").get_json()["total"] == 0
    s = api.post(f"/api/movimentacoes/{mid}/saida")
    assert s.status_code == 200 and float(s.get_json()["valor_total"]) == 0
    assert api.get("/api/pagamentos/pendentes?pagina=1").get_json()["total"] == 0   # nada a cobrar na saída


def test_cada_vaga_comporta_um_carro_do_mensalista_por_vez(api):
    cid, _ = _mensalista_com_vagas(api, ["AAA1111", "BBB2222", "CCC3333"], 2)
    e1 = api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"})
    e2 = api.post("/api/movimentacoes/entrada", json={"placa": "BBB2222"})
    assert e1.status_code == 201 and e2.status_code == 201
    r = api.post("/api/movimentacoes/entrada", json={"placa": "CCC3333"})          # terceiro carro, só 2 vagas
    assert r.status_code == 409 and "Todas as 2 vaga(s)" in r.get_json()["erro"] and "AAA1111" in r.get_json()["erro"]
    assert api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"}).status_code == 409  # mesma placa já dentro
    api.post(f"/api/movimentacoes/{e1.get_json()['id_movimentacao']}/saida")      # libera uma vaga
    assert api.post("/api/movimentacoes/entrada", json={"placa": "CCC3333"}).status_code == 201


def test_mensalista_so_entra_com_veiculo_do_tipo_da_sua_vaga(api):
    cid, _ = _mensalista_com_vagas(api, ["AAA1111"], 1, "CARRO")
    criar_veiculo(api, cid, "MOT1A23", tipo_veiculo="MOTO")
    r = api.post("/api/movimentacoes/entrada", json={"placa": "MOT1A23"})
    assert r.status_code == 409 and "para moto" in r.get_json()["erro"]


def test_mensalista_nao_ocupa_vaga_rotativa_e_horista_nao_ocupa_a_dele(api):
    _mensalista_com_vagas(api, ["AAA1111"], 1)
    api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"})
    cliente_com_veiculo(api, "HOR1234")            # horista, e não há vaga rotativa
    r = api.post("/api/movimentacoes/entrada", json={"placa": "HOR1234"})
    assert r.status_code == 409 and "rotativas" in r.get_json()["erro"]


def test_nao_tira_a_vaga_com_o_carro_do_mensalista_dentro(api):
    cid, vagas = _mensalista_com_vagas(api, ["AAA1111"], 1)
    _pagar_abertas(api)
    mid = api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"}).get_json()["id_movimentacao"]
    r = api.post(f"/api/movimentacoes/mensalistas/vagas/{vagas[0]}/saida")
    assert r.status_code == 409 and "AAA1111" in r.get_json()["erro"]
    assert api.post(f"/api/vagas/{vagas[0]}/desvincular").status_code == 409
    api.post(f"/api/movimentacoes/{mid}/saida")
    assert api.post(f"/api/movimentacoes/mensalistas/vagas/{vagas[0]}/saida").status_code == 200


def test_painel_conta_vaga_de_mensalista_ocupada_so_com_carro_dentro(api):
    cid, _ = _mensalista_com_vagas(api, ["AAA1111"], 2)
    carro = lambda: [t for t in api.get("/api/dashboard/resumo").get_json()["por_tipo"] if t["tipo"] == "CARRO"][0]
    assert carro()["total"] == 2 and carro()["ocupadas"] == 0 and carro()["mensalistas_vinculadas"] == 2
    api.post("/api/movimentacoes/entrada", json={"placa": "AAA1111"})
    assert carro()["ocupadas"] == 1
