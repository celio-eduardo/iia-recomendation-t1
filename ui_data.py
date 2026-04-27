"""
Módulo responsável pela camada de integração entre a interface (Streamlit)
e o banco de dados do sistema de recomendação.

Este módulo encapsula:
- Conexão com o banco SQLite
- Operações CRUD (usuários e avaliações)
- Geração de recomendações
- Cálculo de métricas do sistema

Modelos de recomendação disponíveis:
------------------------------------
1. Heurístico (baseline):
   - Baseado em score ponderado (nota, custo, conforto, experiência)
   - Inclui bônus por região

2. KNN (Content-Based Filtering):
   - Baseado em similaridade entre vetor de contexto/perfil e features dos hotéis
   - Integra histórico do usuário + contexto atual via interpolação linear
"""

import sqlite3
import uuid
from typing import Dict, List, Optional

import pandas as pd

from banco_sql import init_db
from bd_populate import populate_from_v3
from data_generator import df_hotels, df_ratings
from knn_model import get_recommendations_knn

DB_NAME = "sistema_recomendacao.db"

FEATURE_COLUMNS = [
    "luxo",
    "lazer",
    "urbano",
    "pet_friendly",
    "kids_friendly",
    "acessibilidade",
    "seguranca",
    "preco",
    "silencio",
    "capacidade",
]


