import streamlit as st
import pandas as pd
from teste_basico import validar_integracao
from recomendacao_controller import RecomendacaoController
from ui_data import (
    authenticate_user, create_user, ensure_database_ready,
    get_catalog_coverage, get_ratings_by_context, get_ratings_by_region,
    get_rating_distribution, get_connection
)
from enum import Enum

# Nova estrutura centralizada
class AppState(Enum):
    PAGE = "pagina_atual"
    USER_ID = "user_id"
    AUTH = "is_authenticated"
    RECS_DF = "recs_df"
    CONTROLLER = "controladora_sessao"
    LOGIN = "login"
    PERFIL = "perfil_base"
    CONTEXTO = "contexto_viagem"
    METRICAS = "metricas_calculadas"
    RAW_RECS = "raw_recs"

class Pages(Enum):
    QUESTIONS = "Perguntas de viagem"
    RECOMMENDATIONS = "Recomendacoes"
    RATING = "Avaliacao"
    METRICS = "Metricas"

class Algorithms(Enum):
    KNN = "KNN"
    FM = "FM"
    
PERFIS = ["business", "casal_luxo", "lazer_familia", "pet_owner", "com_filhos", "com_idosos"]
REGIOES = ["Sao Paulo", "Frio/Serra", "Interior", "Litoral/Parques"]

def init_state() -> None:
    defaults = {
        AppState.AUTH.value: False,
        AppState.USER_ID.value: None,
        AppState.PAGE.value: Pages.QUESTIONS.value,
        AppState.LOGIN.value: None,
        AppState.PERFIL.value: None,
        AppState.CONTEXTO.value: None,
        AppState.RECS_DF.value: None,
        AppState.CONTROLLER.value: None,
        AppState.PAGE.value: Pages.QUESTIONS.value,
        AppState.METRICAS.value: None,
        AppState.RAW_RECS.value: None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def obter_controladora():
    """Garante que a controladora tenha conexão fresca com o banco sem quebrar o Streamlit"""
    conn = get_connection()
    df_hoteis = pd.read_sql_query("SELECT * FROM hoteis", conn, index_col='id_hotel')
    
    controller = RecomendacaoController(conn, df_hoteis)
    
    # Restaura o estado da sessão anterior, se existir
    if st.session_state["controladora_sessao"]:
        controller.sessao = st.session_state["controladora_sessao"]
        
    return controller, conn


def render_login_screen() -> None:
    st.title("Sistema de Recomendação de Hotéis")
    st.subheader("Login e Cadastro")

    tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])

    with tab_login:
        with st.form("login_form"):
            login = st.text_input("Login")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
            if submit:
                user = authenticate_user(login, senha)
                if user is None:
                    st.error("Credenciais invalidas.")
                else:
                    st.session_state["is_authenticated"] = True
                    st.session_state["user_id"] = user["id_usuario"]
                    st.session_state["login"] = user["login"]
                    st.session_state["perfil_base"] = user["perfil_base"]
                    st.success("Login realizado com sucesso.")
                    st.rerun()

    with tab_cadastro:
        with st.form("cadastro_form"):
            novo_login = st.text_input("Novo login")
            nova_senha = st.text_input("Nova senha", type="password")
            perfil = st.selectbox("Perfil base", PERFIS)
            submit = st.form_submit_button("Cadastrar")
            if submit:
                if not novo_login.strip() or not nova_senha.strip():
                    st.warning("Preencha login e senha.")
                else:
                    user_id = create_user(novo_login, nova_senha, perfil)
                    if user_id is None:
                        st.error("Login já existente. Escolha outro.")
                    else:
                        st.success("Cadastro concluido. Agora faça login.")

