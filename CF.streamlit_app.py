import io
import re
import unicodedata
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Controle Financeiro Pessoal",
    layout="wide",
)

EIXOS_PADRAO = [
    "Alimentação",
    "Delivery",
    "Transporte",
    "Moradia",
    "Assinaturas",
    "Lazer",
    "Saúde",
    "Compras",
    "Viagens",
    "Outros",
]

PALAVRAS_DATA = [
    "data",
    "date",
    "data da compra",
    "data compra",
    "data transacao",
    "data transação",
]

PALAVRAS_DESCRICAO = [
    "descricao",
    "descrição",
    "description",
    "estabelecimento",
    "merchant",
    "titulo",
    "título",
    "historico",
    "histórico",
    "nome",
]

PALAVRAS_VALOR = [
    "valor",
    "amount",
    "value",
    "valor da compra",
    "valor compra",
    "total",
]

REGRAS_AUTOMATICAS = {
    "Transporte": [
        "uber",
        "99app",
        "99 app",
        "cabify",
        "posto",
        "combustivel",
        "combustível",
        "estacionamento",
        "pedagio",
        "pedágio",
    ],
    "Delivery": [
        "ifood",
        "rappi",
        "ubereats",
        "uber eats",
        "delivery",
    ],
    "Alimentação": [
        "restaurante",
        "mercado",
        "supermercado",
        "padaria",
        "carrefour",
        "assai",
        "atacadao",
        "atacadão",
        "pao de acucar",
        "pão de açúcar",
    ],
    "Assinaturas": [
        "netflix",
        "spotify",
        "amazon prime",
        "youtube",
        "google one",
        "icloud",
        "microsoft",
        "chatgpt",
        "openai",
    ],
    "Moradia": [
        "aluguel",
        "condominio",
        "condomínio",
        "energia",
        "sabesp",
        "copel",
        "internet",
        "claro",
        "vivo fibra",
    ],
    "Saúde": [
        "farmacia",
        "farmácia",
        "drogaria",
        "hospital",
        "clinica",
        "clínica",
        "laboratorio",
        "laboratório",
    ],
}


# ============================================================
# FUNÇÕES
# ============================================================

def normalizar_texto(texto):
    texto = str(texto).strip().lower()

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    texto = re.sub(r"\s+", " ", texto)

    return texto


def identificar_coluna(colunas, possibilidades):
    colunas_normalizadas = {
        coluna: normalizar_texto(coluna)
        for coluna in colunas
    }

    possibilidades_normalizadas = [
        normalizar_texto(item)
        for item in possibilidades
    ]

    for coluna, coluna_normalizada in colunas_normalizadas.items():
        if coluna_normalizada in possibilidades_normalizadas:
            return coluna

    for coluna, coluna_normalizada in colunas_normalizadas.items():
        for possibilidade in possibilidades_normalizadas:
            if possibilidade in coluna_normalizada:
                return coluna

    return None


def converter_valor(valor):
    if pd.isna(valor):
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    texto = texto.replace("R$", "")
    texto = texto.replace(" ", "")

    negativo = texto.startswith("-")

    texto = texto.replace("-", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9.]", "", texto)

    if not texto:
        return None

    try:
        numero = float(texto)
        return -numero if negativo else numero
    except ValueError:
        return None


def formatar_real(valor):
    valor_formatado = f"{valor:,.2f}"
    valor_formatado = valor_formatado.replace(",", "X")
    valor_formatado = valor_formatado.replace(".", ",")
    valor_formatado = valor_formatado.replace("X", ".")

    return f"R$ {valor_formatado}"


def ler_arquivo(arquivo):
    extensao = arquivo.name.lower().split(".")[-1]

    if extensao == "csv":
        conteudo = arquivo.getvalue()

        tentativas = [
            {"sep": None, "engine": "python", "encoding": "utf-8"},
            {"sep": ";", "encoding": "utf-8"},
            {"sep": ",", "encoding": "utf-8"},
            {"sep": ";", "encoding": "latin-1"},
            {"sep": ",", "encoding": "latin-1"},
        ]

        for configuracao in tentativas:
            try:
                return pd.read_csv(
                    io.BytesIO(conteudo),
                    **configuracao,
                )
            except Exception:
                continue

        raise ValueError("Não foi possível interpretar o arquivo CSV.")

    if extensao in ["xlsx", "xls"]:
        return pd.read_excel(arquivo)

    raise ValueError("Formato não suportado.")


def classificar_eixo(descricao):
    descricao_normalizada = normalizar_texto(descricao)

    for eixo, palavras in REGRAS_AUTOMATICAS.items():
        for palavra in palavras:
            if normalizar_texto(palavra) in descricao_normalizada:
                return eixo

    return "Outros"


