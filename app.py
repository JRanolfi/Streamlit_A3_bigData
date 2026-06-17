import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pysus import sim
from datetime import datetime

# Configuração da página
st.set_page_config(
    page_title="Análise COVID-19 - Bahia",
    page_icon="📊",
    layout="wide"
)

# Título principal
st.title("📊 Como maiores investimentos em Vigilância Epidemiológica contribuíram para reduzir a mortalidade por COVID-19 na Bahia durante a pandemia.")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("🎛️ Configurações")
    st.markdown("Dados de 2020 a 2023")
    st.markdown("---")
    st.subheader("Fontes:")
    st.write("- SIM (Sistema de Informações sobre Mortalidade)")
    st.write("- WCOTA (dados de vacinação)")
    st.write("- Despesas Governo da Bahia")
    
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()

# Cache para carregar dados
@st.cache_data
def load_obitos_data():
    """Carrega dados de óbitos"""
    with st.spinner("Carregando dados de óbitos..."):
        dataframes = []
        for year in [2020, 2021, 2022, 2023]:
            df_year = sim(state="BA", year=year)
            dataframes.append(df_year)
        obitos_bruto = pd.concat(dataframes, ignore_index=True)
        
        covid = obitos_bruto[obitos_bruto["CAUSABAS"] == "B342"].copy()
        covid = covid[["DTOBITO", "IDADE", "SEXO"]]
        covid["DTOBITO"] = pd.to_datetime(covid["DTOBITO"], format="%d%m%Y", errors="coerce")
        covid["IDADE"] = pd.to_numeric(covid["IDADE"], errors="coerce")
        
        unidade = covid["IDADE"] // 100
        valor = covid["IDADE"] % 100
        
        covid["IDADE_ANOS"] = 0.0
        covid.loc[unidade == 3, "IDADE_ANOS"] = valor / 12
        covid.loc[unidade == 4, "IDADE_ANOS"] = valor
        covid.loc[unidade == 5, "IDADE_ANOS"] = 100 + valor
        
        covid = covid.dropna()
        covid["ANO"] = covid["DTOBITO"].dt.year
        covid["MES"] = covid["DTOBITO"].dt.month
        
        return covid

@st.cache_data
def load_vacinas_data():
    """Carrega dados de vacinação"""
    with st.spinner("Carregando dados de vacinação..."):
        url_vacina = "https://raw.githubusercontent.com/wcota/covid19br/master/cases-brazil-states.csv"
        vacinas_bruto = pd.read_csv(url_vacina)
        vacinas_ba = vacinas_bruto[vacinas_bruto["state"] == "BA"].copy()
        vacinas_ba["date"] = pd.to_datetime(vacinas_ba["date"])
        vacinas_ba["ANO"] = vacinas_ba["date"].dt.year
        doses_por_ano = vacinas_ba.groupby("ANO")["vaccinated"].max().reset_index()
        doses_por_ano.columns = ["ANO", "DOSES"]
        return vacinas_ba, doses_por_ano

