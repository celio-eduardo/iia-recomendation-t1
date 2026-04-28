import numpy as np
import pandas as pd
import math
import json

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
        # Pesos TF-IDF calculados uma vez sobre o catálogo completo
        self.idf_weights = self._compute_idf_weights()

    def _compute_idf_weights(self):
        """
        Calcula IDF (Inverse Document Frequency) para cada uma das 10 features.
        No contexto de recomendação baseada em conteúdo:
          - 'Documento' = hotel; 'Termo' = feature (luxo, lazer, ...).
          - TF já está implícito no valor da feature em [0,1].
          - DF = nº de hotéis com feature ACIMA da média do catálogo (feature 'presente').
          - IDF = log(N / DF) + 1  →  features raras/distintivas ganham peso maior.
        O vetor IDF é normalizado para [idf_min, 1] para não distorcer a escala dos scores.
        Referência: Salton & Buckley (1988), "Term-weighting approaches in automatic text retrieval".
        """
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly",
                         "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        matrix = self.df_hoteis[features_cols].values.astype(float)
        N = len(matrix)
        if N == 0:
            return np.ones(len(features_cols))

        col_means = matrix.mean(axis=0)
        # df_counts: quantos hotéis têm feature acima da média (+1 suavização de Laplace)
        df_counts = (matrix > col_means).sum(axis=0) + 1
        idf = np.log(N / df_counts) + 1.0   # +1 garante idf >= 1 mesmo para features universais
        return idf / idf.max()               # normaliza relativo ao peso máximo

    def iniciar_sessao(self, id_usuario, respostas_formulario):
        self.sessao['id_usuario'] = id_usuario
        self.sessao['contexto_dict'] = respostas_formulario
        self.sessao['hoteis_exibidos'] = []
        self.sessao['posicao_absoluta_atual'] = 0
        
        vetor_contexto = self._build_context_vector(respostas_formulario)
        
        # O QUE MUDA: Selecionamos apenas as colunas de features vetoriais do usuário
        query_historico = f"""
            SELECT 
                nota_luxo, nota_lazer, nota_urbano, nota_pet_friendly, nota_kids_friendly, 
                nota_acessibilidade, nota_seguranca, nota_preco, nota_silencio, nota_capacidade 
            FROM avaliacoes 
            WHERE id_usuario = '{id_usuario}'
        """
        df_historico = pd.read_sql_query(query_historico, self.conn)
        
        if df_historico.empty:
            self.sessao['vetor_final_busca'] = vetor_contexto
        else:
            vetor_perfil = self._build_user_profile(df_historico)
            self.sessao['vetor_final_busca'] = (self.alpha_adaptacao * vetor_contexto) + ((1 - self.alpha_adaptacao) * vetor_perfil)

    def carregar_recomendacoes(self):
        if self.sessao.get('contexto_dict') is None:
            return []
        
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
    
    def registrar_abandono(self) -> dict:
        """Registra o abandono na telemetria e retorna métricas locais e globais."""
        # Correção da chave: Usamos 'hoteis_exibidos' que é a chave real da sessão
        historico = self.sessao.get("hoteis_exibidos", [])
        total = len(historico)
        algo = self.sessao.get("algoritmo_ativo", "Desconhecido")
        
        # 1. Grava a telemetria (Telemetria != Matriz de Utilidade)
        self._registrar_log_sessao(converteu=False)
        
        # 2. Busca as métricas globais para dar contexto ao desenvolvedor
        metricas_globais = self._gerar_dashboard_metricas_globais()
        
        # 3. Unifica os dados
        metricas_final = {
            "status_sessao": "abandono",
            "algoritmo_utilizado": algo,
            "hoteis_apresentados": total,
            "precisao_sessao": 0.0,
            **metricas_globais # Mescla RMSE e NDCG globais aqui
        }
        
        self.sessao = {} 
        return metricas_final

    def finalizar_com_avaliacao(self, id_hotel_escolhido, avaliacoes_detalhadas: dict):
        # 1. CAPTURA DE ESTADO (Blindagem contra limpeza prematura)
        lista_ids_exibidos = [h['id_hotel'] for h in self.sessao.get('hoteis_exibidos', [])]
        algo_usado = self.sessao.get('algoritmo_ativo', 'Desconhecido')
        total_hoteis = len(lista_ids_exibidos)
        
        if id_hotel_escolhido in lista_ids_exibidos:
            posicao_global_clique = lista_ids_exibidos.index(id_hotel_escolhido) + 1
        else:
            posicao_global_clique = total_hoteis if total_hoteis > 0 else 1    
        
        contexto_json = json.dumps(self.sessao['contexto_dict']) if self.sessao.get('contexto_dict') else "{}"
        
        # 2. PERSISTÊNCIA SQL
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO avaliacoes (
                id_usuario, id_hotel, contexto_viagem, logica_geracao, posicao_exibicao,
                nota_luxo, nota_lazer, nota_urbano, nota_pet_friendly, nota_kids_friendly,
                nota_acessibilidade, nota_seguranca, nota_preco, nota_silencio, nota_capacidade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.sessao.get('id_usuario'), id_hotel_escolhido, contexto_json, algo_usado, posicao_global_clique,
            avaliacoes_detalhadas.get('luxo', 3.0),
            avaliacoes_detalhadas.get('lazer', 3.0),
            avaliacoes_detalhadas.get('urbano', 3.0),
            avaliacoes_detalhadas.get('pet_friendly', 3.0),
            avaliacoes_detalhadas.get('kids_friendly', 3.0),
            avaliacoes_detalhadas.get('acessibilidade', 3.0),
            avaliacoes_detalhadas.get('seguranca', 3.0),
            avaliacoes_detalhadas.get('preco', 3.0),
            avaliacoes_detalhadas.get('silencio', 3.0),
            avaliacoes_detalhadas.get('capacidade', 3.0)
        ))
        self.conn.commit()
        
        # 3. REGISTRO DE TELEMETRIA
        self._registrar_log_sessao(converteu=True)
        
        # 4. INJEÇÃO DE MÉTRICAS (O dicionário final recebe as variáveis blindadas)
        metricas_sucesso = self._gerar_dashboard_metricas_globais()
        metricas_sucesso["status_sessao"] = "sucesso"
        metricas_sucesso["algoritmo_utilizado"] = algo_usado
        metricas_sucesso["hoteis_apresentados"] = total_hoteis
        
        # 5. LIMPEZA SEGURA DA SESSÃO (Última operação)
        self.sessao = {}
        
        return metricas_sucesso

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
        # A nova teoria: O perfil latente do usuário é a média do que ele avaliou.
        # Nós extraímos a matriz [N x 10] do dataframe de histórico
        matriz_notas = user_ratings_df.values
        
        # EDGE CASE RESOLVIDO: Normalização de [1-5] para [0-1]
        matriz_notas_normalizada = (matriz_notas - 1.0) / 4.0
        
        # np.nanmean lida com o caso de borda de colunas nulas ou em branco
        perfil_medio = np.nanmean(matriz_notas_normalizada, axis=0)
        
        # Tratamento de caso de borda de NaN remanescente (caso o usuário mandou vetor vazio)
        return np.nan_to_num(perfil_medio, nan=0.1)

    def _filtrar_por_regiao(self, regiao):
        if regiao:
            return self.df_hoteis[self.df_hoteis["regiao"] == regiao].copy()
        return self.df_hoteis.copy()
    # Exemplo de adaptação no retorno do KNN e FM:
    def _gerar_justificativa(self, vetor_hotel, vetor_busca):
        features = ["Luxo", "Lazer", "Urbano", "Pet", "Kids", "Acess.", "Segur.", "Preço", "Silêncio", "Capac."]
        # Identifica onde houve a maior coincidência de valores altos (produto elemento a elemento)
        contribuicao = vetor_hotel * vetor_busca
        top_feature_idx = np.argmax(contribuicao)
        return f"Destaque: {features[top_feature_idx]}"
    
    def _computar_knn(self, final_vector, regiao, offset, limit):
        df_filtrado = self._filtrar_por_regiao(regiao)
        if df_filtrado.empty: return []
            
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        hotel_vectors = df_filtrado[features_cols].values

        # --- TF-IDF: pondera features por raridade no catálogo ---
        # TF já está implícito nos valores [0,1]; multiplica pelo IDF pré-computado.
        hotel_vectors_tfidf = hotel_vectors * self.idf_weights
        final_vector_tfidf  = final_vector  * self.idf_weights

        # Similaridade de cosseno no espaço TF-IDF
        dot_products = np.dot(hotel_vectors_tfidf, final_vector_tfidf)
        norm_hoteis  = np.linalg.norm(hotel_vectors_tfidf, axis=1)
        norm_busca   = np.linalg.norm(final_vector_tfidf)
        similaridades = dot_products / ((norm_hoteis * norm_busca) + 1e-9)
        
        indices_ordenados = np.argsort(similaridades)[::-1]
        indices_pagina = indices_ordenados[offset : offset + limit]
        
        return [
            {
                "id_hotel": df_filtrado.index[i], 
                "score": similaridades[i],
                "justificativa": self._gerar_justificativa(hotel_vectors[i], final_vector)
            } for i in indices_pagina
        ]

    def _computar_fm(self, final_vector, regiao, offset, limit):
        df_filtrado = self._filtrar_por_regiao(regiao)
        if df_filtrado.empty: return []
            
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        matriz_hoteis = df_filtrado[features_cols].values

        # --- TF-IDF: pondera features por raridade antes do produto escalar ---
        matriz_tfidf       = matriz_hoteis * self.idf_weights
        final_vector_tfidf = final_vector  * self.idf_weights

        scores_base = np.dot(matriz_tfidf, final_vector_tfidf)

        # Penalidade FM: interação latente Luxo x Urbano (aplicada nos valores originais)
        lambda_penalty = 0.6
        penalidades = lambda_penalty * (matriz_hoteis[:, 0] * matriz_hoteis[:, 2])
        
        scores_finais = scores_base - penalidades
        
        indices_ordenados = np.argsort(scores_finais)[::-1]
        indices_pagina = indices_ordenados[offset : offset + limit]
        
        return [
            {
                "id_hotel": df_filtrado.index[i], 
                "score": scores_finais[i],
                "justificativa": self._gerar_justificativa(matriz_hoteis[i], final_vector)
            } for i in indices_pagina
        ]

    # ==========================================
    # MÉTRICAS E AVALIAÇÃO (Tratando Edge Cases)
    # ==========================================

    # Dentro da classe RecomendacaoController em recomendacao_controller.py

    def _registrar_log_sessao(self, converteu: bool):
        """Método privado para gravar a telemetria no banco."""
        historico = self.sessao.get("hoteis_exibidos", [])
        
        query = '''
            INSERT INTO log_sessoes (id_usuario, algoritmo_usado, qtd_exibida, converteu_em_escolha)
            VALUES (?, ?, ?, ?)
        '''
        self.conn.execute(query, (
            self.sessao.get("id_usuario"),
            self.sessao.get("algoritmo_ativo"),
            len(historico),
            1 if converteu else 0
        ))
        self.conn.commit()

    def _gerar_dashboard_metricas_globais(self):
        try:
            query = """
                SELECT 
                    (nota_luxo + nota_lazer + nota_urbano + nota_pet_friendly + nota_kids_friendly + 
                     nota_acessibilidade + nota_seguranca + nota_preco + nota_silencio + nota_capacidade) / 10.0 as nota_media,
                    posicao_exibicao, logica_geracao, id_hotel, id_usuario
                FROM avaliacoes
            """
            df_todas = pd.read_sql_query(query, self.conn)
        except Exception as e:
            return {"erro": f"Erro de esquema: {str(e)}"}

        df_fm = df_todas[df_todas['logica_geracao'].isin(['FM', 'Perfil+Região+Tradeoff'])]
        rmse_global = None
        if not df_fm.empty:
            erros_sq = []
            for _, row in df_fm.iterrows():
                # TRECHO CORRIGIDO: O Mock agora faz um predict real
                pred_real = self._obter_predicao_fm_real(row['id_hotel'], row['id_usuario'])
                erros_sq.append((row['nota_media'] - pred_real) ** 2)
            rmse_global = math.sqrt(np.mean(erros_sq))

        df_knn = df_todas[df_todas['logica_geracao'] == 'KNN']
        ndcg_global = None
        if not df_knn.empty:
            ndcg_lista = []
            for _, row in df_knn.iterrows():
                # TRATAMENTO DE EDGE CASE: Se for fake user (posicao nula), 
                # emulamos que ele achou o hotel na posição 3 (média probabilística)
                pos = row['posicao_exibicao'] if pd.notna(row['posicao_exibicao']) and row['posicao_exibicao'] > 0 else 3.0
                
                # Formula NDCG: DCG / IDCG. (Assumindo Ideal DCG onde o item estaria na posicao 1 -> 1.0)
                dcg = 1.0 / math.log2(pos + 1)
                idcg = 1.0 / math.log2(1 + 1)
                ndcg = dcg / idcg
                ndcg_lista.append(ndcg)
                
            ndcg_global = np.mean(ndcg_lista)

        return {
            'RMSE_Global_FM': round(rmse_global, 3) if rmse_global else "Aguardando",
            'NDCG_Global_KNN': round(ndcg_global, 3) if ndcg_global else 0.0
        }

    # TRECHO NOVO: Cálculo matemático substituindo o Mock cravado
    def _obter_predicao_fm_real(self, id_hotel, id_usuario):
        """Calcula a utilidade real baseada no produto escalar para fins de RMSE"""
        # Pega as características do hotel
        hoteis = self.df_hoteis.loc[self.df_hoteis.index == id_hotel]
        if hoteis.empty: return 3.0 # Fator de neutralidade
        
        features_cols = ["luxo", "lazer", "urbano", "pet_friendly", "kids_friendly", "acessibilidade", "seguranca", "preco", "silencio", "capacidade"]
        f_hotel = hoteis[features_cols].values[0]
        
        # Pega o histórico do usuário para traçar o perfil w
        query_hist = f"""
            SELECT nota_luxo, nota_lazer, nota_urbano, nota_pet_friendly, nota_kids_friendly, 
                   nota_acessibilidade, nota_seguranca, nota_preco, nota_silencio, nota_capacidade 
            FROM avaliacoes WHERE id_usuario = '{id_usuario}'
        """
        df_hist = pd.read_sql_query(query_hist, self.conn)
        if df_hist.empty: return 3.0
        
        w_usuario = self._build_user_profile(df_hist)
        
        # --- TRECHO CORRIGIDO ---
        # 1. Calcula o produto escalar (dot product) bruto
        dot_product = np.dot(w_usuario, f_hotel)
        
        # 2. Normaliza o resultado dividindo pelo número exato de dimensões (10)
        # Isso impede a 'explosão dimensional' garantindo que o valor fique no intervalo [0, 1]
        utilidade_norm = dot_product / 10.0 
        
        # 3. Projeta a utilidade normalizada de volta para a escala de 1 a 5 estrelas do sistema
        predicao_escala = (utilidade_norm * 4.0) + 1.0
        
        # 4. Garante que o valor final nunca passe dos limites de nota
        return np.clip(predicao_escala, 1.0, 5.0)