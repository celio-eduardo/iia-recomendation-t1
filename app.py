import streamlit as st

from ui_data import (
    authenticate_user,
    create_user,
    ensure_database_ready,
    get_catalog_coverage,
    get_ratings_by_context,
    get_ratings_by_region,
    get_rating_distribution,
    get_recommendations,
    submit_rating,
)

PERFIS = [
    "business",
    "casal_luxo",
    "lazer_familia",
    "pet_owner",
    "com_filhos",
    "com_idosos",
]

REGIOES = ["Sao Paulo", "Frio/Serra", "Interior", "Litoral/Parques"]


def init_state() -> None:
    defaults = {
        "is_authenticated": False,
        "user_id": None,
        "login": None,
        "perfil_base": None,
        "contexto_viagem": None,
        "recs_df": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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
        # Selectboxes para os filtros absolutos e tipo principal
        regiao = st.selectbox("Região desejada", REGIOES)
        tipo_viagem = st.selectbox("Tipo de viagem", ["familiar", "negocios", "com amigos", "lua_de_mel"])
        
        st.write("Atendimentos específicos necessários:")
        # Checkboxes que virarão 1.0 ou 0.0 no Hot Encode
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
            
            # Aqui chamamos a Controladora Final (instanciada previamente)
            # Ex: st.session_state['controller'].iniciar_sessao(user_id, contexto)
            # st.session_state["recs_df"] = st.session_state['controller'].carregar_recomendacoes()
            
            st.success("Recomendações moduladas para o seu contexto atual!")


def render_recommendations_screen() -> None:
    st.header("Recomendacoes")
    recs_df = st.session_state.get("recs_df")
    if recs_df is None:
        st.info("Responda as perguntas para gerar recomendações.")
        return
    if recs_df.empty:
        st.warning("Não há recomendações disponíveis para o contexto atual.")
        return

    st.dataframe(recs_df, use_container_width=True)


def render_rating_screen() -> None:
    st.header("Avaliação das recomendações")
    recs_df = st.session_state.get("recs_df")
    
    if recs_df is None or len(recs_df) == 0: # Ajuste para tratar lista vazia
        st.info("Gere recomendações antes de avaliar.")
        return

    with st.form("rating_form"):
        # Extrai os IDs para o selectbox
        opcoes_hoteis = [h['id_hotel'] for h in recs_df] if isinstance(recs_df, list) else recs_df["id_hotel"].tolist()
        hotel_id = st.selectbox("Hotel escolhido para avaliar", opcoes_hoteis)
        nota = st.slider("Sua nota real (1 a 5)", 1, 5, 4)
        
        submit = st.form_submit_button("Confirmar Avaliação")
        if submit:
            # Aqui acionamos o finalizador da controladora que já calcula as métricas
            metricas = st.session_state['controller'].finalizar_com_avaliacao(hotel_id, nota)
            
            st.success("Avaliação salva!")
            st.write("### Acurácia do Algoritmo nesta sessão:")
            st.json(metricas) # Exibe NDCG e RMSE calculados


def render_metrics_screen() -> None:
    st.header("Métricas do algoritmo")

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
    st.sidebar.write(f"Usuario: {st.session_state['login']}")
    st.sidebar.write(f"Perfil base: {st.session_state['perfil_base']}")

    if st.sidebar.button("Sair"):
        for key in [
            "is_authenticated",
            "user_id",
            "login",
            "perfil_base",
            "contexto_viagem",
            "recs_df",
        ]:
            st.session_state[key] = None if key != "is_authenticated" else False
        st.rerun()

    page = st.sidebar.radio(
        "Telas",
        [
            "Perguntas de viagem",
            "Recomendaçoes",
            "Avaliaçao",
            "Metricas",
        ],
    )

    if page == "Perguntas de viagem":
        render_questions_screen()
    elif page == "Recomendacoes":
        render_recommendations_screen()
    elif page == "Avaliacao":
        render_rating_screen()
    elif page == "Metricas":
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
