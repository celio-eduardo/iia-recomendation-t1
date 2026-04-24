import sqlite3

def populate_from_v3(conn, df_hotels, df_ratings):
    # 1. Ajuste de Hoteis: Mapear nomes e adicionar coluna 'nome'
    df_hotels_db = df_hotels.copy()
    
    # Adiciona a coluna 'nome' que é obrigatória (NOT NULL)
    df_hotels_db['nome'] = [f"Hotel {idx}" for idx in df_hotels_db.index]
    
    # Renomeia as colunas para bater exatamente com o banco de dados
    df_hotels_db = df_hotels_db.rename(columns={
        'Luxo': 'luxo', 'Lazer': 'lazer', 'Urbano': 'urbano',
        'PetFriendly': 'pet_friendly', 'KidsFriendly': 'kids_friendly',
        'Acessibilidade': 'acessibilidade', 'Seguranca': 'seguranca',
        'Preco': 'preco', 'Silencio': 'silencio', 'Capacidade': 'capacidade'
    })
    
    # Salva Hotéis (id_hotel é o índice no DataFrame)
    df_hotels_db.to_sql('hoteis', conn, if_exists='append', index_label='id_hotel')
    
    # 2. Ajuste de Avaliações: Mapear nomes de colunas
    df_ratings_db = df_ratings.rename(columns={
        'user_id': 'id_usuario',
        'hotel_id': 'id_hotel',
        'rating': 'nota',
        'perfil': 'contexto_viagem',
        'logica': 'logica_geracao'
    })
    
    # Selecionar apenas as colunas que existem na tabela 'avaliacoes'
    df_ratings_db = df_ratings_db[['id_usuario', 'id_hotel', 'nota', 'contexto_viagem', 'logica_geracao']]
    
    # Salva Avaliações
    df_ratings_db.to_sql('avaliacoes', conn, if_exists='append', index=False)
    
    # 3. Criação de Usuários
    unique_users = df_ratings[['user_id', 'perfil']].drop_duplicates()
    for _, row in unique_users.iterrows():
        try:
            conn.execute(
                "INSERT INTO usuarios (id_usuario, login, senha, perfil_base) VALUES (?, ?, ?, ?)",
                (row['user_id'], f"user_{row['user_id']}", "senha123", row['perfil'])
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