def enriquecer_e_normalizar_recomendacoes(df_recs: pd.DataFrame, conn, algo_ativo: str) -> pd.DataFrame:
    """Adiciona dados de exibição e normaliza scores para uma escala de 1 a 5."""
    if df_recs.empty:
        return df_recs
        
    df_detalhes = pd.read_sql_query(
        "SELECT id_hotel, nome, regiao, preco, luxo FROM hoteis", conn
    )
    df_recs = df_recs.merge(df_detalhes, on="id_hotel", how="left")

    s_min = df_recs['score'].min()
    s_max = df_recs['score'].max()
    
    if s_max > s_min:
        if algo_ativo == Algorithms.KNN.value:
            # KNN: Menor distância é melhor (inversão)
            df_recs['afinidade'] = ((s_max - df_recs['score']) / (s_max - s_min) * 4) + 1
        else:
            # FM: Maior probabilidade é melhor (direto)
            df_recs['afinidade'] = ((df_recs['score'] - s_min) / (s_max - s_min) * 4) + 1
    else:
        df_recs['afinidade'] = 5.0

    # NOVO: Cálculo matemático do Preço Sintético
    # Utilizamos clip para tratar o caso de borda de valores negativos ou acima de 1
    p_seguro = df_recs['preco'].clip(lower=0, upper=1)
    l_seguro = df_recs['luxo'].clip(lower=0, upper=1)
    
    # Se 'preco' alto no banco significa 'barato', use: (1 - p_seguro) na fórmula abaixo
    c_base = 150.0
    alpha = 400.0
    beta = 600.0
    
    df_recs['preco_exibicao'] = c_base + (p_seguro * alpha) + (l_seguro * beta)

    # ALTERADO: Retornamos 'preco_exibicao' em vez do 'preco' cru
    return df_recs[['nome', 'regiao', 'preco_exibicao', 'luxo', 'afinidade', 'id_hotel']]


def render_questions_screen() -> None:
    st.header("Perguntas sobre a viagem")
    st.write("Defina o contexto atual para personalizar suas recomendações.")

    with st.form("questions_form"):
        regiao = st.selectbox("Região desejada", REGIOES)
        tipo_viagem = st.selectbox("Tipo de viagem", ["familiar", "negocios", "com amigos", "lua_de_mel"])
        
        st.write("Atendimentos específicos necessários:")
        pet_friendly = st.checkbox("Pet Friendly (Animais de estimação)")
        kids_friendly = st.checkbox("Kids Friendly (Crianças)")
        idosos = st.checkbox("Acessibilidade (Idosos/PCD)")
        
        submit = st.form_submit_button("Gerar recomendações")
        
        if submit:
            contexto = {
                "regiao": regiao,
                "tipo_viagem": tipo_viagem,
                "pet_friendly": pet_friendly,
                "kids_friendly": kids_friendly,
                "idosos": idosos,
            }
            st.session_state[AppState.CONTEXTO.value] = contexto
            
            # 1. Instancia e inicia a sessão na controladora
            controller, conn = obter_controladora()
            controller.iniciar_sessao(st.session_state[AppState.USER_ID.value], contexto)
            
            # 2. Roda os algoritmos pesados
            with st.spinner("A calcular as melhores recomendações (KNN/FM)..."):
                hoteis_recomendados = controller.carregar_recomendacoes()
                
            st.session_state[AppState.CONTROLLER.value] = controller.sessao
            
            # 3. Formata para exibição usando a função arquitetada (NOVO LOCAL CORRETO)
            df_bruto = pd.DataFrame(hoteis_recomendados)
            st.session_state[AppState.RAW_RECS.value] = df_bruto
            
            algo_ativo = controller.sessao.get('algoritmo_ativo', Algorithms.KNN.value)
            df_recs = enriquecer_e_normalizar_recomendacoes(df_bruto, conn, algo_ativo)
            
            # Salva o dataframe pronto para a tela
            st.session_state[AppState.RECS_DF.value] = df_recs
            
            st.session_state[AppState.PAGE.value] = Pages.RECOMMENDATIONS.value
            st.success("Recomendações moduladas para o seu contexto atual!")
            
            conn.close()
            st.rerun()