def get_connection() -> sqlite3.Connection:
    """
    Cria e retorna uma conexão com o banco SQLite.

    Retorno
    -------
    sqlite3.Connection
        Conexão configurada com acesso por nome de coluna (Row)
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_database_ready() -> None:
    """
    Garante que o banco de dados está inicializado e populado.

    - Cria tabelas (via init_db)
    - Popula com dados sintéticos se estiver vazio
    """
    conn = init_db(DB_NAME)
    try:
        total_hoteis = conn.execute("SELECT COUNT(*) FROM hoteis").fetchone()[0]
        total_avaliacoes = conn.execute("SELECT COUNT(*) FROM avaliacoes").fetchone()[0]

        if total_hoteis == 0 or total_avaliacoes == 0:
            populate_from_v3(conn, df_hotels, df_ratings)
    finally:
        conn.close()


def create_user(login: str, senha: str, perfil_base: str) -> Optional[str]:
    """
    Cria um novo usuário no sistema.

    Parâmetros
    ----------
    login : str
    senha : str
    perfil_base : str

    Retorno
    -------
    str ou None
        ID do usuário criado ou None em caso de login duplicado
    """
    user_id = f"UAPP_{uuid.uuid4().hex[:8].upper()}"

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO usuarios (id_usuario, login, senha, perfil_base)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, login.strip(), senha, perfil_base),
        )
        conn.commit()
        return user_id

    except sqlite3.IntegrityError:
        return None

    finally:
        conn.close()


def authenticate_user(login: str, senha: str) -> Optional[Dict[str, str]]:
    """
    Autentica um usuário.

    Retorna dados básicos do usuário se as credenciais forem válidas.
    """
    conn = get_connection()

    row = conn.execute(
        """
        SELECT id_usuario, login, perfil_base
        FROM usuarios
        WHERE login = ? AND senha = ?
        """,
        (login.strip(), senha),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


def list_user_recommended_hotels(user_id: str) -> List[str]:
    """
    Retorna lista de hotéis já avaliados pelo usuário.

    Utilizado para evitar recomendar itens já vistos.
    """
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT DISTINCT id_hotel
        FROM avaliacoes
        WHERE id_usuario = ?
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    return [row["id_hotel"] for row in rows]


def get_recommendations_heuristic(context: Dict[str, str], user_id: str, top_n: int = 10) -> pd.DataFrame:
    """
    Gera recomendações utilizando um modelo baseado em score heurístico.

    Componentes do score:
    - Nota média do hotel
    - Custo-benefício
    - Conforto
    - Experiência
    - Bônus por região

    Parâmetros
    ----------
    context : dict
    user_id : str
    top_n : int

    Retorno
    -------
    pd.DataFrame
        Top-N recomendações
    """
    conn = get_connection()

    hotels_df = pd.read_sql_query("SELECT * FROM hoteis", conn)

    ratings_df = pd.read_sql_query(
        "SELECT id_hotel, AVG(nota) AS media_nota FROM avaliacoes GROUP BY id_hotel",
        conn,
    )

    conn.close()

    if hotels_df.empty:
        return hotels_df

    # Junta média de avaliações
    hotels_df = hotels_df.merge(ratings_df, on="id_hotel", how="left")
    hotels_df["media_nota"] = hotels_df["media_nota"].fillna(3.0)

    # Preferências do usuário
    region_pref = context["regiao"]
    peso_custo = context["peso_custo"]
    peso_conforto = context["peso_conforto"]
    peso_experiencia = context["peso_experiencia"]

    # Componentes do score
    price_component = (1.0 - hotels_df["preco"]) * peso_custo
    comfort_component = (hotels_df["silencio"] + hotels_df["seguranca"] + hotels_df["acessibilidade"]) / 3
    comfort_component = comfort_component * peso_conforto
    experience_component = (hotels_df["lazer"] + hotels_df["luxo"] + hotels_df["urbano"]) / 3
    experience_component = experience_component * peso_experiencia

    # Score base
    hotels_df["score_base"] = (
        0.25 * hotels_df["media_nota"] + price_component + comfort_component + experience_component
    )

    # Bônus por região
    hotels_df["bonus_regiao"] = hotels_df["regiao"].apply(lambda value: 0.5 if value == region_pref else 0.0)

    # Score final
    hotels_df["score_final"] = hotels_df["score_base"] + hotels_df["bonus_regiao"]

    # Remove hotéis já avaliados
    seen_hotels = set(list_user_recommended_hotels(user_id))
    if seen_hotels:
        hotels_df = hotels_df[~hotels_df["id_hotel"].isin(seen_hotels)]

    # Top-N
    hotels_df = hotels_df.sort_values("score_final", ascending=False).head(top_n).copy()

    # Justificativa textual
    hotels_df["justificativa"] = hotels_df.apply(_build_justification, axis=1)

    return hotels_df[
        ["id_hotel", "nome", "regiao", "media_nota", "score_final", "justificativa"]
    ]


def get_recommendations(
    context: Dict[str, str],
    user_id: str,
    top_n: int = 10,
    model: str = "KNN",
    alpha: float = 0.7
) -> pd.DataFrame:
    """
    Função unificada para geração de recomendações.

    Esta função permite alternar entre diferentes algoritmos de recomendação,
    possibilitando comparação entre abordagens.

    Parâmetros
    ----------
    context : Dict[str, float]
        Contexto da viagem contendo:
        - regiao (str)
        - peso_custo (float)
        - peso_conforto (float)
        - peso_experiencia (float)

    user_id : str
        Identificador do usuário

    top_n : int, opcional
        Número de recomendações retornadas (default = 10)

    model : str, opcional
        Modelo de recomendação utilizado:
        - "KNN" → modelo baseado em similaridade (Content-Based)
        - "Heurístico" → modelo baseado em score

    alpha : float, opcional
        Peso do contexto no modelo KNN (0 ≤ alpha ≤ 1)

    Retorno
    -------
    pd.DataFrame
        DataFrame contendo as recomendações ordenadas

    Exceções
    --------
    ValueError
        Caso o modelo especificado seja inválido
    """

    if model == "KNN":
        conn = get_connection()

        hotels_df = pd.read_sql_query("SELECT * FROM hoteis", conn)
        ratings_df = pd.read_sql_query("SELECT * FROM avaliacoes", conn)

        conn.close()

        recs = get_recommendations_knn(
            context=context,
            user_id=user_id,
            hotels_df=hotels_df,
            ratings_df=ratings_df,
            alpha=alpha,
            top_n=top_n
        )

        # Remove hotéis já avaliados
        seen_hotels = set(list_user_recommended_hotels(user_id))
        if seen_hotels:
            recs = recs[~recs["id_hotel"].isin(seen_hotels)]

        return recs

    elif model == "Heurístico":
        return get_recommendations_heuristic(context, user_id, top_n)

    else:
        raise ValueError(f"Modelo desconhecido: {model}")


def _build_justification(row: pd.Series) -> str:
    """
    Gera uma justificativa textual para a recomendação.

    Seleciona os atributos mais fortes do hotel.
    """
    attrs = {
        "luxo": row["luxo"],
        "lazer": row["lazer"],
        "seguranca": row["seguranca"],
        "silencio": row["silencio"],
        "preco_bom": 1.0 - row["preco"],
    }

    top_attrs = sorted(attrs.items(), key=lambda item: item[1], reverse=True)[:2]

    labels = ", ".join([item[0] for item in top_attrs])

    return f"Regiao {row['regiao']} com destaque para {labels}."


def submit_rating(user_id: str, hotel_id: str, nota: int, contexto_viagem: str) -> None:
    """
    Registra uma nova avaliação no sistema.
    """
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO avaliacoes (id_usuario, id_hotel, nota, contexto_viagem, logica_geracao)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, hotel_id, nota, contexto_viagem, "Feedback App Streamlit"),
    )

    conn.commit()
    conn.close()


def get_rating_distribution() -> pd.DataFrame:
    """
    Retorna a distribuição de notas atribuídas pelos usuários.
    """
    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT nota, COUNT(*) AS total
        FROM avaliacoes
        GROUP BY nota
        ORDER BY nota
        """,
        conn,
    )

    conn.close()
    return df


