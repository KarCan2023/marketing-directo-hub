import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Marketing Directo – Calculadora SQL", layout="wide")

# ------------------ CONFIG CANALES ------------------ #
# Costos base por canal (modo real):
# - Si la moneda del canal es USD, se convierte a COP con la tasa de cambio.
CHANNELS = {
    "WhatsApp": {"moneda": "USD", "costo": 0.067},  # 0.067 USD por envío
    "SMS": {"moneda": "COP", "costo": 6.0},         # 6 COP
    "Email": {"moneda": "COP", "costo": 12.0},      # 12 COP (mail masivo)
    "Call Blasting": {"moneda": "COP", "costo": 175.0},  # 175 COP
}


def get_cost_cop(canal: str, fx: float) -> float:
    """Devuelve el costo por envío en COP para un canal dado."""
    info = CHANNELS.get(canal)
    if info is None:
        return 0.0
    if info["moneda"] == "COP":
        return float(info["costo"])
    # USD -> COP
    return float(info["costo"]) * fx


def get_cost_display(canal: str, moneda_trabajo: str, fx: float) -> float:
    """
    Devuelve el costo unitario en la moneda seleccionada para trabajar (COP / USD),
    pero internamente siempre parte de COP.
    """
    costo_cop = get_cost_cop(canal, fx)
    if moneda_trabajo == "COP":
        return costo_cop
    if fx <= 0:
        return 0.0
    return costo_cop / fx


