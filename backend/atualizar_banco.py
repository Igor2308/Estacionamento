"""Atualiza um banco JÁ EXISTENTE para a versão nova do sistema (pode rodar quantas vezes quiser).

O que faz:
  1. cria as tabelas de marcas, modelos e cores;
  2. troca as colunas de texto marca/modelo/cor de veiculos por vínculos com essas tabelas,
     aproveitando o que já estava cadastrado (sem perder nada);
  3. adiciona o TIPO DE VEÍCULO nas tarifas e nas vagas:
       - as tarifas que já existiam passam a valer para carro e são copiadas para moto, van, caminhão
         e outro (assim nada trava; depois ajuste cada tipo na tela "Tarifas");
       - as vagas que já existiam ficam como "carro" (corrija no cadastro se alguma for de outro tipo);
  4. cria a tabela de mensalidades (cobrancas_mensalidade) e gera uma mensalidade em aberto, a partir de hoje,
     para cada vaga mensalista que já estava vinculada a um cliente;
  5. recalcula o fim de vigência das tarifas (cada uma vale até a véspera da próxima do mesmo tipo);
  6. adiciona o PAÍS nos endereços (os antigos ficam como "Brasil"), o valor recebido e o troco nos pagamentos
     (para o controle do dinheiro físico) e um índice no nome do cliente (busca/paginação);
  7. se não existir NENHUMA tarifa, cadastra uma inicial para cada tipo de veículo,
     que você pode ajustar depois na tela "Tarifas".

Uso (dentro da pasta backend):  python atualizar_banco.py
"""
from config.database import conectar_banco
from services.mensalidades_service import criar_cobranca
from services.tarifas_service import recalcular_vigencias

TABELAS = [
    """CREATE TABLE IF NOT EXISTS marcas (
        id_marca BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(60) NOT NULL UNIQUE,
        cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        cadastrado_por BIGINT UNSIGNED NULL,
        CONSTRAINT fk_marcas_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL
    )""",
    """CREATE TABLE IF NOT EXISTS modelos (
        id_modelo BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        id_marca BIGINT UNSIGNED NOT NULL,
        nome VARCHAR(80) NOT NULL,
        cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        cadastrado_por BIGINT UNSIGNED NULL,
        CONSTRAINT fk_modelos_marca FOREIGN KEY (id_marca) REFERENCES marcas(id_marca) ON DELETE RESTRICT,
        CONSTRAINT fk_modelos_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
        CONSTRAINT uq_modelos_marca_nome UNIQUE (id_marca, nome)
    )""",
    """CREATE TABLE IF NOT EXISTS cores (
        id_cor BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(40) NOT NULL UNIQUE,
        cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        cadastrado_por BIGINT UNSIGNED NULL,
        CONSTRAINT fk_cores_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL
    )""",
]


TABELA_COBRANCAS = """CREATE TABLE IF NOT EXISTS cobrancas_mensalidade (
    id_cobranca BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_cliente BIGINT UNSIGNED NOT NULL,
    id_vaga BIGINT UNSIGNED NOT NULL,
    tipo_veiculo ENUM('CARRO','MOTO','VAN','CAMINHAO','OUTRO') NOT NULL,
    competencia_inicio DATE NOT NULL,
    competencia_fim DATE NOT NULL,
    valor DECIMAL(10,2) NOT NULL,
    status ENUM('ABERTA','PAGA') NOT NULL DEFAULT 'ABERTA',
    id_pagamento BIGINT UNSIGNED NULL,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_cobrancas_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_cobrancas_vaga FOREIGN KEY (id_vaga) REFERENCES vagas(id_vaga) ON DELETE RESTRICT,
    CONSTRAINT fk_cobrancas_pagamento FOREIGN KEY (id_pagamento) REFERENCES pagamentos(id_pagamento) ON DELETE SET NULL,
    CONSTRAINT fk_cobrancas_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT chk_cobrancas_valor CHECK (valor >= 0),
    CONSTRAINT chk_cobrancas_periodo CHECK (competencia_fim >= competencia_inicio),
    CONSTRAINT uq_cobrancas_vaga_periodo UNIQUE (id_vaga, competencia_inicio),
    INDEX idx_cobrancas_cliente_status (id_cliente, status),
    INDEX idx_cobrancas_vaga_status (id_vaga, status)
)"""

