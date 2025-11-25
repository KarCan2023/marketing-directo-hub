import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Marketing Directo – Calculadora SQL", layout="wide")

# ------------------ CONFIG CANALES ------------------ #
# Costos base y tasas por canal. Siempre calculamos en COP internamente.
CHANNELS = {
    "WhatsApp": {
        "moneda": "USD",
        "costo": 0.067,     # 0.067 USD por envío
        "tasa_mql": 0.0,    # no aplica en directo
        "tasa_sql": 0.03,   # 3% directo a SQL
    },
    "SMS": {
        "moneda": "COP",
        "costo": 6.0,       # 6 COP por SMS
        "tasa_mql": 0, # 0.08% MQL
        "tasa_sql": 0,   # 30% de los MQL pasan a SQL
    },
    "Email": {
        "moneda": "COP",
        "costo": 12.0,      # 12 COP
        "tasa_mql": 0.0015, # 0.15% MQL
        "tasa_sql": 0.134,  # 13.4% de los MQL pasan a SQL
    },
    "Call Blasting": {
        "moneda": "COP",
        "costo": 175.0,     # 175 COP
        "tasa_mql": 0,
        "tasa_sql": 0,   # 10% directo a SQL (referencial)
    },
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
        st.markdown("### Datos de la campaña")

        base_label = st.text_input(
            "Descripción de la base",
            "MQLs abiertos de Empresarios y Contadores",
        )

        colA, colB, colC = st.columns(3)
        cantidad_contactos = colA.number_input(
            "Cantidad de contactos en la base",
            min_value=0,
            value=2858,
            step=100,
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

        col1, col2, col3 = st.columns(3)
        tipo_funnel = col1.radio(
            "Tipo de funnel de la campaña",
            ["Directo a SQL", "MQL → SQL"],
            index=0,
            help=(
                "Directo a SQL: la tasa SQL aplica sobre la base y MQL=SQL.\n"
                "MQL → SQL: primero tasa MQL sobre base y luego tasa SQL sobre MQL."
            ),
            horizontal=True,
        )

        canal = col2.selectbox(
            "Canal",
            list(CHANNELS.keys()),
        )

        segmento = col3.radio(
            "Segmento",
            ["Contadores", "Empresarios", "Empresarios y Contadores", "Otro"],
            index=2,
            horizontal=True,
        )

        # Costo unitario según canal
        costo_unit_display = get_cost_display(canal, moneda_trabajo, tipo_cambio)
        st.info(
            f"Costo unitario estimado para {canal}: "
            f"**{costo_unit_display:.4f} {moneda_trabajo}**"
        )

        submitted = st.form_submit_button("Calcular")

    if not submitted:
        return

    # ------------------ CÁLCULOS ------------------ #
    if cantidad_contactos <= 0 or num_envios_contacto <= 0:
        st.warning("La cantidad de contactos y de envíos deben ser mayores a 0.")
        return

    info_canal = CHANNELS[canal]
    tasa_mql = float(info_canal["tasa_mql"])
    tasa_sql = float(info_canal["tasa_sql"])

    envios = cantidad_contactos * num_envios_contacto
    costo_unit_cop = get_cost_cop(canal, tipo_cambio)
    costo_total_cop = envios * costo_unit_cop

    # Funnel
    if tipo_funnel == "Directo a SQL":
        mql = math.floor(cantidad_contactos * tasa_sql)  # contactos efectivos
        sql = mql                                        # MQL = SQL
        nota = "todos los contactos efectivos pasan directo a comercial (paso MQL-SQL 100%)"
    else:
        mql = math.floor(cantidad_contactos * tasa_mql)
        sql = math.floor(mql * tasa_sql)
        nota = "MQL → SQL según tasas configuradas para el canal"

    # Costos en moneda de trabajo
    if moneda_trabajo == "COP":
        costo_total_calc = costo_total_cop
    else:
        costo_total_calc = costo_total_cop / tipo_cambio if tipo_cambio > 0 else 0.0

    # Budget opcional convertido a COP
    if budget_input and budget_input > 0:
        budget_cop = budget_input * (tipo_cambio if moneda_trabajo == "USD" else 1.0)
    else:
        budget_cop = 0.0

    # Costo por SQL con costo calculado
    if sql > 0:
        cps_calc_cop = costo_total_cop / sql
        cps_calc = cps_calc_cop if moneda_trabajo == "COP" else cps_calc_cop / tipo_cambio
    else:
        cps_calc_cop = 0.0
        cps_calc = 0.0

    # Costo por SQL según budget (si lo hay)
    cps_budget = None
    if budget_cop > 0 and sql > 0:
        cps_budget_cop = budget_cop / sql
        cps_budget = cps_budget_cop if moneda_trabajo == "COP" else cps_budget_cop / tipo_cambio

    # ------------------ MÉTRICAS ARRIBA ------------------ #
    col1, col2, col3 = st.columns(3)
    col1.metric("Base total", f"{int(cantidad_contactos):,}")
    col2.metric("SQL totales", f"{int(sql):,}")
    col3.metric(
        "Costo por SQL (calculado)",
        f"{cps_calc:.2f} {moneda_trabajo}" if sql > 0 else "N/A",
    )

    st.markdown("#### Resumen de costos")
    st.write(
        f"- Costo total estimado (calculado): **{costo_total_calc:,.2f} {moneda_trabajo}** "
        f"(~{costo_total_cop:,.0f} COP)"
    )
    if cps_budget is not None:
        st.write(
            f"- Costo por SQL según budget ({budget_input:.2f} {moneda_trabajo}): "
            f"**{cps_budget:.2f} {moneda_trabajo}**"
        )

    # ------------------ OUTPUT FORMATO TEXTO ------------------ #
    # Budget que mostramos en el texto: si el usuario ingresó uno, ese; si no, el calculado
    if budget_input and budget_input > 0:
        budget_out = budget_input
    else:
        budget_out = costo_total_calc

    lines = []
    lines.append(f"Base: {base_label}")
    lines.append(f"Cantidad: {int(cantidad_contactos):,}")
    lines.append(f"Canales: {canal}")
    lines.append(f"Cantidad de envíos: {num_envios_contacto:.0f} envío(s)")
    lines.append(f"Budget: {budget_out:.2f} {moneda_trabajo}")
    lines.append("Funnel * validado por segmentos sin nuestro ok")

    lines.append(f"{segmento}:")
    lines.append(
        f"                                                              i.      Base {int(cantidad_contactos)} contactos"
    )
    lines.append(
        f"                                                            ii.      Envíos: {int(envios)} {canal.lower()}"
    )
    lines.append(
        f"                                                          iii.      MQLs: {int(mql)}"
    )
    lines.append(
        f"                                                           iv.      SQLs: {int(sql)} -> {nota}"
    )
    lines.append("")
    lines.append("Costos:")
    lines.append(f"SQLs totales: {int(sql)}")
    lines.append(
        f"Costo total estimado: {costo_total_calc:.2f} {moneda_trabajo} (~{costo_total_cop:,.0f} COP)"
    )
    lines.append(f"Costo por sql: {cps_calc:.2f} {moneda_trabajo}")
    if cps_budget is not None:
        lines.append(
            f"Costo por sql (según budget {budget_out:.2f} {moneda_trabajo}): {cps_budget:.2f} {moneda_trabajo}"
        )

    output_text = "\n".join(lines)

    st.markdown("### Output en formato texto para copiar")
    st.text_area("Formato calculado", value=output_text, height=360)

    st.markdown("### Detalle de la campaña")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "segmento": segmento,
                    "canal": canal,
                    "base": cantidad_contactos,
                    "envios": int(envios),
                    "mql": int(mql),
                    "sql": int(sql),
                    "costo_total_cop": int(costo_total_cop),
                    "costo_por_sql_cop": round(cps_calc_cop, 2) if sql > 0 else 0,
                }
            ]
        ),
        use_container_width=True,
    )


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
