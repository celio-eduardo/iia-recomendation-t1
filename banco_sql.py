import sqlite3
import pandas as pd

def init_db(db_name="sistema_recomendacao.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Tabela de Usuários (Cadastro/Login)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario TEXT PRIMARY KEY,
            login TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            perfil_base TEXT NOT NULL -- Ex: 'business', 'casal_luxo'
        )
    ''')

    # Tabela de Hotéis (Matriz de Conteúdo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hoteis (
            id_hotel TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            regiao TEXT NOT NULL,
            luxo REAL, lazer REAL, urbano REAL, 
            pet_friendly REAL, kids_friendly REAL, 
            acessibilidade REAL, seguranca REAL, 
            preco REAL, silencio REAL, capacidade REAL
        )
    ''')

    # Tabela de Avaliações (Interações para a Matriz de Utilidade)
    # ALTERAÇÃO: Expansão para o modelo Multicritério (10 Features do Data Generator)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id_avaliacao INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario TEXT,
            id_hotel TEXT,
            nota_luxo REAL CHECK(nota_luxo >= 1 AND nota_luxo <= 5),
            nota_lazer REAL CHECK(nota_lazer >= 1 AND nota_lazer <= 5),
            nota_urbano REAL CHECK(nota_urbano >= 1 AND nota_urbano <= 5),
            nota_pet_friendly REAL CHECK(nota_pet_friendly >= 1 AND nota_pet_friendly <= 5),
            nota_kids_friendly REAL CHECK(nota_kids_friendly >= 1 AND nota_kids_friendly <= 5),
            nota_acessibilidade REAL CHECK(nota_acessibilidade >= 1 AND nota_acessibilidade <= 5),
            nota_seguranca REAL CHECK(nota_seguranca >= 1 AND nota_seguranca <= 5),
            nota_preco REAL CHECK(nota_preco >= 1 AND nota_preco <= 5),
            nota_silencio REAL CHECK(nota_silencio >= 1 AND nota_silencio <= 5),
            nota_capacidade REAL CHECK(nota_capacidade >= 1 AND nota_capacidade <= 5),
            contexto_viagem TEXT, -- Perfil ativo no momento da avaliação
            logica_geracao TEXT,  -- 'Perfil+Região+Tradeoff' ou 'Aleatório'
            posicao_exibicao INTEGER, 
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario),
            FOREIGN KEY(id_hotel) REFERENCES hoteis(id_hotel)
        )
    ''')
    
    # Adicione este bloco antes do conn.commit() em banco_sql.py
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_sessoes (
            id_log INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario TEXT,
            algoritmo_usado TEXT,
            qtd_exibida INTEGER,
            converteu_em_escolha BOOLEAN, -- 1 para Sim, 0 para Não
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario)
        )
    ''')
    
    conn.commit()
    return conn