def render_recommendations_screen() -> None:
    st.header("Recomendações")
    recs_df = st.session_state.get("recs_df")
    
    if recs_df is None or recs_df.empty:
        st.warning("Não há recomendações disponíveis para o contexto atual.")
        return

    # ALTERADO: Configuração das colunas refletindo o cálculo sintético
    st.dataframe(
        recs_df.drop(columns=['id_hotel']), # Mantemos o ID oculto
        column_config={
            "nome": "Nome do Hotel",
            "regiao": "Localização",
            # Mapeamos a nova coluna com formatação monetária realística
            "preco_exibicao": st.column_config.NumberColumn("Preço Estimado", format="R$ %.2f"),
            "luxo": st.column_config.NumberColumn("Índice de Luxo", format="%.2f"),
            "afinidade": st.column_config.ProgressColumn("Match com seu Perfil", min_value=1, max_value=5, format="%.1f")
        },
        use_container_width=True,
        hide_index=True
    )

    controller, conn = obter_controladora()

    # Controles da Tela (Exibir Mais, Troca de Algoritmo e Abandono)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("Carregar Mais Opções"):
            novos_dados = controller.carregar_recomendacoes()
            st.session_state[AppState.CONTROLLER.value] = controller.sessao
            
            if novos_dados:
                # 1. Recuperamos com segurança a memória inicial do AppState
                df_atual_bruto = st.session_state.get(AppState.RAW_RECS.value)
                if df_atual_bruto is None:
                    df_atual_bruto = pd.DataFrame()
                    
                df_novo_bruto = pd.DataFrame(novos_dados)
                
                # 2. Empilhamos (Concat) Antigos + Novos
                df_total_bruto = pd.concat([df_atual_bruto, df_novo_bruto], ignore_index=True)
                
                # 3. Atualizamos a memória com o novo total para o próximo clique
                st.session_state[AppState.RAW_RECS.value] = df_total_bruto
                
                # 4. Normalizamos as estrelas considerando todos os hotéis juntos
                algo_ativo = controller.sessao.get('algoritmo_ativo', Algorithms.KNN.value)
                df_recs_atualizado = enriquecer_e_normalizar_recomendacoes(df_total_bruto, conn, algo_ativo)
                
                st.session_state[AppState.RECS_DF.value] = df_recs_atualizado
            st.rerun()

    with c2:
        algo_atual = controller.sessao['algoritmo_ativo']
        opcoes_algo = [a.value for a in Algorithms]
        novo_algo = st.selectbox("Algoritmo Ativo", opcoes_algo, 
                                 index=0 if algo_atual == Algorithms.KNN.value else 1)
        
        if novo_algo != algo_atual:
            novos_dados = controller.alternar_algoritmo(novo_algo)
            st.session_state[AppState.CONTROLLER.value] = controller.sessao
            
            # 3. Refazemos o DataFrame do zero com o novo algoritmo
            df_total_bruto = pd.DataFrame(novos_dados)
            st.session_state[AppState.RAW_RECS.value] = df_total_bruto
            
            df_recs_novo = enriquecer_e_normalizar_recomendacoes(df_total_bruto, conn, novo_algo)
            st.session_state[AppState.RECS_DF.value] = df_recs_novo
            st.rerun()

    with c3:
        if st.button("Sair sem escolher (Abandono)", type="primary"):
            metricas = controller.registrar_abandono()
            st.session_state[AppState.METRICAS.value] = metricas
            
            # ADICIONADO: Limpeza total do fluxo de recomendação
            st.session_state[AppState.CONTROLLER.value] = None
            st.session_state[AppState.RECS_DF.value] = None
            st.session_state[AppState.RAW_RECS.value] = None
            
            st.session_state[AppState.PAGE.value] = Pages.METRICS.value
            conn.close()
            st.rerun()
            
    conn.close()
    
    st.divider()
    if st.button("Ir para Avaliação ->"):
        st.session_state[AppState.PAGE.value] = Pages.RATING.value
        st.rerun()


def render_rating_screen() -> None:
    st.header("Avaliação do Hotel Escolhido")
    recs_df = st.session_state.get("recs_df")
    
    if recs_df is None or recs_df.empty:
        st.info("Gere e visualize recomendações antes de avaliar.")
        return

    with st.form("rating_form"):
        opcoes_hoteis = recs_df["id_hotel"].tolist()
        hotel_id = st.selectbox("Qual hotel você efetivamente escolheu?", opcoes_hoteis)
        nota = st.slider("Como foi a sua experiência? (1 a 5)", 1, 5, 4)
        
        submit = st.form_submit_button("Confirmar Avaliação e Ver Métricas")
        if submit:
            controller, conn = obter_controladora()
            metricas = controller.finalizar_com_avaliacao(hotel_id, nota)
            
            st.session_state["metricas_calculadas"] = metricas
            st.session_state["controladora_sessao"] = None # Sessão finalizada
            st.session_state["pagina_atual"] = "Metricas" # Direciona para o fim
            conn.close()
            st.rerun()

