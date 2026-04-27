import numpy as np
import pandas as pd
import math

class RecomendacaoController:
    def __init__(self, db_connection, df_hoteis_features):
        self.conn = db_connection
        self.df_hoteis = df_hoteis_features 
        self.tamanho_pagina = 5
        self.alpha_adaptacao = 0.85 # 85% do peso vai para a tela atual, permitindo a "mudança brusca"
        
        self.sessao = {
            'id_usuario': None,
            'contexto_dict': None,
            'vetor_final_busca': None,
            'algoritmo_ativo': 'KNN',
            'hoteis_exibidos': [], 
            'posicao_absoluta_atual': 0
        }

    def iniciar_sessao(self, id_usuario, respostas_formulario):
        self.sessao['id_usuario'] = id_usuario
        self.sessao['contexto_dict'] = respostas_formulario
        self.sessao['hoteis_exibidos'] = []
        self.sessao['posicao_absoluta_atual'] = 0
        
        vetor_contexto = self._build_context_vector(respostas_formulario)
        
        df_historico = pd.read_sql_query(
            f"SELECT id_hotel, nota FROM avaliacoes WHERE id_usuario = '{id_usuario}'", 
            self.conn
        )
        
        if df_historico.empty:
            self.sessao['vetor_final_busca'] = vetor_contexto
        else:
            vetor_perfil = self._build_user_profile(df_historico)
            self.sessao['vetor_final_busca'] = (self.alpha_adaptacao * vetor_contexto) + ((1 - self.alpha_adaptacao) * vetor_perfil)

    def carregar_recomendacoes(self):
        vetor = self.sessao['vetor_final_busca']
        offset = self.sessao['posicao_absoluta_atual']
        regiao = self.sessao['contexto_dict'].get("regiao")
        
        if self.sessao['algoritmo_ativo'] == 'KNN':
            novos_hoteis = self._computar_knn(vetor, regiao, offset, self.tamanho_pagina)
        else:
            novos_hoteis = self._computar_fm(vetor, regiao, offset, self.tamanho_pagina)
            
        self.sessao['hoteis_exibidos'].extend(novos_hoteis)
        self.sessao['posicao_absoluta_atual'] += self.tamanho_pagina
        
        return novos_hoteis

    def alternar_algoritmo(self, novo_algoritmo):
        self.sessao['algoritmo_ativo'] = novo_algoritmo
        self.sessao['hoteis_exibidos'] = []
        self.sessao['posicao_absoluta_atual'] = 0
        return self.carregar_recomendacoes()

    def finalizar_com_avaliacao(self, id_hotel_escolhido, nota_dada):
        lista_ids_exibidos = [h['id_hotel'] for h in self.sessao['hoteis_exibidos']]
        posicao_global_clique = lista_ids_exibidos.index(id_hotel_escolhido) + 1
        
        cursor = self.conn.cursor()
        # Salva a avaliação e a posição exata para o NDCG Global futuro
        cursor.execute('''
            INSERT INTO avaliacoes (id_usuario, id_hotel, nota, contexto_viagem, logica_geracao, posicao_exibicao)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            self.sessao['id_usuario'], 
            id_hotel_escolhido, 
            nota_dada, 
            str(self.sessao['contexto_dict']), 
            self.sessao['algoritmo_ativo'], 
            posicao_global_clique
        ))
        self.conn.commit()
        
        return self._gerar_dashboard_metricas_globais()

    # ==========================================
    # LÓGICA MATEMÁTICA E ALGORITMOS
    # ==========================================

    def _build_context_vector(self, context):
        features = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        vetor = np.full(len(features), 0.1) # Evita divisao por zero
        
        tipo = context.get("tipo_viagem", "")
        if tipo == "negocios":
            vetor[2] = 1.0; vetor[8] = 0.9; vetor[1] = 0.0
        elif tipo == "familiar":
            vetor[1] = 1.0; vetor[6] = 0.8; vetor[9] = 0.8
        elif tipo == "lua_de_mel":
            vetor[0] = 1.0; vetor[8] = 0.8
        elif tipo == "com amigos":
            vetor[1] = 0.9; vetor[9] = 0.9; vetor[2] = 0.7
            
        if context.get("pet_friendly"): vetor[3] = 1.0
        if context.get("kids_friendly"): vetor[4] = 1.0
        if context.get("idosos"): vetor[5] = 1.0
        
        vetor[7] = 0.2 if tipo in ["lua_de_mel", "luxo"] else 0.8
        return vetor

    def _build_user_profile(self, user_ratings_df):
        merged = user_ratings_df.merge(self.df_hoteis, on="id_hotel")
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        
        weights = merged["nota"].values.reshape(-1, 1)
        features = merged[features_cols].values
        
        return np.sum(features * weights, axis=0) / np.sum(weights)

    def _filtrar_por_regiao(self, regiao):
        if regiao:
            return self.df_hoteis[self.df_hoteis["regiao"] == regiao].copy()
        return self.df_hoteis.copy()

    def _computar_knn(self, final_vector, regiao, offset, limit):
        df_filtrado = self._filtrar_por_regiao(regiao)
        if df_filtrado.empty: return []
            
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        hotel_vectors = df_filtrado[features_cols].values
        
        # Produto escalar vetorizado
        dot_products = np.dot(hotel_vectors, final_vector)
        norm_hoteis = np.linalg.norm(hotel_vectors, axis=1)
        norm_busca = np.linalg.norm(final_vector)
        
        # Cosseno com trava contra NaN
        similaridades = dot_products / ((norm_hoteis * norm_busca) + 1e-9)
        
        indices_ordenados = np.argsort(similaridades)[::-1]
        indices_pagina = indices_ordenados[offset : offset + limit]
        
        return [{"id_hotel": df_filtrado.index[i], "score": similaridades[i]} for i in indices_pagina]

    def _computar_fm(self, final_vector, regiao, offset, limit):
        df_filtrado = self._filtrar_por_regiao(regiao)
        if df_filtrado.empty: return []
            
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        matriz_hoteis = df_filtrado[features_cols].values
        
        scores_base = np.dot(matriz_hoteis, final_vector)
        
        # Emulação da penalidade FM (interação latente Luxo x Urbano)
        lambda_penalty = 0.6
        penalidades = lambda_penalty * (matriz_hoteis[:, 0] * matriz_hoteis[:, 2])
        
        scores_finais = scores_base - penalidades
        
        indices_ordenados = np.argsort(scores_finais)[::-1]
        indices_pagina = indices_ordenados[offset : offset + limit]
        
        return [{"id_hotel": df_filtrado.index[i], "score": scores_finais[i]} for i in indices_pagina]

    # ==========================================
    # MÉTRICAS E AVALIAÇÃO (Tratando Edge Cases)
    # ==========================================

    def _gerar_dashboard_metricas_globais(self):
        try:
            df_todas = pd.read_sql_query("SELECT nota, posicao_exibicao, logica_geracao, id_hotel, id_usuario FROM avaliacoes", self.conn)
        except:
            return {"erro": "Coluna 'posicao_exibicao' não encontrada no banco."}

        # 1. RMSE Global (Apenas para FM - Clipando valores fora de 1-5)
        df_fm = df_todas[df_todas['logica_geracao'] == 'FM']
        rmse_global = None
        if not df_fm.empty:
            erros_sq = []
            for _, row in df_fm.iterrows():
                pred = self._obter_predicao_fm_mock(row['id_hotel']) 
                pred_clip = max(1.0, min(5.0, pred)) # Tratamento de borda da fatoração
                erros_sq.append((row['nota'] - pred_clip) ** 2)
            rmse_global = math.sqrt(np.mean(erros_sq))

        # 2. NDCG Global (Apenas para K-NN - Usando log base 2 absoluto)
        df_knn = df_todas[df_todas['logica_geracao'] == 'KNN']
        ndcg_global = None
        if not df_knn.empty:
            ndcg_lista = []
            for _, row in df_knn.iterrows():
                pos = row['posicao_exibicao']
                if pd.notna(pos) and pos > 0:
                    relevancia = 1.0 / math.log2(pos + 1)
                    ndcg_lista.append(relevancia)
            ndcg_global = np.mean(ndcg_lista)

        return {
            'RMSE_Global_FM': round(rmse_global, 3) if rmse_global else "Aguardando dados FM",
            'NDCG_Global_KNN': round(ndcg_global, 3) if ndcg_global else "Aguardando dados KNN"
        }

    def _obter_predicao_fm_mock(self, id_hotel):
        # Em um cenário real de fatoração pesada, isso leria a matriz latente gerada pelo PyTorch/TF.
        # Aqui, emulamos uma nota para fechar a métrica.
        return 4.5