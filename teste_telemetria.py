import sqlite3
import pandas as pd
from banco_sql import init_db
from recomendacao_controller import RecomendacaoController

def executar_testes_arquitetura():
    # 1. Preparação (Setup)
    conn = init_db("banco_teste.db")
    df_hoteis_mock = pd.DataFrame({
        "luxo": [0.8, 0.2], "lazer": [0.5, 0.9], "urbano": [0.9, 0.1],
        "pet_friendly": [1, 0], "kids_friendly": [0, 1], "acessibilidade": [1, 1],
        "seguranca": [0.9, 0.8], "preco": [0.9, 0.3], "silencio": [0.8, 0.5],
        "capacidade": [0.2, 0.8], "regiao": ["Sao Paulo", "Litoral/Parques"]
    }, index=["H1", "H2"])
    
    # Simula um utilizador na base de dados
    try:
        conn.execute("INSERT INTO usuarios (id_usuario, login, senha, perfil_base) VALUES ('U1', 'teste', '123', 'business')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    controller = RecomendacaoController(conn, df_hoteis_mock)
    contexto = {"tipo_viagem": "negocios", "regiao": "Sao Paulo", "pet_friendly": False, "kids_friendly": False, "idosos": False}

    # 2. Teste de Borda: Abandono com 0 hotéis exibidos
    controller.iniciar_sessao('U1', contexto)
    controller.registrar_abandono()

    # 3. Teste Padrão: Abandono após carregar recomendações
    controller.iniciar_sessao('U1', contexto)
    controller.carregar_recomendacoes()
    controller.registrar_abandono()

    # 4. Teste Padrão: Conversão com sucesso
    controller.iniciar_sessao('U1', contexto)
    controller.carregar_recomendacoes()
    controller.finalizar_com_avaliacao("H1", 4)

    # 5. Avaliação dos Resultados (Asserts)
    df_logs = pd.read_sql_query("SELECT * FROM log_sessoes", conn)
    print("\n--- Registos de Telemetria ---")
    print(df_logs[['id_usuario', 'algoritmo_usado', 'qtd_exibida', 'converteu_em_escolha']])

    assert len(df_logs) == 3, "Deveriam existir 3 registos de sessão."
    assert df_logs.iloc[0]['qtd_exibida'] == 0, "O primeiro abandono deveria ter 0 exibições."
    assert df_logs.iloc[1]['converteu_em_escolha'] == 0, "O segundo registo deve ser um abandono (0)."
    assert df_logs.iloc[2]['converteu_em_escolha'] == 1, "O terceiro registo deve ser um sucesso (1)."
    
    print("\n✅ Todos os testes de arquitetura da telemetria passaram com sucesso.")
    conn.close()

if __name__ == "__main__":
    executar_testes_arquitetura()