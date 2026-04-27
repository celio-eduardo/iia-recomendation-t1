import sqlite3

def populate_from_v3(conn, df_hoteis, df_avaliacoes):
    
    cursor = conn.cursor()
    
    # 1. Limpeza rigorosa do banco de dados antes da inserção
    cursor.execute('DELETE FROM avaliacoes')
    cursor.execute('DELETE FROM hoteis')
    cursor.execute('DELETE FROM usuarios')

    # 2. Inserção de Usuários com a senha padrão exigida
    usuarios_unicos = df_avaliacoes[['user_id', 'perfil']].drop_duplicates(subset=['user_id'])
    
    for _, row in usuarios_unicos.iterrows():
        try:
            # Login dinâmico baseado no user_id e senha fixa para todos
            cursor.execute('''
                INSERT INTO usuarios (id_usuario, login, senha, perfil_base)
                VALUES (?, ?, ?, ?)
            ''', (row['user_id'], f"user_{row['user_id']}", "senha123", row['perfil']))
        except sqlite3.IntegrityError:
            pass
    
    # 3. Inserção de Hotéis
    for index, row in df_hoteis.iterrows():
        try:
            cursor.execute('''
                INSERT INTO hoteis (id_hotel, nome, regiao, luxo, lazer, urbano, pet_friendly, kids_friendly, acessibilidade, seguranca, preco, silencio, capacidade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                index, f"Hotel {index}", row['regiao'], row['Luxo'], row['Lazer'], row['Urbano'], 
                row['PetFriendly'], row['KidsFriendly'], row['Acessibilidade'], row['Seguranca'], 
                row['Preco'], row['Silencio'], row['Capacidade']
            ))
        except sqlite3.IntegrityError:
            pass
    
    # 4. Inserção de Avaliações
    for _, row in df_avaliacoes.iterrows():
        cursor.execute('''
            INSERT INTO avaliacoes (id_usuario, id_hotel, nota, contexto_viagem, logica_geracao)
            VALUES (?, ?, ?, ?, ?)
        ''', (row['user_id'], row['hotel_id'], row['rating'], row['perfil'], row['logica']))

    conn.commit()
