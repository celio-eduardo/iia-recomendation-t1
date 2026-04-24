def populate_from_v3(conn, df_hotels, df_ratings):
    # Salva Hotéis
    df_hotels.to_sql('hoteis', conn, if_exists='append', index_label='id_hotel')
    
    # Salva Avaliações
    df_ratings.to_sql('avaliacoes', conn, if_exists='append', index=False)
    
    # Exemplo de criação de usuários fictícios baseados nas avaliações
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