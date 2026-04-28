import pandas as pd
import numpy as np

# Configuração Global
np.random.seed(42)
N_HOTEIS = 50
N_USUARIOS = 500
LAMBDA_PENALTY = 0.6 # Penalidade para o conflito Luxo vs Urbano
FEATURES = [
    'Luxo', 'Lazer', 'Urbano', 'PetFriendly', 'KidsFriendly', 
    'Acessibilidade', 'Seguranca', 'Preco', 'Silencio', 'Capacidade'
]
REGIOES = ['Sao Paulo', 'Frio/Serra', 'Interior', 'Litoral/Parques']

# 1. Geração de Hotéis com Regiões e Trade-offs (Crescimento de Complexidade)
hotel_list = []
for i in range(N_HOTEIS):
    regiao = np.random.choice(REGIOES)
    # Base inicial via distribuição Beta para evitar linearidade
    row = np.random.beta(2, 2, len(FEATURES))
    
    # Aplicação de Bias Regional (Versão 1)
    if regiao == 'Sao Paulo':
        row[2] += 0.3  # Mais Urbano
        row[6] += 0.2  # Mais Segurança
    elif regiao == 'Frio/Serra':
        row[0] += 0.2  # Mais Luxo
        row[8] += 0.3  # Mais Silêncio
        
    # Aplicação de Trade-offs (Versão 2)
    row[7] = np.clip(row[0] * 0.8 + np.random.normal(0, 0.1), 0, 1)    # Luxo -> Preço Alto
    row[8] = np.clip(1 - row[2] * 0.7 + np.random.normal(0, 0.1), 0, 1) # Urbano -> Menos Silêncio
    
    hotel_list.append([f'H{i:02d}', regiao] + list(np.clip(row, 0, 1)))

df_hotels = pd.DataFrame(hotel_list, columns=['hotel_id', 'regiao'] + FEATURES).set_index('hotel_id')

# 2. Perfis Expandidos (10 Features) e Bias Regionais
# Ordem dos pesos: [Luxo, Lazer, Urbano, Pet, Kids, Acess, Segur, Preco, Silenc, Capac]
profiles = {
    'lazer_familia': {
        'weights': [0.4, 0.9, -0.2, 0.2, 0.8, 0.4, 0.7, -0.3, 0.5, 0.9],
        'bias': {'Interior': 0.5, 'Frio/Serra': -0.3}
    },
    'pet_owner': {
        'weights': [0.3, 0.5, 0.2, 1.5, 0.4, 0.3, 0.5, -0.4, 0.6, 0.4],
        'bias': {'Sao Paulo': -0.3, 'Interior': 0.4}
    },
    'com_filhos': {
        'weights': [0.5, 1.0, -0.3, 0.3, 1.5, 0.5, 0.9, -0.5, 0.4, 1.2],
        'bias': {'Frio/Serra': -0.8, 'Litoral/Parques': 0.6}
    },
    'com_idosos': {
        'weights': [0.8, 0.3, -0.4, 0.0, 0.2, 1.5, 0.9, -0.2, 1.0, 0.5],
        'bias': {'Frio/Serra': -1.0, 'Interior': 0.5}
    },
    'casal_luxo': {
        'weights': [1.5, 0.6, 0.2, 0.1, 0.0, 0.2, 0.7, -0.8, 1.2, 0.2],
        'bias': {'Frio/Serra': 0.8, 'Sao Paulo': -0.2}
    },
    'business': {
        'weights': [0.4, -0.5, 1.5, 0.0, 0.0, 0.2, 0.9, -0.6, 1.2, 0.2],
        'bias': {'Sao Paulo': 0.8, 'Interior': -0.5}
    }
}

# 3. Geração das Avaliações com a Regra 80/20 e Penalidade Lambda
evaluations = []
for u_id in range(N_USUARIOS):
    if u_id < 50:
        n_ratings = np.random.randint(30, 50)
    else:
        n_ratings = np.random.randint(1, 11)
        
    p_names = list(profiles.keys())
    primary_p = np.random.choice(p_names)
    secondary_p = np.random.choice(p_names)
    
    chosen_hotels = np.random.choice(df_hotels.index, n_ratings, replace=False)
    
    for idx, h_id in enumerate(chosen_hotels):
        current_p = primary_p if idx < 3 else secondary_p
        h_data = df_hotels.loc[h_id]
        features_val = h_data[FEATURES].values.astype(float)
        
        # Probabilidade 80/20 de Ruído (O usuário avalia tudo de forma aleatória)
        if np.random.random() < 0.20:
            ratings_vector = np.random.randint(1, 6, size=len(FEATURES))
            logica = "Aleatório (Ruído)"
        else:
            # O usuário avalia cada feature com base no que o hotel realmente é, 
            # escalonando de 0-1 para 1-5, somado a um ruído de percepção.
            # Essa é a variável target perfeita para o seu algoritmo aprender as preferências!
            ruido_percepcao = np.random.normal(0, 0.5, size=len(FEATURES))
            ratings_vector = np.clip(np.round(features_val * 4 + 1 + ruido_percepcao), 1, 5)
            logica = "Perfil+Região+Tradeoff"
            
        evaluations.append({
            'user_id': f'U{u_id:03d}', 'hotel_id': h_id, 
            'perfil': current_p, 'regiao': h_data['regiao'], 'logica': logica,
            # Mapeamento estrito para as 10 colunas do BD
            'nota_luxo': int(ratings_vector[0]),
            'nota_lazer': int(ratings_vector[1]),
            'nota_urbano': int(ratings_vector[2]),
            'nota_pet_friendly': int(ratings_vector[3]),
            'nota_kids_friendly': int(ratings_vector[4]),
            'nota_acessibilidade': int(ratings_vector[5]),
            'nota_seguranca': int(ratings_vector[6]),
            'nota_preco': int(ratings_vector[7]),
            'nota_silencio': int(ratings_vector[8]),
            'nota_capacidade': int(ratings_vector[9])
        })

df_ratings = pd.DataFrame(evaluations)
