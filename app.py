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
    st.write("Defina o contexto para personalizar suas recomendações.")

    with st.form("questions_form"):
        regiao = st.selectbox("Região desejada", REGIOES)
        peso_custo = st.slider("Importância de custo-benefício", 0.0, 2.0, 1.0, 0.1)
        peso_conforto = st.slider("Importância de conforto", 0.0, 2.0, 1.0, 0.1)
        peso_experiencia = st.slider("Importância de experiência/lazer", 0.0, 2.0, 1.0, 0.1)
        submit = st.form_submit_button("Ver recomendações")
        if submit:
            contexto = {
                "regiao": regiao,
                "peso_custo": peso_custo,
                "peso_conforto": peso_conforto,
                "peso_experiencia": peso_experiencia,
            }
            st.session_state["contexto_viagem"] = contexto
            st.session_state["recs_df"] = get_recommendations(
                context=contexto,
                user_id=st.session_state["user_id"],
                top_n=10,
            )
            st.success("Recomendacoes atualizadas.")


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
    if recs_df is None or recs_df.empty:
        st.info("Gere recomendações antes de avaliar.")
        return

    with st.form("rating_form"):
        hotel_id = st.selectbox("Hotel para avaliar", recs_df["id_hotel"].tolist())
        nota = st.slider("Nota", 1, 5, 4)
        submit = st.form_submit_button("Enviar avaliação")
        if submit:
            contexto = st.session_state.get("contexto_viagem", {})
            contexto_texto = (
                f"regiao={contexto.get('regiao', 'N/A')}"
                f"|custo={contexto.get('peso_custo', 1.0)}"
                f"|conforto={contexto.get('peso_conforto', 1.0)}"
                f"|experiencia={contexto.get('peso_experiencia', 1.0)}"
            )
            submit_rating(
                user_id=st.session_state["user_id"],
                hotel_id=hotel_id,
                nota=nota,
                contexto_viagem=contexto_texto,
            )
            st.success("Avaliacao salva com sucesso.")


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