def padronizar_arquivo(df, nome_arquivo, gastos_positivos):
    coluna_data = identificar_coluna(df.columns, PALAVRAS_DATA)
    coluna_descricao = identificar_coluna(
        df.columns,
        PALAVRAS_DESCRICAO,
    )
    coluna_valor = identificar_coluna(df.columns, PALAVRAS_VALOR)

    colunas_ausentes = []

    if coluna_data is None:
        colunas_ausentes.append("data")

    if coluna_descricao is None:
        colunas_ausentes.append("descrição")

    if coluna_valor is None:
        colunas_ausentes.append("valor")

    if colunas_ausentes:
        raise ValueError(
            "Não foi possível identificar: "
            + ", ".join(colunas_ausentes)
            + f". Colunas encontradas: {list(df.columns)}"
        )

    resultado = pd.DataFrame()

    resultado["Data"] = pd.to_datetime(
        df[coluna_data],
        errors="coerce",
        dayfirst=True,
    )

    resultado["Descrição"] = (
        df[coluna_descricao]
        .fillna("Sem descrição")
        .astype(str)
    )

    resultado["Valor original"] = df[coluna_valor].apply(
        converter_valor
    )

    resultado = resultado.dropna(
        subset=["Data", "Valor original"]
    )

    if gastos_positivos:
        resultado["Valor gasto"] = resultado[
            "Valor original"
        ].abs()
    else:
        resultado = resultado[
            resultado["Valor original"] < 0
        ].copy()

        resultado["Valor gasto"] = resultado[
            "Valor original"
        ].abs()

    resultado["Eixo"] = resultado["Descrição"].apply(
        classificar_eixo
    )

    resultado["Arquivo"] = nome_arquivo
    resultado["Ano"] = resultado["Data"].dt.year
    resultado["Mês"] = resultado["Data"].dt.month

    return resultado[
        [
            "Data",
            "Descrição",
            "Valor gasto",
            "Eixo",
            "Arquivo",
            "Ano",
            "Mês",
        ]
    ]


def gerar_excel(gastos, recebimentos):
    memoria = io.BytesIO()

    with pd.ExcelWriter(memoria, engine="openpyxl") as writer:
        gastos.to_excel(
            writer,
            sheet_name="Gastos",
            index=False,
        )

        recebimentos.to_excel(
            writer,
            sheet_name="Recebimentos",
            index=False,
        )

    memoria.seek(0)

    return memoria.getvalue()


# ============================================================
# ESTADO DO APP
# ============================================================

if "gastos" not in st.session_state:
    st.session_state.gastos = pd.DataFrame(
        columns=[
            "Data",
            "Descrição",
            "Valor gasto",
            "Eixo",
            "Arquivo",
            "Ano",
            "Mês",
        ]
    )

if "recebimentos" not in st.session_state:
    st.session_state.recebimentos = pd.DataFrame(
        columns=[
            "Data",
            "Descrição",
            "Valor recebido",
            "Ano",
            "Mês",
        ]
    )


# ============================================================
# CABEÇALHO
# ============================================================

st.title("💰 Controle Financeiro Pessoal")

st.caption(
    "Importe seus arquivos, classifique os gastos por eixo "
    "e acompanhe os resultados mensais e anuais."
)


# ============================================================
# ABAS
# ============================================================

aba_importacao, aba_tagging, aba_recebimentos, aba_dashboard = st.tabs(
    [
        "1. Importar gastos",
        "2. Classificar gastos",
        "3. Registrar recebimentos",
        "4. Dashboard",
    ]
)


# ============================================================
# ABA 1 — IMPORTAÇÃO
# ============================================================

