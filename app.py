import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Marketing Directo – Calculadora SQL", layout="wide")


# ------------------ PÁGINA: CALCULADORA ------------------ #
def page_calculadora():
    st.header("Calculadora de Marketing Directo (SQL y costos)")

    with st.form("calc_form"):
        # Datos generales de la base y del canal
        colA, colB, colC = st.columns(3)
        base_label = colA.text_input(
            "Descripción de la base",
            "MQLs abiertos de Empresarios y Contadores",
        )
        canal = colB.text_input("Canal", "Wapp")
        moneda = colC.text_input("Moneda", "USD")

        col1, col2, col3 = st.columns(3)
        costo_unit = col1.number_input(
            "Costo unitario por envío",
            min_value=0.0,
            value=0.067,
            step=0.001,
            format="%.4f",
            help="Ejemplo: 0.067 USD por WhatsApp",
        )
        num_envios_contacto = col2.number_input(
            "Cantidad de envíos por contacto",
            min_value=0.0,
            value=1.0,
            step=0.5,
            help="1 envío = un solo push por contacto",
        )
        budget_input = col3.number_input(
            "Budget total (opcional)",
            min_value=0.0,
            value=200.06,
            step=1.0,
            help="Si lo dejas en 0, se calcula con costo_unit x envíos",
        )

        st.markdown("#### Segmentos (puedes editar, borrar o añadir filas)")

        # Estado inicial de segmentos (solo vive en la sesión actual)
        if "segmentos_df" not in st.session_state:
            st.session_state.segmentos_df = pd.DataFrame(
                {
                    "segmento": ["Contadores", "Empresarios"],
                    "base_contactos": [1833, 1025],
                    "usa_segmento": [True, True],
                    "directo_sql": [True, True],
                    "tasa_mql": [0.0, 0.0],   # no aplica si es directo_sql
                    "tasa_sql": [0.035, 0.035],  # 3.5% aprox
                }
            )

        segmentos_df = st.data_editor(
            st.session_state.segmentos_df,
            num_rows="dynamic",
            use_container_width=True,
            key="segmentos_editor",
            column_config={
                "segmento": st.column_config.TextColumn("Segmento"),
                "base_contactos": st.column_config.NumberColumn(
                    "Base contactos", min_value=0
                ),
                "usa_segmento": st.column_config.CheckboxColumn("Usar"),
                "directo_sql": st.column_config.CheckboxColumn(
                    "Directo a SQL (MQL=SQL)"
                ),
                "tasa_mql": st.column_config.NumberColumn(
                    "Tasa MQL (0-1)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                ),
                "tasa_sql": st.column_config.NumberColumn(
                    "Tasa SQL (0-1)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                ),
            },
        )

        submitted = st.form_submit_button("Calcular")

    if not submitted:
        return

    # Guardar cambios en sesión
    st.session_state.segmentos_df = segmentos_df

    # ---- Cálculos ---- #
    resultados_segmentos = []
    total_base = 0
    total_envios = 0
    total_sql = 0

    for _, row in segmentos_df.iterrows():
        if not row.get("usa_segmento", True):
            continue

        base = int(row.get("base_contactos") or 0)
        if base <= 0:
            continue

        total_base += base

        # Envíos por segmento
        envios = base * num_envios_contacto
        total_envios += envios

        # Lógica de funnel
        if row.get("directo_sql", False):
            tasa_sql = float(row.get("tasa_sql") or 0.0)
            mql = math.floor(base * tasa_sql)  # MQL = contactos que responden
            sql = mql  # 100% de MQL pasan a SQL
            nota = "todos los contactos efectivos pasan directo a comercial (paso MQL-SQL 100%)"
        else:
            tasa_mql = float(row.get("tasa_mql") or 0.0)
            tasa_sql = float(row.get("tasa_sql") or 0.0)
            mql = math.floor(base * tasa_mql)
            sql = math.floor(mql * tasa_sql)
            nota = "MQL → SQL según tasas configuradas"

        total_sql += sql

        resultados_segmentos.append(
            {
                "segmento": row["segmento"],
                "base": base,
                "envios": int(envios),
                "mql": mql,
                "sql": sql,
                "nota": nota,
            }
        )

    # Budget
    if budget_input and budget_input > 0:
        budget = budget_input
    else:
        budget = total_envios * costo_unit

    costo_por_sql = (budget / total_sql) if total_sql > 0 else 0.0

    # ---- Métricas arriba ---- #
    col1, col2, col3 = st.columns(3)
    col1.metric("Base total", f"{int(total_base):,}")
    col2.metric("SQL totales", f"{int(total_sql):,}")
    col3.metric("Costo por SQL", f"{costo_por_sql:.2f} {moneda}")

    # ---- Formato de salida tipo informe (para copiar/pegar en Teams / mail) ---- #
    lines = []
    lines.append(f"Base: {base_label}")
    lines.append(f"Cantidad: {int(total_base):,}")
    lines.append(f"Canales: {canal}")
    lines.append(f"Cantidad de envíos: {num_envios_contacto:.0f} envío(s)")
    lines.append(f"Budget: {budget:.2f} {moneda}")
    lines.append("Funnel * validado por segmentos sin nuestro ok")

    for seg in resultados_segmentos:
        lines.append(f"{seg['segmento']}:")
        lines.append(
            f"                                                              i.      Base {seg['base']} contactos"
        )
        lines.append(
            f"                                                            ii.      Envíos: {seg['envios']} {canal.lower()}"
        )
        lines.append(
            f"                                                          iii.      MQLs: {seg['mql']}"
        )
        lines.append(
            f"                                                           iv.      SQLs: {seg['sql']} -> {seg['nota']}"
        )
        lines.append("")

    lines.append("Costos:")
    lines.append(f"SQLs totales: {int(total_sql)}")
    lines.append(f"Costo por sql: {costo_por_sql:.2f} {moneda}")

    output_text = "\n".join(lines)

    st.markdown("### Output en formato texto para copiar")
    st.text_area("Formato calculado", value=output_text, height=320)

    st.markdown("### Tabla de resultados por segmento")
    if resultados_segmentos:
        st.dataframe(pd.DataFrame(resultados_segmentos), use_container_width=True)
    else:
        st.info("Configura al menos un segmento con base > 0.")


# ------------------ PÁGINA: COPIES (SIN BASE) ------------------ #
def page_copies():
    st.header("Vista de copies (solo referencia, sin base de datos)")
    st.info(
        "Aquí puedes registrar copies y sus resultados de campañas anteriores. "
        "La información solo vive en esta sesión (no se guarda en ninguna base)."
    )

    if "copies_df" not in st.session_state:
        st.session_state.copies_df = pd.DataFrame(
            columns=[
                "campaña",
                "canal",
                "pais",
                "segmento",
                "objetivo",
                "copy_texto",
                "tasa_respuesta",
                "sql_generados",
                "es_ganador",
            ]
        )

    copies_df = st.data_editor(
        st.session_state.copies_df,
        use_container_width=True,
        num_rows="dynamic",
        key="copies_editor",
        column_config={
            "es_ganador": st.column_config.CheckboxColumn("Es ganador"),
            "tasa_respuesta": st.column_config.NumberColumn(
                "Tasa respuesta (0-1)",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
            ),
            "sql_generados": st.column_config.NumberColumn(
                "SQL generados", min_value=0, step=1
            ),
        },
    )

    st.session_state.copies_df = copies_df

    solo_ganadores = st.checkbox("Mostrar solo ganadores", value=False)
    if solo_ganadores:
        df_show = copies_df[copies_df["es_ganador"] == True]
    else:
        df_show = copies_df

    st.markdown("#### Copies filtrados")
    st.dataframe(df_show, use_container_width=True)


# ------------------ MAIN ------------------ #
def main():
    st.title("Marketing Directo – Calculadora rápida")

    page = st.sidebar.radio("Navegación", ["Calculadora", "Copies"])
    if page == "Calculadora":
        page_calculadora()
    else:
        page_copies()


if __name__ == "__main__":
    main()
