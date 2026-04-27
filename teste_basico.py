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
    
    existe_banco = os.path.exists(DB_NAME)
    
    if existe_banco:
        print(f"[STATUS] Banco de dados '{DB_NAME}' já ativo. Pulando reset físico.")
        # Mesmo com o banco existindo, rodamos o init_db para garantir 
        # que tabelas novas (como log_sessoes) sejam criadas se faltarem.
        conn = init_db(DB_NAME)
    else:
        print(f"[PASSO 1] Banco não encontrado. Iniciando criação do zero...")
        conn = init_db(DB_NAME)
        print(f"[PASSO 2] Novo banco '{DB_NAME}' inicializado.")

        # 2. População (Só ocorre se o banco for novo)
        try:
            print(f"[PASSO 3] Populando com dados do data_generator.py...")
            populate_from_v3(conn, df_hotels, df_ratings)
            print("[PASSO 4] Banco populado com sucesso.")
        except Exception as e:
            print(f"[ERRO] Falha ao popular banco novo: {e}")
            conn.close()
            return

    # 3. Verificação dos Dados
    print(f"[PASSO 3] Dados capturados do data_generator.py:")
    print(f" - Hotéis gerados: {len(df_hotels)}")
    print(f" - Avaliações geradas: {len(df_ratings)}")

    # 5. Buscar Melhores Usuários para o Front-end
    extrair_usuarios_premium(conn)

    conn.close()
    print("=== PROCESSO FINALIZADO ===")

if __name__ == "__main__":
    validar_integracao()