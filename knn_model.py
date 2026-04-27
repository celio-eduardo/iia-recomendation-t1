"""
Módulo responsável pela implementação do sistema de recomendação baseado em conteúdo
utilizando K-Nearest Neighbors (KNN) com similaridade do cosseno.

Fluxo do algoritmo:
1. Construção do vetor de contexto do usuário (contexto atual)
2. Construção do perfil do usuário (histórico de avaliações)
3. Combinação entre contexto e perfil (interpolação linear)
4. Cálculo de similaridade entre usuário e hotéis
5. Retorno dos hotéis mais similares (Top-N)

Este modelo é classificado como:
- Recomendador baseado em conteúdo (Content-Based Filtering)
- Sensível a contexto (Context-Aware Recommender System)
"""

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

"""
Lista de features utilizadas para representar cada hotel no espaço vetorial.

Cada hotel é representado como um vetor numérico de dimensão 10,
onde cada posição corresponde a uma característica relevante.
"""
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


def build_context_vector(context):
    """
    Constrói o vetor de contexto do usuário a partir das preferências informadas na interface.

    O vetor de contexto projeta preferências abstratas (custo, conforto, experiência)
    no espaço de features dos hotéis.

    Parâmetros
    ----------
    context : dict
        Dicionário contendo:
        - peso_experiencia
        - peso_conforto
        - peso_custo

    Retorno
    -------
    np.ndarray
        Vetor de dimensão igual ao número de features (10),
        representando a intenção atual do usuário.
    """
    return np.array([
        context["peso_experiencia"],  # luxo
        context["peso_experiencia"],  # lazer
        context["peso_experiencia"],  # urbano
        0.5,                          # pet_friendly (neutro)
        0.5,                          # kids_friendly (neutro)
        context["peso_conforto"],     # acessibilidade
        context["peso_conforto"],     # seguranca
        1 - context["peso_custo"],    # preco (inverso: menor custo = maior preferência)
        context["peso_conforto"],     # silencio
        0.5                           # capacidade (neutro)
    ])


def build_user_profile(user_id, ratings_df, hotels_df):
    """
    Constrói o vetor de perfil do usuário com base no histórico de avaliações.

    O perfil é calculado como uma média ponderada das features dos hotéis avaliados,
    onde as notas atribuídas pelo usuário são utilizadas como pesos.

    Parâmetros
    ----------
    user_id : str
        Identificador do usuário (ex: "U001")

    ratings_df : pd.DataFrame
        DataFrame contendo avaliações dos usuários (id_usuario, id_hotel, nota)

    hotels_df : pd.DataFrame
        DataFrame contendo features dos hotéis

    Retorno
    -------
    np.ndarray ou None
        Vetor de perfil do usuário ou None em caso de cold start
    """
    # Filtra avaliações do usuário
    user_ratings = ratings_df[ratings_df["id_usuario"] == user_id]

    # Cold start: usuário sem histórico
    if user_ratings.empty:
        return None

    # Junta avaliações com features dos hotéis
    merged = user_ratings.merge(hotels_df, on="id_hotel")

    # Notas como pesos
    weights = merged["nota"].values.reshape(-1, 1)

    # Matriz de features dos hotéis avaliados
    features = merged[FEATURE_COLUMNS].values

    # Média ponderada das features
    # p_u = sum(nota_i * vetor_hotel_i) / sum(nota_i)
    profile = np.sum(features * weights, axis=0) / np.sum(weights)

    return profile


def combine_vectors(context_vec, profile_vec, alpha=0.7):
    """
    Combina o vetor de contexto com o perfil do usuário usando interpolação linear.

    Fórmula:
        v_final = alpha * contexto + (1 - alpha) * perfil

    Parâmetros
    ----------
    context_vec : np.ndarray
        Vetor de contexto

    profile_vec : np.ndarray ou None
        Vetor de perfil do usuário

    alpha : float
        Peso do contexto (0 <= alpha <= 1)

    Retorno
    -------
    np.ndarray
        Vetor final utilizado para recomendação
    """
    # Caso de cold start: usar apenas contexto
    if profile_vec is None:
        return context_vec

    return alpha * context_vec + (1 - alpha) * profile_vec


def knn_recommend(final_vector, hotels_df, top_n=5):
    """
    Calcula a similaridade entre o vetor do usuário e todos os hotéis,
    retornando os Top-N mais similares.

    A similaridade é medida utilizando o cosseno entre vetores.

    Parâmetros
    ----------
    final_vector : np.ndarray
        Vetor representando preferências do usuário

    hotels_df : pd.DataFrame
        DataFrame com features dos hotéis

    top_n : int
        Número de recomendações a retornar

    Retorno
    -------
    pd.DataFrame
        DataFrame com os hotéis mais similares ordenados por similaridade
    """
    # Matriz de vetores dos hotéis
    hotel_vectors = hotels_df[FEATURE_COLUMNS].values

    # Similaridade do cosseno entre usuário e hotéis
    similarities = cosine_similarity([final_vector], hotel_vectors)[0]

    # Copia para evitar modificar original
    hotels_df = hotels_df.copy()

    # Adiciona score de similaridade
    hotels_df["similaridade"] = similarities

    # Ordena e retorna Top-N
    return hotels_df.sort_values("similaridade", ascending=False).head(top_n)


def get_recommendations_knn(context, user_id, hotels_df, ratings_df, alpha=0.7, top_n=5):
    """
    Função principal do sistema de recomendação baseado em KNN.

    Executa todo o pipeline:
    1. Criação do vetor de contexto
    2. Construção do perfil do usuário
    3. Combinação entre contexto e perfil
    4. Geração de recomendações

    Parâmetros
    ----------
    context : dict
        Contexto da viagem

    user_id : str
        Identificador do usuário

    hotels_df : pd.DataFrame
        Base de hotéis

    ratings_df : pd.DataFrame
        Base de avaliações

    alpha : float
        Peso do contexto

    top_n : int
        Número de recomendações

    Retorno
    -------
    pd.DataFrame
        Top-N hotéis recomendados
    """
    # Vetor de contexto
    context_vec = build_context_vector(context)

    # Perfil do usuário
    profile_vec = build_user_profile(user_id, ratings_df, hotels_df)

    # Vetor final (contexto + histórico)
    final_vec = combine_vectors(context_vec, profile_vec, alpha)

    # Geração das recomendações
    return knn_recommend(final_vec, hotels_df, top_n)