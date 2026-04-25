# MVP Streamlit - Sistema de Recomendacao

Aplicacao Streamlit com fluxo completo para:

- login/cadastro
- perguntas simples sobre viagem
- recomendacoes de hoteis
- avaliacao de recomendacoes
- metricas de cobertura e distribuicao

## Requisitos

- Python 3.10+
- Dependencias do `requirements.txt`

## Instalacao

Se seu ambiente tiver `pip`:

```bash
python3 -m pip install -r requirements.txt
```

Se o `pip` nao estiver instalado no sistema:

```bash
sudo apt update
sudo apt install -y python3-pip
python3 -m pip install -r requirements.txt
```

## Executar

```bash
streamlit run app.py
```

O app inicializa o banco automaticamente e popula os dados de exemplo quando necessario.