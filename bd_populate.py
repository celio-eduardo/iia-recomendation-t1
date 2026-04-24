import sqlite3

def populate_from_v3(conn, df_hotels, df_ratings):
    # 1. Ajuste de Hoteis: Adicionar coluna 'nome' exigida pelo BD
    df_hotels_db = df_hotels.copy()
    df_hotels_db['nome'] = [f"Hotel {idx}" for idx in df_hotels_db.index]
    
    # Salva Hotéis (index_label mapeia o índice 'hotel_id' para a PK do banco)
    df_hotels_db.to_sql('hoteis', conn, if_exists='append', index_label='id_hotel')
    
    # 2. Ajuste de Avaliações: Renomear colunas para bater com o Schema SQL
    df_ratings_db = df_ratings.rename(columns={
        'user_id': 'id_usuario',
        'hotel_id': 'id_hotel',
        'rating': 'nota',
        'perfil': 'contexto_viagem',
        'logica': 'logica_geracao'
    })
    
    # Remover colunas que existem no DF mas não na tabela 'avaliacoes' (ex: regiao)
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
