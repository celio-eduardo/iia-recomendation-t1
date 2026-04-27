import streamlit as st
import pandas as pd
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
        AppState.METRICAS.value: None
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
            st.session_state["contexto_viagem"] = contexto
            
            # 1. Instancia e inicia a sessão na controladora
            controller, conn = obter_controladora()
            controller.iniciar_sessao(st.session_state["user_id"], contexto)
            
            with st.spinner("A calcular as melhores recomendações (KNN/FM)..."):
                hoteis_recomendados = controller.carregar_recomendacoes()
                
            st.session_state["controladora_sessao"] = controller.sessao
            
            # Formata para exibição
            df_recs = pd.DataFrame(hoteis_recomendados)
            if not df_recs.empty:
                df_detalhes = pd.read_sql_query("SELECT id_hotel, nome, regiao FROM hoteis", conn)
                df_recs = df_recs.merge(df_detalhes, on="id_hotel", how="left")
            
            st.session_state["recs_df"] = df_recs
            # 3. Salva o estado da controladora na sessão do Streamlit
            st.session_state["controladora_sessao"] = controller.sessao
            
            st.session_state["pagina_atual"] = "Recomendacoes"
            
            st.success("Recomendações moduladas para o seu contexto atual!")
            conn.close()
            st.rerun()


def render_recommendations_screen() -> None:
    st.header("Recomendações")
    recs_df = st.session_state.get("recs_df")
    
    if recs_df is None or recs_df.empty:
        st.warning("Não há recomendações disponíveis para o contexto atual.")
        return

    st.dataframe(recs_df, use_container_width=True)

    controller, conn = obter_controladora()

    # Controles da Tela (Exibir Mais, Troca de Algoritmo e Abandono)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("Carregar Mais Opções"):
            novos = controller.carregar_recomendacoes()
            st.session_state["controladora_sessao"] = controller.sessao
            
            # Formata novos hoteis e anexa ao DataFrame existente
            if novos:
                df_novos = pd.DataFrame(novos)
                df_detalhes = pd.read_sql_query("SELECT id_hotel, nome, regiao FROM hoteis", conn)
                df_novos = df_novos.merge(df_detalhes, on="id_hotel", how="left")
                st.session_state["recs_df"] = pd.concat([st.session_state["recs_df"], df_novos], ignore_index=True)
            st.rerun()

    with c2:
        algo_atual = controller.sessao['algoritmo_ativo']
        opcoes_algo = [a.value for a in Algorithms]
        novo_algo = st.selectbox("Algoritmo Ativo", opcoes_algo, 
                             index=0 if algo_atual == Algorithms.KNN.value else 1)
        
        if novo_algo != algo_atual:
            novos = controller.alternar_algoritmo(novo_algo)
            st.session_state["controladora_sessao"] = controller.sessao
            
            # Refaz o DataFrame do zero
            df_novos = pd.DataFrame(novos)
            df_detalhes = pd.read_sql_query("SELECT id_hotel, nome, regiao FROM hoteis", conn)
            st.session_state["recs_df"] = df_novos.merge(df_detalhes, on="id_hotel", how="left")
            st.rerun()

    with c3:
        if st.button("Sair sem escolher (Abandono)", type="primary"):
            # Computa o erro de ranqueamento e redireciona
            metricas = controller.registrar_abandono()
            st.session_state["metricas_calculadas"] = metricas
            st.session_state["controladora_sessao"] = None # Limpa a sessão
            st.session_state["pagina_atual"] = "Metricas" # Direciona tela
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
    st.header("Métricas do Algoritmo")
    
    # Exibe o resultado do fluxo que acabou de ocorrer
    metricas = st.session_state.get("metricas_calculadas")
    if metricas:
        if metricas.get('status_sessao') == 'abandono':
            st.error("Sessão finalizada sem escolha. O algoritmo falhou em sugerir opções relevantes.")
        else:
            st.success("Avaliação computada. Ciclo finalizado com sucesso.")
            
        st.write("### Desempenho Global dos Algoritmos:")
        st.json(metricas)
    
    # Renderiza os gráficos padrões abaixo (distribuição, cobertura, etc)
    st.divider()

    dist_notas = get_rating_distribution()
    por_contexto = get_ratings_by_context()
    por_regiao = get_ratings_by_region()
    cobertura = get_catalog_coverage(top_n=5)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuição de notas")
        st.bar_chart(dist_notas.set_index("nota"))
    with c2:
        st.subheader("Avaliações por região")
        st.bar_chart(por_regiao.set_index("regiao"))

    st.subheader("Avaliações por contexto")
    st.dataframe(por_contexto, use_container_width=True)

    st.subheader("Cobertura do catálogo")
    st.dataframe(cobertura, use_container_width=True)


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
        index_atual = opcoes_telas.index(st.session_state["pagina_atual"])
    except ValueError:
        index_atual = 0
        
    page = st.sidebar.radio("Telas", opcoes_telas, index=index_atual)
    
    # Se o usuário clicar manualmente na sidebar, obedece
    if page != st.session_state["pagina_atual"]:
        st.session_state["pagina_atual"] = page
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
    ensure_database_ready()
    init_state()

    if st.session_state["is_authenticated"]:
        render_authenticated_app()
    else:
        render_login_screen()


if __name__ == "__main__":
    main()