def render_metrics_screen() -> None:
    st.header("Métricas de Performance")
    
    # Recupera os dados usando o Enum que estabelecemos
    metricas = st.session_state.get(AppState.METRICAS.value)
    
    if not metricas:
        st.info("Aguardando finalização de uma sessão para exibir métricas.")
        return

    # --- SEÇÃO 1: Resultado da Sessão Atual ---
    st.subheader("Resultado do Ciclo Atual")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        cor = "normal" if metricas.get('status_sessao') == 'sucesso' else "inverse"
        st.metric("Status", metricas.get('status_sessao', 'N/A').upper(), delta_color=cor)
    with c2:
        st.metric("Algoritmo Ativo", metricas.get('algoritmo_utilizado'))
    with c3:
        st.metric("Hotéis Tentados", metricas.get('hoteis_apresentados'))

    if metricas.get('status_sessao') == 'abandono':
        st.error("O usuário saiu sem escolher. O algoritmo não converteu nesta tentativa.")
    else:
        st.success("Conversão realizada! O usuário escolheu um dos hotéis sugeridos.")

    # --- SEÇÃO 2: Saúde Global do Sistema (Contexto) ---
    st.divider()
    st.subheader("Indicadores de Acurácia Global")
    st.write("Estes dados mostram o desempenho médio do sistema para todos os usuários.")
    
    g1, g2 = st.columns(2)
    with g1:
        rmse = metricas.get('RMSE_Global_FM')
        st.metric("RMSE (Factorization Machines)", rmse, 
                  help="Erro Quadrático Médio. Quanto menor, mais precisa é a predição de notas.")
    with g2:
        ndcg = metricas.get('NDCG_Global_KNN')
        # Formata se for número, senão exibe o texto de "Aguardando"
        val_ndcg = f"{ndcg:.3f}" if isinstance(ndcg, (int, float)) else ndcg
        st.metric("NDCG (K-Nearest Neighbors)", val_ndcg, 
                  help="Qualidade do Ranking. Quanto mais próximo de 1.0, melhores são as posições dos hotéis sugeridos.")


def render_authenticated_app() -> None:
    st.sidebar.title("Navegação")
    st.sidebar.write(f"Usuario: {st.session_state[AppState.LOGIN.value]}")
    st.sidebar.write(f"Perfil base: {st.session_state[AppState.PERFIL.value]}")

    if st.sidebar.button("Sair / Reset"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_state()
        st.rerun()
    
    opcoes_telas = [p.value for p in Pages]
    
    try:
        index_atual = opcoes_telas.index(st.session_state[AppState.PAGE.value])
    except ValueError:
        index_atual = 0
        
    page = st.sidebar.radio("Telas", opcoes_telas, index=index_atual)
    
    # Se o usuário clicar manualmente na sidebar, obedece
    if page != st.session_state[AppState.PAGE.value]:
        st.session_state[AppState.PAGE.value] = page
        st.rerun()

    if page == Pages.QUESTIONS.value:
        render_questions_screen()
    elif page == Pages.RECOMMENDATIONS.value:
        render_recommendations_screen()
    elif page == Pages.RATING.value:
        render_rating_screen()
    elif page == Pages.METRICS.value:
        render_metrics_screen()


def main() -> None:
    st.set_page_config(page_title="MVP Recomendacao", layout="wide")
    # --- ARQUITETURA DE INICIALIZAÇÃO ÚNICA ---
    @st.cache_resource
    def executar_setup_inicial():
        """
        Executa o teste básico e a população do banco apenas uma vez
        quando o servidor do Streamlit inicia.
        """
        validar_integracao()
        return True

    # Chama a função de setup (o cache garante que só rode no primeiro carregamento)
    executar_setup_inicial()
    
    init_state()

    if st.session_state["is_authenticated"]:
        render_authenticated_app()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