@st.cache_data
def load_despesas_data():
    """Carrega dados de despesas"""
    with st.spinner("Carregando dados de despesas..."):
        url = "https://raw.githubusercontent.com/erickassis/despesas_bahia_2019_2023/refs/heads/main/despesas.csv"
        despesas = pd.read_csv(url)
        despesas = despesas[(despesas["Ano"] >= 2020) & (despesas['Ano'] <= 2023)].copy()
        
        despesas["Valor Pago"] = (
            despesas["Valor Pago"]
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        despesas["Valor Pago"] = pd.to_numeric(despesas["Valor Pago"], errors="coerce")
        
        gasto_por_ano = despesas.groupby("Ano")["Valor Pago"].sum().reset_index()
        gasto_por_ano["Valor Pago"] = gasto_por_ano["Valor Pago"] / 1_000_000
        gasto_por_ano.columns = ["ANO", "GASTO_MILHOES"]

        return despesas, gasto_por_ano

# Carregar todos os dados
try:
    covid = load_obitos_data()
    vacinas_ba, doses = load_vacinas_data()
    despesas, gastos = load_despesas_data()
    
    # Criar tabela consolidada
    obitos_por_ano = covid.groupby("ANO").size().reset_index(name="OBITOS")
    tabela = obitos_por_ano.merge(gastos, on="ANO")
    tabela = tabela.merge(doses, on="ANO", how="left")
    tabela["DOSES"] = tabela["DOSES"].fillna(0)
    
    # Tabs
    tab1, tab2 = st.tabs([
        "📈 Visão Geral",
        "👥 Perfil das Vítimas"
    ])
    
    # TAB 1 - VISÃO GERAL
    with tab1:
        st.header("Indicadores Chave")
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Óbitos", f"{tabela['OBITOS'].sum():,}")
        with col2:
            st.metric("Total Investido", f"R$ {tabela['GASTO_MILHOES'].sum():.1f}M")
        with col3:
            st.metric("Total de Doses", f"{(tabela['DOSES'].sum() / 1_000_000):.1f}M")
        with col4:
            st.metric("Idade Média", f"{covid['IDADE_ANOS'].mean():.1f} anos")
        
        # Gráfico principal
        month_mapping = {
            'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
            'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
            'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
        }

        despesas["Mes_numeric"] = despesas["Nome do Mês"].str.lower().map(month_mapping)

        despesas["Mes"] = pd.to_datetime(
            despesas["Ano"].astype(str) + "-" + despesas["Mes_numeric"].astype(str).str.zfill(2) + "-01"
        )

        gasto_mensal = despesas.groupby("Mes")["Valor Pago"].sum().reset_index()
        gasto_mensal.columns = ["DATA_MES", "GASTO_MILHOES"]
        gasto_mensal["GASTO_MILHOES"] = gasto_mensal["GASTO_MILHOES"] / 1_000_000
        gasto_mensal = gasto_mensal.sort_values("DATA_MES")

        # ── Preparo dos dados mensais de óbitos ─────────────────────────────────────
        obitos_mes = covid.groupby(["ANO", "MES"]).size().reset_index(name="OBITOS")
        obitos_mes["DATA"] = pd.to_datetime(
            obitos_mes["ANO"].astype(str) + "-" + obitos_mes["MES"].astype(str).str.zfill(2) + "-01"
        )
        obitos_mes = obitos_mes.sort_values("DATA")

        # ── Preparo dos dados mensais de vacinas ────────────────────────────────────
        vacinas_ba["DATA_MES"] = vacinas_ba["date"].dt.to_period("M").dt.to_timestamp()
        doses_mes = (
            vacinas_ba.groupby("DATA_MES")["vaccinated"]
            .max()
            .reset_index()
            .sort_values("DATA_MES")
        )
        doses_mes["DOSES_NOVAS"] = doses_mes["vaccinated"].diff().clip(lower=0)
        doses_mes["DOSES_NOVAS_MILHOES"] = doses_mes["DOSES_NOVAS"] / 1_000_000  # <-- Doses em milhões
        doses_mes = doses_mes[doses_mes["DATA_MES"].dt.year >= 2020]
        
        # Criar gráfico
        # Criar gráfico
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Barras - Óbitos
        fig.add_trace(
            go.Bar(
                x=obitos_mes["DATA"],
                y=obitos_mes["OBITOS"],
                name="Óbitos",
                marker_color="#E63946",
                opacity=0.6
            ),
            secondary_y=False
        )

        # Linha - Doses (agora em valores absolutos)
        fig.add_trace(
            go.Scatter(
                x=doses_mes["DATA_MES"],
                y=doses_mes["DOSES_NOVAS"],
                name="Doses (mi)",
                line=dict(color="#2A9D8F", width=2),
                mode="lines+markers"
            ),
            secondary_y=True
        )

        # Linha - Gastos
        fig.add_trace(
            go.Scatter(
                x=gasto_mensal["DATA_MES"],
                y=gasto_mensal["GASTO_MILHOES"],
                name="Gasto (R$ milhões)",
                line=dict(color="#F4A261", width=2, dash="dash"),
                mode="lines+markers"
            ),
            secondary_y=True
        )

        # Layout
        fig.update_layout(
            title="Óbitos, Vacinação e Investimento - Bahia",
            hovermode="x unified",
            height=500,
            template="plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ),
            xaxis_title="Data",
            yaxis_title="Óbitos",
            yaxis2_title="Doses"
        )

        # Cores dos eixos
        fig.update_yaxes(title_font_color="#E63946", tickfont_color="#E63946", secondary_y=False)
        fig.update_yaxes(title_font_color="#2A9D8F", tickfont_color="#2A9D8F", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)
        
        # Análise adicional
        with st.expander("📊 Análise dos Dados"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Pico de Óbitos",
                    f"{obitos_mes['OBITOS'].max():,}",
                    f"Mês: {obitos_mes.loc[obitos_mes['OBITOS'].idxmax(), 'DATA'].strftime('%b/%Y')}"
                )
            with col2:
                st.metric(
                    "Pico de Vacinação",
                    f"{doses_mes['DOSES_NOVAS'].max() / 1_000_000:.2f}M",
                    f"Mês: {doses_mes.loc[doses_mes['DOSES_NOVAS'].idxmax(), 'DATA_MES'].strftime('%b/%Y')}"
                )
            with col3:
                st.metric(
                    "Pico de Investimento",
                    f"R$ {gasto_mensal['GASTO_MILHOES'].max():.1f}M",
                    f"Mês: {gasto_mensal.loc[gasto_mensal['GASTO_MILHOES'].idxmax(), 'DATA_MES'].strftime('%b/%Y')}"
                )

    
    # TAB 3 - PERFIL DAS VÍTIMAS
    with tab2:
        st.header("Perfil das Vítimas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Histograma de idade
            fig = px.histogram(covid, x="IDADE_ANOS", nbins=20,
                              title="Distribuição de Idade",
                              labels={"IDADE_ANOS": "Idade (anos)", "count": "Frequência"})
            fig.update_traces(marker_color="#457B9D")
            
            media = covid['IDADE_ANOS'].mean()
            mediana = covid['IDADE_ANOS'].median()
            
            fig.add_vline(x=mediana, line_dash="dash", line_color="red",
                         annotation_text=f"Mediana: {mediana:.0f}")
            fig.add_vline(x=media, line_dash="dash", line_color="orange",
                         annotation_text=f"Média: {media:.0f}")
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Idade média por ano
            media_idade = covid.groupby("ANO")["IDADE_ANOS"].mean().reset_index()
            fig = px.line(media_idade, x="ANO", y="IDADE_ANOS",
                         title="Idade Média por Ano",
                         markers=True,
                         labels={"IDADE_ANOS": "Idade média (anos)", "ANO": "Ano"})
            fig.update_traces(line_color="#E76F51", marker_color="#E76F51")
            st.plotly_chart(fig, use_container_width=True)

        
    # Rodapé
    st.markdown("---")
    st.markdown(f"*Dados atualizados em: {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
    st.markdown("*💡 Dica: Passe o mouse nos gráficos para ver detalhes e use zoom!*")

except Exception as e:
    st.error(f"Erro ao carregar dados: {str(e)}")
    st.info("Verifique sua conexão com a internet e recarregue a página.")