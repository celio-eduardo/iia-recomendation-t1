import sqlite3
import pandas as pd
import os

# Importando suas funções e dados reais
try:
    from banco_sql import init_db
    from data_generator import df_hotels, df_ratings
    from bd_populate import populate_from_v3
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    print("Certifique-se de que os nomes dos arquivos estão corretos no diretório.")
    exit()

DB_NAME = "sistema_recomendacao.db"

def validar_integracao():
    print("=== INICIANDO TESTE DE INTEGRAÇÃO REAL ===\n")

    # 1. Reset e Inicialização do Banco
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    conn = init_db(DB_NAME)
    print(f"[PASSO 1] Banco '{DB_NAME}' inicializado via init_db().")

    # 2. Verificação dos Dados Gerados
    # O data_generator.py roda no import e disponibiliza df_hotels e df_ratings
    print(f"[PASSO 2] Dados capturados do data_generator.py:")
    print(f" - Hotéis gerados: {len(df_hotels)}")
    print(f" - Avaliações geradas: {len(df_ratings)}")

    # 3. População do Banco
    # Nota: Caso haja erro de nome de coluna (ex: Luxo vs luxo), o populate_from_v3 original pode falhar.
    # O script abaixo chama sua função original.
    try:
        populate_from_v3(conn, df_hotels, df_ratings)
        print("[PASSO 3] Banco populado com sucesso via populate_from_v3().")
    except Exception as e:
        print(f"[ERRO NO PASSO 3] Falha ao popular banco: {e}")
        return

    # 4. Execução do Select Matriz
    # Lendo o conteúdo do seu arquivo SQL real
    try:
        with open('select_matriz_utilidade.sql', 'r') as f:
            query = f.read()
        
        df_matriz_final = pd.read_sql_query(query, conn)
        print("\n=== VALIDAÇÃO DA MATRIZ FINAL (via JOIN SQL) ===")
        print(f"Total de registros recuperados: {len(df_matriz_final)}")
        print("Primeiras 5 linhas da matriz resultante:")
        print(df_matriz_final.head())
        
        # Validação de integridade
        if len(df_matriz_final) == len(df_ratings):
            print("\n[SUCESSO] O número de interações no banco coincide com o gerado.")
        else:
            print(f"\n[AVISO] Divergência: Geradas {len(df_ratings)}, mas recuperadas {len(df_matriz_final)}.")
            
    except Exception as e:
        print(f"[ERRO NO PASSO 4] Falha ao executar SQL de matriz: {e}")

    conn.close()

if __name__ == "__main__":
    validar_integracao()