with aba_importacao:
    st.subheader("Importar extratos")

    st.info(
        "O arquivo precisa ter alguma coluna de data, "
        "descrição e valor."
    )

    arquivos = st.file_uploader(
        "Selecione arquivos CSV ou XLSX",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
    )

    gastos_positivos = st.radio(
        "Como os gastos aparecem no arquivo?",
        options=[
            "Como valores positivos",
            "Como valores negativos",
        ],
        horizontal=True,
    ) == "Como valores positivos"

    coluna_importar, coluna_limpar = st.columns(2)

    with coluna_importar:
        importar = st.button(
            "Importar arquivos",
            type="primary",
            use_container_width=True,
        )

    with coluna_limpar:
        limpar_gastos = st.button(
            "Limpar gastos importados",
            use_container_width=True,
        )

    if limpar_gastos:
        st.session_state.gastos = st.session_state.gastos.iloc[0:0]
        st.success("Gastos removidos.")

    if importar:
        if not arquivos:
            st.warning("Selecione pelo menos um arquivo.")
        else:
            arquivos_processados = []
            erros = []

            for arquivo in arquivos:
                try:
                    df_original = ler_arquivo(arquivo)

                    df_padronizado = padronizar_arquivo(
                        df=df_original,
                        nome_arquivo=arquivo.name,
                        gastos_positivos=gastos_positivos,
                    )

                    arquivos_processados.append(df_padronizado)

                except Exception as erro:
                    erros.append(
                        f"{arquivo.name}: {str(erro)}"
                    )

            if arquivos_processados:
                novos_gastos = pd.concat(
                    arquivos_processados,
                    ignore_index=True,
                )

                st.session_state.gastos = pd.concat(
                    [
                        st.session_state.gastos,
                        novos_gastos,
                    ],
                    ignore_index=True,
                )

                st.session_state.gastos = (
                    st.session_state.gastos
                    .drop_duplicates(
                        subset=[
                            "Data",
                            "Descrição",
                            "Valor gasto",
                        ],
                        keep="last",
                    )
                    .sort_values("Data")
                    .reset_index(drop=True)
                )

                st.success(
                    f"{len(novos_gastos)} transações importadas."
                )

            if erros:
                for erro in erros:
                    st.error(erro)

    if not st.session_state.gastos.empty:
        st.write(
            f"Total de transações carregadas: "
            f"**{len(st.session_state.gastos)}**"
        )

        st.dataframe(
            st.session_state.gastos.tail(20),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# ABA 2 — TAGGING
# ============================================================

with aba_tagging:
    st.subheader("Classificar gastos por eixo")

    if st.session_state.gastos.empty:
        st.warning("Importe primeiro um arquivo de gastos.")

    else:
        st.write(
            "Edite a coluna **Eixo**. Você pode utilizar "
            "os eixos sugeridos ou digitar um novo."
        )

        st.caption(
            "Eixos sugeridos: "
            + ", ".join(EIXOS_PADRAO)
        )

        base_edicao = st.session_state.gastos.copy()

        base_edicao["Data"] = pd.to_datetime(
            base_edicao["Data"]
        )

        base_editada = st.data_editor(
            base_edicao,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY",
                    disabled=True,
                ),
                "Descrição": st.column_config.TextColumn(
                    "Descrição",
                    disabled=False,
                ),
                "Valor gasto": st.column_config.NumberColumn(
                    "Valor gasto",
                    format="R$ %.2f",
                    disabled=True,
                ),
                "Eixo": st.column_config.TextColumn(
                    "Eixo",
                    help="Digite o eixo do gasto.",
                ),
                "Arquivo": st.column_config.TextColumn(
                    "Arquivo",
                    disabled=True,
                ),
                "Ano": None,
                "Mês": None,
            },
            key="editor_gastos",
        )

        if st.button(
            "Salvar classificações",
            type="primary",
        ):
            base_editada["Data"] = pd.to_datetime(
                base_editada["Data"]
            )

            base_editada["Ano"] = base_editada["Data"].dt.year
            base_editada["Mês"] = base_editada["Data"].dt.month

            st.session_state.gastos = base_editada.copy()

            st.success("Classificações salvas.")


# ============================================================
# ABA 3 — RECEBIMENTOS
# ============================================================