def get_ratings_by_context() -> pd.DataFrame:
    """
    Retorna quantidade de avaliações por contexto de viagem.
    """
    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT contexto_viagem, COUNT(*) AS total
        FROM avaliacoes
        GROUP BY contexto_viagem
        ORDER BY total DESC
        """,
        conn,
    )

    conn.close()
    return df


def get_ratings_by_region() -> pd.DataFrame:
    """
    Retorna quantidade de avaliações por região.
    """
    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT h.regiao, COUNT(*) AS total
        FROM avaliacoes a
        JOIN hoteis h ON a.id_hotel = h.id_hotel
        GROUP BY h.regiao
        ORDER BY total DESC
        """,
        conn,
    )

    conn.close()
    return df


def get_catalog_coverage(top_n: int = 5) -> pd.DataFrame:
    """
    Calcula a cobertura do catálogo de recomendações.

    Mede quantos hotéis diferentes aparecem no Top-N agregado
    para todos os usuários.

    Retorno em porcentagem.
    """
    conn = get_connection()

    users_df = pd.read_sql_query("SELECT id_usuario FROM usuarios", conn)

    conn.close()

    recommended_hotels = set()

    if users_df.empty:
        return pd.DataFrame({"metrica": ["Cobertura"], "valor": [0.0]})

    for _, row in users_df.iterrows():
        rec_df = get_recommendations(
            {
                "regiao": "Sao Paulo",
                "peso_custo": 1.0,
                "peso_conforto": 1.0,
                "peso_experiencia": 1.0,
            },
            row["id_usuario"],
            top_n=top_n,
        )
        recommended_hotels.update(rec_df["id_hotel"].tolist())

    conn = get_connection()
    total_hotels = conn.execute("SELECT COUNT(*) AS c FROM hoteis").fetchone()["c"]
    conn.close()

    coverage = (len(recommended_hotels) / total_hotels) if total_hotels else 0.0

    return pd.DataFrame(
        {
            "metrica": ["Cobertura de hoteis no Top-N agregado"],
            "valor": [round(coverage * 100, 2)],
        }
    )