# ------------------ PÁGINA: CALCULADORA ------------------ #
def page_calculadora():
    st.header("Calculadora de Marketing Directo (SQL y costos)")

    with st.form("calc_form"):
        # Moneda y tasa de cambio
        colm1, colm2 = st.columns(2)
        moneda_trabajo = colm1.selectbox(
            "Moneda de trabajo (visualización)",
            ["COP", "USD"],
            help="Si eliges USD, igualmente todos los cálculos internos se hacen en COP.",
        )
        tipo_cambio = colm2.number_input(
            "Tasa de cambio USD → COP",
            min_value=1.0,
            value=4200.0,
            step=50.0,
            help="Ejemplo: 1 USD = 4200 COP.",
        )

        # Datos generales de la base / campaña
        colA, colB, colC = st.columns(3)
        base_label = colA.text_input(
            "Descripción de la base",
            "MQLs abiertos de Empresarios y Contadores",
        )
        num_envios_contacto = colB.number_input(
            "Cantidad de envíos por contacto",
            min_value=0.0,
            value=1.0,
            step=0.5,
            help="1 envío = un solo push por contacto.",
        )
        budget_input = colC.number_input(
            f"Budget total (opcional) en {moneda_trabajo}",
            min_value=0.0,
            value=0.0,
            step=10.0,
            help="Si lo dejas en 0, el costo se calcula solo con costos unitarios.",
        )

        # Tipo de funnel global
        tipo_funnel = st.radio(
            "Tipo de funnel de la campaña",
            ["Directo a SQL", "MQL → SQL"],
            index=0,
            help=(
                "Directo a SQL: la tasa SQL aplica sobre la base y MQL=SQL.\n"
                "MQL → SQL: primero tasa MQL sobre base y luego tasa SQL sobre MQL."
            ),
            horizontal=True,
        )

        st.markdown("#### Mix de canales por segmento")

        # Estado inicial de segmentos (solo vive en la sesión actual)
        if "segmentos_df" not in st.session_state:
            st.session_state.segmentos_df = pd.DataFrame(
                {
                    "segmento": ["Contadores", "Empresarios"],
                    "base_contactos": [1833, 1025],
                    "usa_segmento": [True, True],
                    "canal": ["WhatsApp", "WhatsApp"],
                    # Si funnel = Directo a SQL, solo se usa tasa_sql
                    # Si funnel = MQL → SQL, se usan ambas tasas
                    "tasa_mql": [0.0, 0.0],      # no aplica si es directo a SQL
                    "tasa_sql": [0.035, 0.035],  # 3.5% aprox, ejemplo
                }
            )

        df_seg = st.session_state.segmentos_df.copy()

        # Nos aseguramos de que existan todas las columnas
        for col in ["segmento", "base_contactos", "usa_segmento", "canal", "tasa_mql", "tasa_sql"]:
            if col not in df_seg.columns:
                if col == "segmento":
                    df_seg[col] = ""
                elif col in ["base_contactos"]:
                    df_seg[col] = 0
                elif col in ["usa_segmento"]:
                    df_seg[col] = True
                elif col == "canal":
                    df_seg[col] = "WhatsApp"
                else:
                    df_seg[col] = 0.0

        # Costo unitario en la moneda de trabajo (solo visual, no editable)
        df_seg["costo_unitario"] = df_seg["canal"].apply(
            lambda c: get_cost_display(c, moneda_trabajo, tipo_cambio)
        )

        df_edit = st.data_editor(
            df_seg,
            num_rows="dynamic",
            use_container_width=True,
            key="segmentos_editor",
            column_config={
                "segmento": st.column_config.TextColumn("Segmento"),
                "base_contactos": st.column_config.NumberColumn(
                    "Base contactos", min_value=0
                ),
                "usa_segmento": st.column_config.CheckboxColumn("Usar"),
                "canal": st.column_config.SelectboxColumn(
                    "Canal",
                    options=list(CHANNELS.keys()),
                ),
                "tasa_mql": st.column_config.NumberColumn(
                    "Tasa MQL (0-1)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                    help="Solo aplica si el funnel es MQL → SQL.",
                ),
                "tasa_sql": st.column_config.NumberColumn(
                    "Tasa SQL (0-1)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.001,
                    help=(
                        "En Directo a SQL: tasa de contactos que llegan a SQL.\n"
                        "En MQL → SQL: tasa de MQL que pasan a SQL."
                    ),
                ),
                "costo_unitario": st.column_config.NumberColumn(
                    f"Costo unitario ({moneda_trabajo})",
                    disabled=True,
                    help="Calculado automáticamente según canal y tasa de cambio.",
                ),
            },
        )

        submitted = st.form_submit_button("Calcular")

    if not submitted:
        return

    # Guardar cambios en sesión
    st.session_state.segmentos_df = df_edit

    # ------------------ CÁLCULOS ------------------ #
    resultados_segmentos = []
    total_base = 0
    total_envios = 0
    total_sql = 0
    total_costo_cop = 0.0
    canales_usados = set()

    for _, row in df_edit.iterrows():
        if not row.get("usa_segmento", True):
            continue

        base = int(row.get("base_contactos") or 0)
        if base <= 0:
            continue

        canal = row.get("canal", "WhatsApp")
        canales_usados.add(canal)

        # Envíos por segmento
        envios = base * num_envios_contacto
        costo_envio_cop = get_cost_cop(canal, tipo_cambio)
        costo_segmento_cop = envios * costo_envio_cop

        # Funnel
        tasa_mql = float(row.get("tasa_mql") or 0.0)
        tasa_sql = float(row.get("tasa_sql") or 0.0)

        if tipo_funnel == "Directo a SQL":
            # La tasa SQL aplica directo sobre la base
            mql = math.floor(base * tasa_sql)  # contactos efectivos
            sql = mql                           # MQL = SQL
            nota = "todos los contactos efectivos pasan directo a comercial (paso MQL-SQL 100%)"
        else:
            # Funnel MQL → SQL
            mql = math.floor(base * tasa_mql)
            sql = math.floor(mql * tasa_sql)
            nota = "MQL → SQL según tasas configuradas"

        total_base += base
        total_envios += envios
        total_sql += sql
        total_costo_cop += costo_segmento_cop

        resultados_segmentos.append(
            {
                "segmento": row["segmento"],
                "canal": canal,
                "base": base,
                "envios": int(envios),
                "mql": mql,
                "sql": sql,
                "costo_segmento_cop": costo_segmento_cop,
                "nota": nota,
            }
        )

    # Si no hay segmentos válidos, salimos
    if not resultados_segmentos:
        st.info("Configura al menos un segmento con base > 0.")
        return

    # Costos en moneda de trabajo
    if moneda_trabajo == "COP":
        costo_total_calc = total_costo_cop
    else:
        costo_total_calc = total_costo_cop / tipo_cambio if tipo_cambio > 0 else 0.0

    # Budget opcional convertido a COP
    if budget_input and budget_input > 0:
        budget_cop = budget_input * (tipo_cambio if moneda_trabajo == "USD" else 1.0)
    else:
        budget_cop = 0.0

    # Costo por SQL con costo calculado
    if total_sql > 0:
        cps_calc_cop = total_costo_cop / total_sql
        cps_calc = cps_calc_cop if moneda_trabajo == "COP" else cps_calc_cop / tipo_cambio
    else:
        cps_calc_cop = 0.0
        cps_calc = 0.0

    # Costo por SQL según budget (si lo hay)
    cps_budget = None
    if budget_cop > 0 and total_sql > 0:
        cps_budget_cop = budget_cop / total_sql
        cps_budget = cps_budget_cop if moneda_trabajo == "COP" else cps_budget_cop / tipo_cambio

    # ------------------ MÉTRICAS ARRIBA ------------------ #
    col1, col2, col3 = st.columns(3)
    col1.metric("Base total", f"{int(total_base):,}")
    col2.metric("SQL totales", f"{int(total_sql):,}")
    col3.metric(
        "Costo por SQL (calculado)",
        f"{cps_calc:.2f} {moneda_trabajo}" if total_sql > 0 else "N/A",
    )

    st.markdown("#### Resumen de costos")
    st.write(
        f"- Costo total estimado (calculado): **{costo_total_calc:,.2f} {moneda_trabajo}** "
        f"(~{total_costo_cop:,.0f} COP)"
    )
    if cps_budget is not None:
        st.write(
            f"- Costo por SQL según budget ({budget_input:.2f} {moneda_trabajo}): "
            f"**{cps_budget:.2f} {moneda_trabajo}**"
        )

    # ------------------ OUTPUT FORMATO TEXTO ------------------ #
    canales_lista = ", ".join(sorted(canales_usados))

    # Budget que mostramos en el texto: si el usuario ingresó uno, ese; si no, el calculado
    if budget_input and budget_input > 0:
        budget_out = budget_input
    else:
        budget_out = costo_total_calc

    lines = []
    lines.append(f"Base: {base_label}")
    lines.append(f"Cantidad: {int(total_base):,}")
    lines.append(f"Canales: {canales_lista}")
    lines.append(f"Cantidad de envíos: {num_envios_contacto:.0f} envío(s)")
    lines.append(f"Budget: {budget_out:.2f} {moneda_trabajo}")
    lines.append("Funnel * validado por segmentos sin nuestro ok")

    for seg in resultados_segmentos:
        lines.append(f"{seg['segmento']} – {seg['canal']}:")
        lines.append(
            f"                                                              i.      Base {seg['base']} contactos"
        )
        lines.append(
            f"                                                            ii.      Envíos: {seg['envios']} {seg['canal'].lower()}"
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
    lines.append(
        f"Costo total estimado: {costo_total_calc:.2f} {moneda_trabajo} (~{total_costo_cop:,.0f} COP)"
    )
    lines.append(f"Costo por sql: {cps_calc:.2f} {moneda_trabajo}")
    if cps_budget is not None:
        lines.append(
            f"Costo por sql (según budget {budget_out:.2f} {moneda_trabajo}): {cps_budget:.2f} {moneda_trabajo}"
        )

    output_text = "\n".join(lines)

    st.markdown("### Output en formato texto para copiar")
    st.text_area("Formato calculado", value=output_text, height=360)

    st.markdown("### Tabla de resultados por segmento")
    st.dataframe(pd.DataFrame(resultados_segmentos), use_container_width=True)


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