with aba_recebimentos:
    st.subheader("Registrar valores recebidos")

    with st.form("formulario_recebimento"):
        coluna_data, coluna_descricao, coluna_valor = st.columns(
            [1, 2, 1]
        )

        with coluna_data:
            data_recebimento = st.date_input(
                "Data",
                value=date.today(),
            )

        with coluna_descricao:
            descricao_recebimento = st.text_input(
                "Descrição",
                placeholder="Ex.: salário, freelance ou reembolso",
            )

        with coluna_valor:
            valor_recebido = st.number_input(
                "Valor recebido",
                min_value=0.0,
                step=100.0,
                format="%.2f",
            )

        salvar_recebimento = st.form_submit_button(
            "Adicionar recebimento",
            type="primary",
            use_container_width=True,
        )

    if salvar_recebimento:
        if valor_recebido <= 0:
            st.warning("Digite um valor maior que zero.")
        else:
            data_convertida = pd.to_datetime(data_recebimento)

            novo_recebimento = pd.DataFrame(
                [
                    {
                        "Data": data_convertida,
                        "Descrição": (
                            descricao_recebimento
                            or "Recebimento"
                        ),
                        "Valor recebido": valor_recebido,
                        "Ano": data_convertida.year,
                        "Mês": data_convertida.month,
                    }
                ]
            )

            st.session_state.recebimentos = pd.concat(
                [
                    st.session_state.recebimentos,
                    novo_recebimento,
                ],
                ignore_index=True,
            )

            st.success("Recebimento adicionado.")

    if not st.session_state.recebimentos.empty:
        recebimentos_editados = st.data_editor(
            st.session_state.recebimentos,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Data": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY",
                ),
                "Valor recebido": st.column_config.NumberColumn(
                    "Valor recebido",
                    format="R$ %.2f",
                ),
                "Ano": None,
                "Mês": None,
            },
            key="editor_recebimentos",
        )

        coluna_salvar, coluna_limpar_recebimentos = st.columns(2)

        with coluna_salvar:
            if st.button(
                "Salvar recebimentos",
                use_container_width=True,
            ):
                recebimentos_editados["Data"] = pd.to_datetime(
                    recebimentos_editados["Data"]
                )

                recebimentos_editados["Ano"] = (
                    recebimentos_editados["Data"].dt.year
                )

                recebimentos_editados["Mês"] = (
                    recebimentos_editados["Data"].dt.month
                )

                st.session_state.recebimentos = (
                    recebimentos_editados.copy()
                )

                st.success("Recebimentos salvos.")

        with coluna_limpar_recebimentos:
            if st.button(
                "Limpar recebimentos",
                use_container_width=True,
            ):
                st.session_state.recebimentos = (
                    st.session_state.recebimentos.iloc[0:0]
                )

                st.success("Recebimentos removidos.")


# ============================================================
# ABA 4 — DASHBOARD
# ============================================================

