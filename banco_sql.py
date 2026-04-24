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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id_avaliacao INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario TEXT,
            id_hotel TEXT,
            nota INTEGER CHECK(nota >= 1 AND nota <= 5),
            contexto_viagem TEXT, -- Perfil ativo no momento da avaliação
            logica_geracao TEXT,  -- 'Perfil+Região+Tradeoff' ou 'Aleatório'
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario),
            FOREIGN KEY(id_hotel) REFERENCES hoteis(id_hotel)
        )
    ''')
    
    conn.commit()
    return conn