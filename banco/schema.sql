CREATE DATABASE IF NOT EXISTS banco_estacionamento
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE banco_estacionamento;

CREATE TABLE usuarios (
    id_usuario BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    login VARCHAR(60) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE clientes (
    id_cliente BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    tipo_pessoa ENUM('FISICA', 'JURIDICA') NOT NULL DEFAULT 'FISICA',
    cpf VARCHAR(14) NULL UNIQUE,
    cnpj VARCHAR(18) NULL UNIQUE,
    telefone VARCHAR(20) NULL,
    email VARCHAR(150) NULL,
    modalidade ENUM('MENSALISTA', 'HORISTA') NOT NULL DEFAULT 'HORISTA',
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_clientes_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_clientes_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE TABLE enderecos (
    id_endereco BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_cliente BIGINT UNSIGNED NOT NULL,
    tipo_endereco ENUM('RESIDENCIAL','COMERCIAL','COBRANCA','OUTRO') NOT NULL DEFAULT 'RESIDENCIAL',
    cep VARCHAR(9) NULL,
    logradouro VARCHAR(150) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    complemento VARCHAR(100) NULL,
    bairro VARCHAR(100) NULL,
    cidade VARCHAR(100) NOT NULL,
    estado CHAR(2) NOT NULL,
    principal BOOLEAN NOT NULL DEFAULT FALSE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_enderecos_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_enderecos_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_enderecos_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    INDEX idx_enderecos_cliente (id_cliente)
);

-- Listas controladas: o usuário cadastra marcas, modelos e cores e depois só seleciona
-- (evita "verde" / "vede"). O índice UNIQUE ignora maiúsculas/minúsculas e acentos.
CREATE TABLE marcas (
    id_marca BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(60) NOT NULL UNIQUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_marcas_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE TABLE modelos (
    id_modelo BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_marca BIGINT UNSIGNED NOT NULL,
    nome VARCHAR(80) NOT NULL,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_modelos_marca FOREIGN KEY (id_marca) REFERENCES marcas(id_marca) ON DELETE RESTRICT,
    CONSTRAINT fk_modelos_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT uq_modelos_marca_nome UNIQUE (id_marca, nome)
);

CREATE TABLE cores (
    id_cor BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(40) NOT NULL UNIQUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_cores_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE TABLE veiculos (
    id_veiculo BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_cliente BIGINT UNSIGNED NOT NULL,
    placa VARCHAR(10) NOT NULL UNIQUE,
    id_marca BIGINT UNSIGNED NULL,
    id_modelo BIGINT UNSIGNED NULL,
    id_cor BIGINT UNSIGNED NULL,
    tipo_veiculo ENUM('CARRO','MOTO','VAN','CAMINHAO','OUTRO') NOT NULL DEFAULT 'CARRO',
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_veiculos_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_veiculos_marca FOREIGN KEY (id_marca) REFERENCES marcas(id_marca) ON DELETE RESTRICT,
    CONSTRAINT fk_veiculos_modelo FOREIGN KEY (id_modelo) REFERENCES modelos(id_modelo) ON DELETE RESTRICT,
    CONSTRAINT fk_veiculos_cor FOREIGN KEY (id_cor) REFERENCES cores(id_cor) ON DELETE RESTRICT,
    CONSTRAINT fk_veiculos_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_veiculos_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    INDEX idx_veiculos_cliente (id_cliente)
);

CREATE TABLE vagas (
    id_vaga BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    setor VARCHAR(50) NULL,
    tipo_vaga ENUM('MENSALISTA','ROTATIVA') NOT NULL DEFAULT 'ROTATIVA',
    tipo_veiculo ENUM('CARRO','MOTO','VAN','CAMINHAO','OUTRO') NOT NULL DEFAULT 'CARRO',
    id_cliente BIGINT UNSIGNED NULL,
    vinculada_em DATETIME NULL,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_vagas_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_vagas_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_vagas_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT chk_vagas_rotativas_sem_cliente CHECK (tipo_vaga = 'MENSALISTA' OR id_cliente IS NULL),
    INDEX idx_vagas_cliente (id_cliente),
    INDEX idx_vagas_tipo_ativa (tipo_vaga, ativa)
);

CREATE TABLE configuracoes_tarifas (
    id_tarifa BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tipo_veiculo ENUM('CARRO','MOTO','VAN','CAMINHAO','OUTRO') NOT NULL DEFAULT 'CARRO',
    mensalidade_por_vaga DECIMAL(10,2) NOT NULL,
    valor_periodo_30_min DECIMAL(10,2) NOT NULL,
    vigencia_inicio DATE NOT NULL,
    vigencia_fim DATE NULL,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_tarifas_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_tarifas_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT chk_tarifas_valores CHECK (mensalidade_por_vaga >= 0 AND valor_periodo_30_min >= 0),
    CONSTRAINT chk_tarifas_vigencia CHECK (vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio),
    INDEX idx_tarifas_vigencia (tipo_veiculo, vigencia_inicio, vigencia_fim)
);

CREATE TABLE movimentacoes (
    id_movimentacao BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_veiculo BIGINT UNSIGNED NULL,
    id_cliente BIGINT UNSIGNED NULL,
    placa_registrada VARCHAR(10) NOT NULL,
    entrada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    saida_em DATETIME NULL,
    valor_periodo_aplicado DECIMAL(10,2) NULL,
    periodos_cobrados INT UNSIGNED NULL,
    valor_total DECIMAL(10,2) NULL,
    observacao VARCHAR(255) NULL,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_movimentacoes_veiculo FOREIGN KEY (id_veiculo) REFERENCES veiculos(id_veiculo) ON DELETE RESTRICT,
    CONSTRAINT fk_movimentacoes_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_movimentacoes_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_movimentacoes_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT chk_movimentacoes_horarios CHECK (saida_em IS NULL OR saida_em >= entrada_em),
    CONSTRAINT chk_movimentacoes_valores CHECK ((valor_periodo_aplicado IS NULL OR valor_periodo_aplicado >= 0) AND (valor_total IS NULL OR valor_total >= 0)),
    INDEX idx_movimentacoes_placa (placa_registrada),
    INDEX idx_movimentacoes_entrada_saida (entrada_em, saida_em),
    INDEX idx_movimentacoes_cliente (id_cliente)
);

CREATE TABLE pagamentos (
    id_pagamento BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_cliente BIGINT UNSIGNED NULL,
    id_movimentacao BIGINT UNSIGNED NULL,
    tipo_pagamento ENUM('MENSALIDADE','HORISTA','OUTRO') NOT NULL,
    competencia_inicio DATE NULL,
    competencia_fim DATE NULL,
    quantidade_vagas_cobradas INT UNSIGNED NULL,
    valor_unitario_aplicado DECIMAL(10,2) NULL,
    valor_pago DECIMAL(10,2) NOT NULL,
    forma_pagamento ENUM('DINHEIRO','PIX','CARTAO_CREDITO','CARTAO_DEBITO','TRANSFERENCIA','OUTRO') NOT NULL,
    pago_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observacao VARCHAR(255) NULL,
    cadastrado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    cadastrado_por BIGINT UNSIGNED NULL,
    atualizado_por BIGINT UNSIGNED NULL,
    CONSTRAINT fk_pagamentos_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    CONSTRAINT fk_pagamentos_movimentacao FOREIGN KEY (id_movimentacao) REFERENCES movimentacoes(id_movimentacao) ON DELETE RESTRICT,
    CONSTRAINT fk_pagamentos_cadastrado_por FOREIGN KEY (cadastrado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_pagamentos_atualizado_por FOREIGN KEY (atualizado_por) REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    CONSTRAINT chk_pagamentos_valor CHECK (valor_pago >= 0),
    INDEX idx_pagamentos_cliente (id_cliente),
    INDEX idx_pagamentos_data (pago_em)
);

-- Mensalidade gerada para cada vaga mensalista vinculada (um período de 1 mês por linha).
-- Nasce ABERTA ao vincular a vaga (e a cada novo mês) e vira PAGA quando o pagamento é registrado.
CREATE TABLE cobrancas_mensalidade (
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
);
