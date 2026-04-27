import sqlite3
import pandas as pd

def extrair_usuarios_exemplo(db_name="sistema_recomendacao.db"):
    conn = sqlite3.connect(db_name)
    
    # Query que agrupa por perfil e pega o usuário com mais avaliações em cada
    query = """
    SELECT 
        u.perfil_base, 
        u.login, 
        u.senha, 
        COUNT(a.id_avaliacao) as total_avaliacoes
    FROM usuarios u
    JOIN avaliacoes a ON u.id_usuario = a.id_usuario
    GROUP BY u.id_usuario
    ORDER BY u.perfil_base, total_avaliacoes DESC
    """
    
    df = pd.read_sql_query(query, conn)
    
    # Pega apenas o primeiro (o que tem mais avaliações) de cada perfil
    top_per_profile = df.groupby('perfil_base').head(1)
    
    print("=== USUÁRIOS PARA APRESENTAÇÃO (TOP POR PERFIL) ===")
    print(top_per_profile.to_string(index=False))
    
    conn.close()

if __name__ == "__main__":
    extrair_usuarios_exemplo()