with aba_dashboard:
    st.subheader("Dashboard financeiro")

    gastos = st.session_state.gastos.copy()
    recebimentos = st.session_state.recebimentos.copy()

    if gastos.empty and recebimentos.empty:
        st.warning(
            "Importe gastos ou registre recebimentos "
            "para visualizar o dashboard."
        )

    else:
        anos_disponiveis = set()

        if not gastos.empty:
            anos_disponiveis.update(
                gastos["Ano"].dropna().astype(int).tolist()
            )

        if not recebimentos.empty:
            anos_disponiveis.update(
                recebimentos["Ano"].dropna().astype(int).tolist()
            )

        anos_disponiveis = sorted(
            anos_disponiveis,
            reverse=True,
        )

        coluna_periodo, coluna_ano, coluna_mes = st.columns(3)

        with coluna_periodo:
            tipo_visao = st.radio(
                "Visão",
                options=[
                    "Mês",
                    "Ano acumulado",
                ],
                horizontal=True,
            )

        with coluna_ano:
            ano_selecionado = st.selectbox(
                "Ano",
                options=anos_disponiveis,
            )

        meses = {
            1: "Janeiro",
            2: "Fevereiro",
            3: "Março",
            4: "Abril",
            5: "Maio",
            6: "Junho",
            7: "Julho",
            8: "Agosto",
            9: "Setembro",
            10: "Outubro",
            11: "Novembro",
            12: "Dezembro",
        }

        with coluna_mes:
            mes_selecionado = st.selectbox(
                "Mês de referência",
                options=list(meses.keys()),
                format_func=lambda numero: meses[numero],
                disabled=tipo_visao == "Ano acumulado",
            )

        if tipo_visao == "Mês":
            gastos_filtrados = gastos[
                (gastos["Ano"] == ano_selecionado)
                & (gastos["Mês"] == mes_selecionado)
            ].copy()

            recebimentos_filtrados = recebimentos[
                (recebimentos["Ano"] == ano_selecionado)
                & (recebimentos["Mês"] == mes_selecionado)
            ].copy()

            titulo_periodo = (
                f"{meses[mes_selecionado]} de "
                f"{ano_selecionado}"
            )

        else:
            gastos_filtrados = gastos[
                gastos["Ano"] == ano_selecionado
            ].copy()

            recebimentos_filtrados = recebimentos[
                recebimentos["Ano"] == ano_selecionado
            ].copy()

            titulo_periodo = f"Ano de {ano_selecionado}"

        total_gasto = gastos_filtrados["Valor gasto"].sum()
        total_recebido = recebimentos_filtrados[
            "Valor recebido"
        ].sum()

        saldo = total_recebido - total_gasto

        st.markdown(f"### {titulo_periodo}")

        metrica_gasto, metrica_recebido, metrica_saldo = st.columns(
            3
        )

        metrica_gasto.metric(
            "Valor total gasto",
            formatar_real(total_gasto),
        )

        metrica_recebido.metric(
            "Valor total recebido",
            formatar_real(total_recebido),
        )

        metrica_saldo.metric(
            "Saldo",
            formatar_real(saldo),
        )

        st.divider()

        if not gastos_filtrados.empty:
            gastos_por_eixo = (
                gastos_filtrados
                .groupby("Eixo", as_index=False)["Valor gasto"]
                .sum()
                .sort_values(
                    "Valor gasto",
                    ascending=False,
                )
            )

            if total_gasto > 0:
                gastos_por_eixo["Percentual"] = (
                    gastos_por_eixo["Valor gasto"]
                    / total_gasto
                )
            else:
                gastos_por_eixo["Percentual"] = 0

            gastos_por_eixo["Valor formatado"] = (
                gastos_por_eixo["Valor gasto"]
                .apply(formatar_real)
            )

            gastos_por_eixo["Percentual formatado"] = (
                gastos_por_eixo["Percentual"]
                .apply(lambda valor: f"{valor:.1%}")
            )

            coluna_tabela, coluna_grafico = st.columns(
                [1, 1.4]
            )

            with coluna_tabela:
                st.markdown("#### Gastos por eixo")

                st.dataframe(
                    gastos_por_eixo[
                        [
                            "Eixo",
                            "Valor formatado",
                            "Percentual formatado",
                        ]
                    ].rename(
                        columns={
                            "Valor formatado": "Valor gasto",
                            "Percentual formatado": "% do total",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            with coluna_grafico:
                st.markdown("#### Distribuição dos gastos")

                grafico_eixos = px.bar(
                    gastos_por_eixo,
                    x="Valor gasto",
                    y="Eixo",
                    orientation="h",
                    text="Percentual formatado",
                    labels={
                        "Valor gasto": "Valor gasto",
                        "Eixo": "Eixo",
                    },
                )

                grafico_eixos.update_layout(
                    yaxis={
                        "categoryorder": "total ascending"
                    },
                    xaxis_tickprefix="R$ ",
                )

                st.plotly_chart(
                    grafico_eixos,
                    use_container_width=True,
                )

        else:
            st.info(
                "Não existem gastos no período selecionado."
            )

        if tipo_visao == "Ano acumulado":
            st.divider()
            st.markdown("#### Evolução mensal e saldo acumulado")

            gastos_mensais = (
                gastos_filtrados
                .groupby("Mês")["Valor gasto"]
                .sum()
                .reindex(range(1, 13), fill_value=0)
            )

            recebimentos_mensais = (
                recebimentos_filtrados
                .groupby("Mês")["Valor recebido"]
                .sum()
                .reindex(range(1, 13), fill_value=0)
            )

            evolucao = pd.DataFrame(
                {
                    "Mês número": range(1, 13),
                    "Gastos": gastos_mensais.values,
                    "Recebimentos": recebimentos_mensais.values,
                }
            )

            evolucao["Saldo mensal"] = (
                evolucao["Recebimentos"]
                - evolucao["Gastos"]
            )

            evolucao["Saldo acumulado"] = (
                evolucao["Saldo mensal"].cumsum()
            )

            evolucao["Mês"] = evolucao["Mês número"].map(
                meses
            )

            grafico_acumulado = px.line(
                evolucao,
                x="Mês",
                y="Saldo acumulado",
                markers=True,
                labels={
                    "Saldo acumulado": "Saldo acumulado",
                    "Mês": "Mês",
                },
            )

            grafico_acumulado.update_yaxes(
                tickprefix="R$ "
            )

            st.plotly_chart(
                grafico_acumulado,
                use_container_width=True,
            )

            st.dataframe(
                evolucao[
                    [
                        "Mês",
                        "Gastos",
                        "Recebimentos",
                        "Saldo mensal",
                        "Saldo acumulado",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Gastos": st.column_config.NumberColumn(
                        format="R$ %.2f"
                    ),
                    "Recebimentos": st.column_config.NumberColumn(
                        format="R$ %.2f"
                    ),
                    "Saldo mensal": st.column_config.NumberColumn(
                        format="R$ %.2f"
                    ),
                    "Saldo acumulado": st.column_config.NumberColumn(
                        format="R$ %.2f"
                    ),
                },
            )

        st.divider()
        st.markdown("#### Salvar sua base")

        arquivo_excel = gerar_excel(
            gastos=st.session_state.gastos,
            recebimentos=st.session_state.recebimentos,
        )

        st.download_button(
            label="Baixar base consolidada em Excel",
            data=arquivo_excel,
            file_name="controle_financeiro.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