TIPOS_VEICULO = ("CARRO", "MOTO", "VAN", "CAMINHAO", "OUTRO")
ENUM_TIPOS = "ENUM('CARRO','MOTO','VAN','CAMINHAO','OUTRO') NOT NULL DEFAULT 'CARRO'"


def colunas(cur, tabela):
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (tabela,))
    return {linha[0] for linha in cur.fetchall()}


def main():
    con = conectar_banco()
    cur = con.cursor()

    for ddl in TABELAS:
        cur.execute(ddl)
    print("OK  tabelas marcas / modelos / cores")

    existentes = colunas(cur, "veiculos")
    novas = {
        "id_marca": "ADD COLUMN id_marca BIGINT UNSIGNED NULL, "
                    "ADD CONSTRAINT fk_veiculos_marca FOREIGN KEY (id_marca) REFERENCES marcas(id_marca) ON DELETE RESTRICT",
        "id_modelo": "ADD COLUMN id_modelo BIGINT UNSIGNED NULL, "
                     "ADD CONSTRAINT fk_veiculos_modelo FOREIGN KEY (id_modelo) REFERENCES modelos(id_modelo) ON DELETE RESTRICT",
        "id_cor": "ADD COLUMN id_cor BIGINT UNSIGNED NULL, "
                  "ADD CONSTRAINT fk_veiculos_cor FOREIGN KEY (id_cor) REFERENCES cores(id_cor) ON DELETE RESTRICT",
    }
    for nome, alteracao in novas.items():
        if nome not in existentes:
            cur.execute("ALTER TABLE veiculos " + alteracao)

    # Aproveita os textos antigos (marca/modelo/cor) e depois remove essas colunas.
    existentes = colunas(cur, "veiculos")
    if {"marca", "modelo", "cor"} & existentes:
        if "marca" in existentes:
            cur.execute("INSERT IGNORE INTO marcas (nome) SELECT DISTINCT TRIM(marca) FROM veiculos "
                        "WHERE marca IS NOT NULL AND TRIM(marca) <> ''")
            cur.execute("UPDATE veiculos v JOIN marcas m ON m.nome = TRIM(v.marca) SET v.id_marca = m.id_marca "
                        "WHERE v.id_marca IS NULL")
        if "cor" in existentes:
            cur.execute("INSERT IGNORE INTO cores (nome) SELECT DISTINCT TRIM(cor) FROM veiculos "
                        "WHERE cor IS NOT NULL AND TRIM(cor) <> ''")
            cur.execute("UPDATE veiculos v JOIN cores c ON c.nome = TRIM(v.cor) SET v.id_cor = c.id_cor "
                        "WHERE v.id_cor IS NULL")
        if "modelo" in existentes and "marca" in existentes:
            cur.execute("INSERT IGNORE INTO modelos (id_marca, nome) SELECT DISTINCT v.id_marca, TRIM(v.modelo) "
                        "FROM veiculos v WHERE v.id_marca IS NOT NULL AND v.modelo IS NOT NULL AND TRIM(v.modelo) <> ''")
            cur.execute("UPDATE veiculos v JOIN modelos mo ON mo.id_marca = v.id_marca AND mo.nome = TRIM(v.modelo) "
                        "SET v.id_modelo = mo.id_modelo WHERE v.id_modelo IS NULL")
        for antiga in ("marca", "modelo", "cor"):
            if antiga in existentes:
                cur.execute(f"ALTER TABLE veiculos DROP COLUMN {antiga}")
    print("OK  veículos agora usam marca / modelo / cor cadastrados")

    # Tipo de veículo nas tarifas (e cópia das tarifas antigas para os outros tipos, uma única vez).
    if "tipo_veiculo" not in colunas(cur, "configuracoes_tarifas"):
        cur.execute(f"ALTER TABLE configuracoes_tarifas ADD COLUMN tipo_veiculo {ENUM_TIPOS} AFTER id_tarifa")
        for tipo in TIPOS_VEICULO:
            if tipo == "CARRO":
                continue
            cur.execute(
                "INSERT INTO configuracoes_tarifas (tipo_veiculo, mensalidade_por_vaga, valor_periodo_30_min, "
                "vigencia_inicio, vigencia_fim, cadastrado_por, atualizado_por) "
                "SELECT %s, mensalidade_por_vaga, valor_periodo_30_min, vigencia_inicio, vigencia_fim, "
                "cadastrado_por, atualizado_por FROM configuracoes_tarifas WHERE tipo_veiculo = 'CARRO'", (tipo,))
        print("OK  tarifas agora são por tipo de veículo (as antigas valem para todos os tipos)")
    else:
        print("OK  tarifas já são por tipo de veículo")

    # Tipo de veículo nas vagas.
    if "tipo_veiculo" not in colunas(cur, "vagas"):
        cur.execute(f"ALTER TABLE vagas ADD COLUMN tipo_veiculo {ENUM_TIPOS} AFTER tipo_vaga")
        print("OK  vagas agora têm tipo de veículo (as antigas ficaram como carro - ajuste se precisar)")
    else:
        print("OK  vagas já têm tipo de veículo")

    # Mensalidades: tabela nova + uma cobrança em aberto (a partir de hoje) para cada vaga já vinculada.
    cur.execute(TABELA_COBRANCAS)
    cd = con.cursor(dictionary=True)
    cd.execute("SELECT CURRENT_DATE AS hoje")
    hoje = cd.fetchone()["hoje"]
    cd.execute("""
        SELECT v.id_vaga, v.id_cliente, v.tipo_veiculo
        FROM vagas v
        WHERE v.tipo_vaga = 'MENSALISTA' AND v.id_cliente IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM cobrancas_mensalidade cb
                          WHERE cb.id_vaga = v.id_vaga AND cb.id_cliente = v.id_cliente)
    """)
    for vaga in cd.fetchall():
        _, erro = criar_cobranca(cd, vaga, hoje)
        print("OK  mensalidade gerada para a vaga", vaga["id_vaga"] if not erro else f"(vaga {vaga['id_vaga']}: {erro})")

    # Vigências: cada tarifa vale até a véspera da próxima do mesmo tipo.
    for tipo in TIPOS_VEICULO:
        recalcular_vigencias(cd, tipo)
    cd.close()
    print("OK  vigências das tarifas recalculadas")

    # País do endereço, valor recebido/troco do pagamento e índice de busca por nome.
    if "pais" not in colunas(cur, "enderecos"):
        cur.execute("ALTER TABLE enderecos ADD COLUMN pais VARCHAR(60) NOT NULL DEFAULT 'Brasil' AFTER estado")
        print("OK  endereços agora têm país (os antigos ficaram como Brasil)")
    else:
        print("OK  endereços já têm país")

    cols_pag = colunas(cur, "pagamentos")
    if "valor_recebido" not in cols_pag:
        cur.execute("ALTER TABLE pagamentos ADD COLUMN valor_recebido DECIMAL(10,2) NULL AFTER forma_pagamento, "
                    "ADD COLUMN troco DECIMAL(10,2) NULL AFTER valor_recebido")
        print("OK  pagamentos agora guardam valor recebido e troco (dinheiro)")
    else:
        print("OK  pagamentos já guardam valor recebido e troco")

    cur.execute("SELECT COUNT(*) FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'clientes' AND INDEX_NAME = 'idx_clientes_nome'")
    if cur.fetchone()[0] == 0:
        cur.execute("ALTER TABLE clientes ADD INDEX idx_clientes_nome (nome)")
        print("OK  índice de busca por nome de cliente")

    cur.execute("SELECT COUNT(*) FROM configuracoes_tarifas")
    if cur.fetchone()[0] == 0:
        for tipo in TIPOS_VEICULO:
            cur.execute("INSERT INTO configuracoes_tarifas (tipo_veiculo, mensalidade_por_vaga, valor_periodo_30_min, "
                        "vigencia_inicio) VALUES (%s, 300.00, 5.00, '2020-01-01')", (tipo,))
        print("OK  tarifas iniciais cadastradas (R$ 5,00 / 30 min e R$ 300,00 por vaga, para cada tipo) - ajuste na tela Tarifas")
    else:
        print("OK  já existe tarifa cadastrada")

    con.commit()
    cur.close()
    con.close()
    print("Banco atualizado.")


if __name__ == "__main__":
    main()
