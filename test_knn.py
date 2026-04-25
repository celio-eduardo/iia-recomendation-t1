import pandas as pd

from knn_model import get_recommendations_knn
from banco_sql import init_db
from bd_populate import populate_from_v3
from data_generator import df_hotels, df_ratings

DB_NAME = "sistema_recomendacao.db"

def ensure_database_ready() -> None:
    conn = init_db(DB_NAME)
    try:
        # init_db returns a plain sqlite connection (rows as tuples),
        # so count queries must use numeric indexing.
        total_hoteis = conn.execute("SELECT COUNT(*) FROM hoteis").fetchone()[0]
        total_avaliacoes = conn.execute("SELECT COUNT(*) FROM avaliacoes").fetchone()[0]
        if total_hoteis == 0 or total_avaliacoes == 0:
            populate_from_v3(conn, df_hotels, df_ratings)
    finally:
        conn.close()

def load_data():
    conn = init_db(DB_NAME)

    hotels_df = pd.read_sql_query("SELECT * FROM hoteis", conn)
    ratings_df = pd.read_sql_query("SELECT * FROM avaliacoes", conn)

    conn.close()

    return hotels_df, ratings_df

def print_recommendations(recs):
    print("\n===== TOP RECOMENDAÇÕES =====\n")

    for i, row in recs.iterrows():
        print(f"Hotel ID: {row['id_hotel']}")
        print(f"Similaridade: {row['similaridade']:.4f}")
        print("-" * 30)

def test_knn(user_id, context, alpha=0.7):
    print("\n Iniciando teste KNN\n")

    hotels_df, ratings_df = load_data()

    print(f"Total de hotéis: {len(hotels_df)}")
    print(f"Total de avaliações: {len(ratings_df)}")

    recs = get_recommendations_knn(
        context=context,
        user_id=user_id,
        hotels_df=hotels_df,
        ratings_df=ratings_df,
        alpha=alpha,
        top_n=5
    )

    print_recommendations(recs)

if __name__ == "__main__":

    context = {
        "peso_experiencia": 0.9,
        "peso_conforto": 0.7,
        "peso_custo": 0.2
    }

    print("\n=== TESTE 1: Usuário com histórico ===")
    test_knn(user_id=1, context=context, alpha=0.7)

    print("\n=== TESTE 2: Usuário novo (cold start) ===")
    test_knn(user_id=9999, context=context, alpha=0.7)

    print("\n=== TESTE 3: alpha alto (prioriza contexto) ===")
    test_knn(user_id=1, context=context, alpha=0.9)

    print("\n=== TESTE 4: alpha baixo (prioriza histórico) ===")
    test_knn(user_id=1, context=context, alpha=0.3)