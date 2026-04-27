import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

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
    return np.array([
        context["peso_experiencia"],  # luxo
        context["peso_experiencia"],  # lazer
        context["peso_experiencia"],  # urbano
        0.5,                          # pet_friendly
        0.5,                          # kids_friendly
        context["peso_conforto"],     # acessibilidade
        context["peso_conforto"],     # seguranca
        1 - context["peso_custo"],    # preco
        context["peso_conforto"],     # silencio
        0.5                           # capacidade
    ])

def build_user_profile(user_id, ratings_df, hotels_df):
    user_ratings = ratings_df[ratings_df["id_usuario"] == user_id]

    if user_ratings.empty:
        return None

    merged = user_ratings.merge(hotels_df, on="id_hotel")

    weights = merged["nota"].values.reshape(-1, 1)
    features = merged[FEATURE_COLUMNS].values

    # Perfil do usuário é a média das características dos hotéis que ele avaliou, ponderada pelas notas.
    profile = np.sum(features * weights, axis=0) / np.sum(weights)
    return profile

def combine_vectors(context_vec, profile_vec, alpha=0.7):
    if profile_vec is None:
        return context_vec  # cold start
    return alpha * context_vec + (1 - alpha) * profile_vec

def knn_recommend(final_vector, hotels_df, top_n=5):
    hotel_vectors = hotels_df[FEATURE_COLUMNS].values

    # Faz a similaridade do cosseno para medir a proximidade entre o vetor de preferência do usuário e os vetores dos hotéis
    similarities = cosine_similarity([final_vector], hotel_vectors)[0]

    hotels_df = hotels_df.copy()
    # Adiciona coluna de similaridades
    hotels_df["similaridade"] = similarities

    # Ordena da maior similaridade para a menor e pega os primeiros n (top 5)
    return hotels_df.sort_values("similaridade", ascending=False).head(top_n)

def get_recommendations_knn(context, user_id, hotels_df, ratings_df, alpha=0.7, top_n=5):
    context_vec = build_context_vector(context)
    profile_vec = build_user_profile(user_id, ratings_df, hotels_df)

    final_vec = combine_vectors(context_vec, profile_vec, alpha)

    return knn_recommend(final_vec, hotels_df, top_n)