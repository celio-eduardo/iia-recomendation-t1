import sqlite3
import pandas as pd
import os

try:
    from banco_sql import init_db
    from data_generator import df_hotels, df_ratings
    from bd_populate import populate_from_v3
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    exit()

DB_NAME = "sistema_recomendacao.db"

def extrair_usuarios_premium(conn):
    print("\n=== USUÁRIOS PREMIUM PARA APRESENTAÇÃO (TOP 1 DE CADA PERFIL) ===")
    query = """
    SELECT 
        u.perfil_base, 
        u.login, 
        u.senha, 
        COUNT(a.id_avaliacao) as avaliacoes_registradas
    FROM usuarios u
    JOIN avaliacoes a ON u.id_usuario = a.id_usuario
    GROUP BY u.id_usuario
    ORDER BY u.perfil_base, avaliacoes_registradas DESC
    """
    df = pd.read_sql_query(query, conn)
    
    top_per_profile = df.groupby('perfil_base').head(1)
    print(top_per_profile.to_string(index=False))
    print("==================================================================\n")

def validar_integracao():
    print("=== INICIANDO TESTE DE INTEGRAÇÃO E RESET DO BANCO ===\n")

    # 1. Reset Físico Total do Banco (Garante que nunca haja sujeira anterior)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"[PASSO 1] Banco antigo '{DB_NAME}' removido com sucesso.")
    else:
        print(f"[PASSO 1] Nenhum banco antigo encontrado.")
    
    # 2. Inicialização
    conn = init_db(DB_NAME)
    print(f"[PASSO 2] Novo banco '{DB_NAME}' inicializado via init_db().")

    # 3. Verificação dos Dados
    print(f"[PASSO 3] Dados capturados do data_generator.py:")
    print(f" - Hotéis gerados: {len(df_hotels)}")
    print(f" - Avaliações geradas: {len(df_ratings)}")

    # 4. População
    try:
        populate_from_v3(conn, df_hotels, df_ratings)
        print("[PASSO 4] Banco populado com sucesso (senhas 'senha123' aplicadas).")
    except Exception as e:
        print(f"[ERRO NO PASSO 4] Falha ao popular banco: {e}")
        return

    # 5. Buscar Melhores Usuários para o Front-end
    extrair_usuarios_premium(conn)

    conn.close()
    print("=== PROCESSO FINALIZADO ===")

if __name__ == "__main__":
    validar_integracao()