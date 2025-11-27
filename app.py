import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Marketing Directo – Calculadora SQL", layout="wide")

# ------------------ COSTOS POR PAÍS (EN COP) ------------------ #
# Nota: para SMS usamos proveedor Masive (marketing masivo).
# Si quieres usar Nua (18 COP), cambia los valores de "SMS" a 18 donde aplique.
COSTOS_POR_PAIS = {
    "Colombia": {
        "WhatsApp": 320,       # Whatsapp - Treble
        "Email": 134,          # Correo
        "SMS": 5,              # SMS - Masive
        "Call Blasting": 175,
    },
    "México": {
        "WhatsApp": 320,       # Whatsapp - Treble
        "Email": 134,          # Correo
        "SMS": 40,             # SMS - Masive
        "Call Blasting": 175,
    },
    "Ecuador": {
        "WhatsApp": 320,       # Whatsapp - Treble
        "Email": 134,          # Correo
        "SMS": 120,            # SMS - Masive
        "Call Blasting": 175,
    },
    "Uruguay": {
        "WhatsApp": 320,       # Whatsapp - Treble
        "Email": 140,          # Correo
        "SMS": 200,            # SMS - Masive
        "Call Blasting": 175,
    },
    "Chile": {
        "WhatsApp": 800,       # Whatsapp - Atom
        "Email": 119,          # Correo
        # Sin costos cargados para SMS / Call Blasting en Chile
    },
}

# ------------------ CUPOS DE ENVÍOS POR PAÍS / PERÍODO ------------------ #
# Valores en cantidad de envíos disponibles por período.
MAX_ENVIOS = {
    "Colombia": {
        "Mensual": {
            "Empresarios": {
                "WhatsApp": 5326,
                "SMS": 26628,
                "Call Blasting": 6657,
            },
            "Aliados": {
                "WhatsApp": 3550,
                "SMS": 17752,
                "Call Blasting": 4438,
            },
        },
        "Anual": {
            "Empresarios": {
                "WhatsApp": 63912,
                "SMS": 319536,
                "Call Blasting": 79884,
            },
            "Aliados": {
                "WhatsApp": 42600,
                "SMS": 213024,
                "Call Blasting": 53256,
            },
        },
    },
    "México": {
        "Mensual": {
            "Empresarios": {
                "WhatsApp": 2580,
                "SMS": 16700,
                "Call Blasting": 2500,
            },
            "Aliados": {
                "WhatsApp": 1435,
                "SMS": 8000,
                "Call Blasting": 2250,
            },
        },
        "Anual": {
            "Empresarios": {
                "WhatsApp": 30960,
                "SMS": 200400,
                "Call Blasting": 30000,
            },
            "Aliados": {
                "WhatsApp": 17220,
                "SMS": 96000,
                "Call Blasting": 27000,
            },
        },
    },
    "Ecuador": {
        "Mensual": {
            "Empresarios": {
                "WhatsApp": 640,
                "SMS": 425,
                "Call Blasting": 155,
            },
            "Aliados": {
                "WhatsApp": 640,
                "SMS": 425,
                "Call Blasting": 155,
            },
        },
        "Anual": {
            "Empresarios": {
                "WhatsApp": 7680,
                "SMS": 5100,
                "Call Blasting": 1860,
            },
            "Aliados": {
                "WhatsApp": 7680,
                "SMS": 5100,
                "Call Blasting": 1860,
            },
        },
    },
    # Uruguay y Chile sin cupos definidos en esta tabla.
}

# ------------------ CONFIG CANALES (TASAS) ------------------ #
# Aquí dejamos solo tasas. El costo se toma de COSTOS_POR_PAIS.
CHANNELS = {
    "WhatsApp": {
        "moneda": "USD",
        "costo": 0.09,     # solo fallback, ya no se usa si hay país
        "tasa_mql": 0.0,   # no aplica en directo
        "tasa_sql": 0.03,  # 3% directo a SQL
    },
    "SMS": {
        "moneda": "COP",
        "costo": 4.0,      # fallback
        "tasa_mql": 0.0,
        "tasa_sql": 0.0,
    },
    "Email": {
        "moneda": "COP",
        "costo": 12.0,      # fallback
        "tasa_mql": 0.0015, # 0.15% MQL
        "tasa_sql": 0.134,  # 13.4% de los MQL pasan a SQL
    },
    "Call Blasting": {
        "moneda": "COP",
        "costo": 175.0,     # fallback
        "tasa_mql": 0.0,
        "tasa_sql": 0.0,
    },
}


def normalizar_segmento_para_cupo(segmento_ui: str):
    """
    Mapea el segmento de la UI a las llaves de MAX_ENVIOS.
    Empresarios → 'Empresarios'
    Contadores / Aliados / Emp + Contadores → 'Aliados'
    """
    seg = segmento_ui.lower()
    if "empresarios" in seg and "contadores" not in seg:
        return "Empresarios"
    if "aliados" in seg or "contadores" in seg:
        return "Aliados"
    if "empresarios y contadores" in seg:
        return "Aliados"
    return None


def get_max_envios(pais, periodo, segmento_ui, canal):
    seg_key = normalizar_segmento_para_cupo(segmento_ui)
    if seg_key is None:
        return None
    return (
        MAX_ENVIOS
        .get(pais, {})
        .get(periodo, {})
        .get(seg_key, {})
        .get(canal)
    )


def get_cost_cop(canal, fx, pais=None) -> float:
    """Devuelve el costo por envío en COP para un canal dado."""
    # 1) Si hay costo definido por país, usamos ese.
    if pais:
        costo_pais = COSTOS_POR_PAIS.get(pais, {}).get(canal)
        if costo_pais is not None:
            return float(costo_pais)

    # 2) Fallback: tabla genérica CHANNELS
    info = CHANNELS.get(canal)
    if info is None:
        return 0.0
    if info["moneda"] == "COP":
        return float(info["costo"])
    # USD → COP
    return float(info["costo"]) * fx


def get_cost_display(canal, moneda_trabajo, fx, pais=None) -> float:
    """
    Devuelve el costo unitario en la moneda seleccionada para trabajar (COP / USD),
    pero internamente siempre parte de COP.
    """
    costo_cop = get_cost_cop(canal, fx, pais)
    if moneda_trabajo == "COP":
        return costo_cop
    if fx <= 0:
        return 0.0
    return costo_cop / fx


# ------------------ PÁGINA: CALCULADORA ------------------ #
def page_calculadora():
    st.header("Calculadora de Marketing Directo (SQL y costos)")

    with st.form("calc_form"):
        # País, moneda y tasa de cambio
        colp, colm1, colm2 = st.columns(3)
        pais = colp.selectbox(
            "País",
            list(COSTOS_POR_PAIS.keys()),
        )
        moneda_trabajo = colm1.selectbox(
            "Moneda de trabajo (visualización)",
            ["COP", "USD"],
            help="Si eliges USD, igualmente todos los cálculos internos se hacen en COP.",
        )
        tipo_cambio = colm2.number_input(
            "Tasa de cambio USD → COP",
            min_value=1.0,
            value=4000.0,
            step=50.0,
            help="Ejemplo: 1 USD = 4000 COP.",
        )

        # Datos generales de la base / campaña
        st.markdown("### Datos de la campaña")

        col_per, col_dummy = st.columns(2)
        periodo_cupo = col_per.radio(
            "Periodo de referencia para cupos de envíos",
            ["Mensual", "Anual"],
            horizontal=True,
            index=0,
        )

        base_label = st.text_input(
            "Descripción de la base",
            "MQLs abiertos de Empresarios y Contadores",
        )

        colA, colB, colC = st.columns(3)
        cantidad_contactos = colA.number_input(
            "Cantidad de contactos en la base canal 1",
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

        canal1 = col2.selectbox(
            "Canal 1",
            list(CHANNELS.keys()),
            key="canal1",
        )
        add_second = col2.checkbox("Añadir segundo canal", value=False, key="add_second")

        segmento = col3.radio(
            "Segmento",
            ["Contadores", "Empresarios", "Empresarios y Contadores", "Otro"],
            index=2,
            horizontal=True,
        )

        # --- Canal 1: tasas editables --- #
        info_canal1_default = CHANNELS[canal1]
        col_t1, col_t2 = st.columns(2)
        tasa_mql1_input = col_t1.number_input(
            "Tasa MQL canal 1 (0-1, editable)",
            min_value=0.0,
            max_value=1.0,
            step=0.0001,
            value=float(info_canal1_default["tasa_mql"]),
            format="%.4f",
            help="Solo aplica si el funnel es MQL → SQL.",
        )
        tasa_sql1_input = col_t2.number_input(
            "Tasa SQL canal 1 (0-1, editable)",
            min_value=0.0,
            max_value=1.0,
            step=0.0001,
            value=float(info_canal1_default["tasa_sql"]),
            format="%.4f",
            help="En Directo: tasa de contactos que llegan a SQL. En MQL→SQL: tasa de MQL que pasan a SQL.",
        )

        # Costo unitario canal 1
        costo_unit1_display = get_cost_display(canal1, moneda_trabajo, tipo_cambio, pais)
        if moneda_trabajo == "COP":
            costo1_fmt = f"{costo_unit1_display:,.0f}"
        else:
            costo1_fmt = f"{costo_unit1_display:.4f}"
        st.info(
            f"Costo unitario estimado Canal 1 ({canal1}) en {pais}: "
            f"**{costo1_fmt} {moneda_trabajo}**"
        )

        # --- Canal 2 y 3: inicialización de variables --- #
        canal2 = None
        cantidad_contactos_2 = 0
        tasa_mql2_input = 0.0
        tasa_sql2_input = 0.0

        add_third = False
        canal3 = None
        cantidad_contactos_3 = 0
        tasa_mql3_input = 0.0
        tasa_sql3_input = 0.0

        # --- Canal 2 opcional --- #
        if add_second:
            st.markdown("### Canal 2 (opcional)")
            col2a, col2b = st.columns(2)
            canal2 = col2a.selectbox(
                "Canal 2",
                list(CHANNELS.keys()),
                key="canal2",
            )
            cantidad_contactos_2 = col2b.number_input(
                "Cantidad de contactos en la base canal 2",
                min_value=0,
                value=0,
                step=100,
            )

            info_canal2_default = CHANNELS[canal2]
            col2_t1, col2_t2 = st.columns(2)
            tasa_mql2_input = col2_t1.number_input(
                "Tasa MQL canal 2 (0-1, editable)",
                min_value=0.0,
                max_value=1.0,
                step=0.0001,
                value=float(info_canal2_default["tasa_mql"]),
                format="%.4f",
                help="Solo aplica si el funnel es MQL → SQL.",
            )
            tasa_sql2_input = col2_t2.number_input(
                "Tasa SQL canal 2 (0-1, editable)",
                min_value=0.0,
                max_value=1.0,
                step=0.0001,
                value=float(info_canal2_default["tasa_sql"]),
                format="%.4f",
                help="En Directo: tasa de contactos que llegan a SQL. En MQL→SQL: tasa de MQL que pasan a SQL.",
            )

            costo_unit2_display = get_cost_display(canal2, moneda_trabajo, tipo_cambio, pais)
            if moneda_trabajo == "COP":
                costo2_fmt = f"{costo_unit2_display:,.0f}"
            else:
                costo2_fmt = f"{costo_unit2_display:.4f}"
            st.info(
                f"Costo unitario estimado Canal 2 ({canal2}) en {pais}: "
                f"**{costo2_fmt} {moneda_trabajo}**"
            )

            # --- Canal 3 opcional --- #
            add_third = st.checkbox("Añadir tercer canal", value=False, key="add_third")
            if add_third:
                st.markdown("### Canal 3 (opcional)")
                col3a, col3b = st.columns(2)
                canal3 = col3a.selectbox(
                    "Canal 3",
                    list(CHANNELS.keys()),
                    key="canal3",
                )
                cantidad_contactos_3 = col3b.number_input(
                    "Cantidad de contactos en la base canal 3",
                    min_value=0,
                    value=0,
                    step=100,
                )

                info_canal3_default = CHANNELS[canal3]
                col3_t1, col3_t2 = st.columns(2)
                tasa_mql3_input = col3_t1.number_input(
                    "Tasa MQL canal 3 (0-1, editable)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.0001,
                    value=float(info_canal3_default["tasa_mql"]),
                    format="%.4f",
                    help="Solo aplica si el funnel es MQL → SQL.",
                )
                tasa_sql3_input = col3_t2.number_input(
                    "Tasa SQL canal 3 (0-1, editable)",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.0001,
                    value=float(info_canal3_default["tasa_sql"]),
                    format="%.4f",
                    help="En Directo: tasa de contactos que llegan a SQL. En MQL→SQL: tasa de MQL que pasan a SQL.",
                )

                costo_unit3_display = get_cost_display(
                    canal3, moneda_trabajo, tipo_cambio, pais
                )
                if moneda_trabajo == "COP":
                    costo3_fmt = f"{costo_unit3_display:,.0f}"
                else:
                    costo3_fmt = f"{costo_unit3_display:.4f}"
                st.info(
                    f"Costo unitario estimado Canal 3 ({canal3}) en {pais}: "
                    f"**{costo3_fmt} {moneda_trabajo}**"
                )

        submitted = st.form_submit_button("Calcular")

    if not submitted:
        return

    # ------------------ ARMAR CONFIG DE CANALES ------------------ #
    canales_config = []

    # Canal 1
    if cantidad_contactos > 0:
        canales_config.append(
            {
                "canal": canal1,
                "tasa_mql": float(tasa_mql1_input),
                "tasa_sql": float(tasa_sql1_input),
                "base": int(cantidad_contactos),
            }
        )

    # Canal 2
    if add_second and canal2 is not None and cantidad_contactos_2 > 0:
        canales_config.append(
            {
                "canal": canal2,
                "tasa_mql": float(tasa_mql2_input),
                "tasa_sql": float(tasa_sql2_input),
                "base": int(cantidad_contactos_2),
            }
        )

    # Canal 3
    if add_second and add_third and canal3 is not None and cantidad_contactos_3 > 0:
        canales_config.append(
            {
                "canal": canal3,
                "tasa_mql": float(tasa_mql3_input),
                "tasa_sql": float(tasa_sql3_input),
                "base": int(cantidad_contactos_3),
            }
        )

    if not canales_config:
        st.warning("Configura al menos un canal con base > 0.")
        return

    if num_envios_contacto <= 0:
        st.warning("La cantidad de envíos por contacto debe ser mayor a 0.")
        return

    # ------------------ CÁLCULO POR CANAL ------------------ #
    resultados_canales = []
    total_base = 0
    total_envios = 0
    total_mql = 0
    total_sql = 0
    total_costo_cop = 0.0

    for cfg in canales_config:
        canal = cfg["canal"]
        base = cfg["base"]
        tasa_mql = cfg["tasa_mql"]
        tasa_sql = cfg["tasa_sql"]

        envios = base * num_envios_contacto
        costo_unit_cop = get_cost_cop(canal, tipo_cambio, pais)
        costo_canal_cop = envios * costo_unit_cop

        # Funnel por canal
        if tipo_funnel == "Directo a SQL":
            mql = math.floor(base * tasa_sql)  # contactos efectivos
            sql = mql                         # MQL = SQL
            nota = "todos los contactos efectivos pasan directo a comercial (paso MQL-SQL 100%)"
        else:
            mql = math.floor(base * tasa_mql)
            sql = math.floor(mql * tasa_sql)
            nota = "MQL → SQL según tasas configuradas para el canal"

        total_base += base
        total_envios += envios
        total_mql += mql
        total_sql += sql
        total_costo_cop += costo_canal_cop

        # Cupos de envíos para este canal
        max_envios = get_max_envios(pais, periodo_cupo, segmento, canal)
        if max_envios is not None and max_envios > 0:
            uso_cupo_pct = round(envios / max_envios * 100, 1)
        else:
            uso_cupo_pct = None

        cps_canal_cop = costo_canal_cop / sql if sql > 0 else 0.0

        resultados_canales.append(
            {
                "pais": pais,
                "periodo_cupo": periodo_cupo,
                "segmento": segmento,
                "canal": canal,
                "base": base,
                "envios": int(envios),
                "cupo_envios_periodo": int(max_envios) if max_envios is not None else None,
                "uso_cupo_%": uso_cupo_pct,
                "mql": int(mql),
                "sql": int(sql),
                "costo_total_cop": int(costo_canal_cop),
                "costo_por_sql_cop": int(round(cps_canal_cop)) if sql > 0 else 0,
                "nota": nota,
            }
        )

    # Si no hay SQL, evitamos divisiones raras
    if total_sql > 0:
        cps_calc_cop = total_costo_cop / total_sql
    else:
        cps_calc_cop = 0.0

    # Costos en moneda de trabajo (totales)
    if moneda_trabajo == "COP":
        costo_total_calc = total_costo_cop
    else:
        costo_total_calc = total_costo_cop / tipo_cambio if tipo_cambio > 0 else 0.0

    cps_calc = cps_calc_cop if moneda_trabajo == "COP" else (
        cps_calc_cop / tipo_cambio if tipo_cambio > 0 else 0.0
    )

    # Budget opcional convertido a COP
    if budget_input and budget_input > 0:
        budget_cop = budget_input * (tipo_cambio if moneda_trabajo == "USD" else 1.0)
    else:
        budget_cop = 0.0

    cps_budget = None
    if budget_cop > 0 and total_sql > 0:
        cps_budget_cop = budget_cop / total_sql
        cps_budget = cps_budget_cop if moneda_trabajo == "COP" else cps_budget_cop / tipo_cambio

    # ------------------ MÉTRICAS ARRIBA ------------------ #
    if moneda_trabajo == "COP":
        cps_metric_fmt = f"{cps_calc:,.0f}" if total_sql > 0 else "N/A"
    else:
        cps_metric_fmt = f"{cps_calc:.2f}" if total_sql > 0 else "N/A"

    col1, col2, col3 = st.columns(3)
    col1.metric("Base total", f"{int(total_base):,}")
    col2.metric("SQL totales", f"{int(total_sql):,}")
    col3.metric("Costo por SQL (calculado)", f"{cps_metric_fmt} {moneda_trabajo}")

    # ------------------ CUPOS / USO DE ENVÍOS ------------------ #
    st.markdown("#### Uso de cupos de envíos (por país / período / canal)")
    tiene_cupos = False
    for r in resultados_canales:
        max_env = r["cupo_envios_periodo"]
        if max_env is None:
            continue
        tiene_cupos = True
        envios = r["envios"]
        canal = r["canal"]
        if envios > max_env:
            st.warning(
                f"{canal} – planeas {envios:,} envíos y el máximo {r['periodo_cupo'].lower()} "
                f"para {segmento} en {pais} es {max_env:,}. Estás excediendo el cupo."
            )
        else:
            uso_pct = r["uso_cupo_%"] or 0
            st.info(
                f"{canal} – usarías {envios:,} de {max_env:,} envíos {r['periodo_cupo'].lower()} "
                f"({uso_pct:.1f}% del cupo) para {segmento} en {pais}."
            )

    if not tiene_cupos:
        st.caption("No hay tabla de cupos cargada para este país/segmento/canal (o el canal no tiene cupo definido).")

    # ------------------ RESUMEN DE COSTOS ------------------ #
    if moneda_trabajo == "COP":
        costo_total_fmt = f"{costo_total_calc:,.0f}"
    else:
        costo_total_fmt = f"{costo_total_calc:,.2f}"

    st.markdown("#### Resumen de costos")
    st.write(
        f"- Costo total estimado (calculado): **{costo_total_fmt} {moneda_trabajo}** "
        f"(~{total_costo_cop:,.0f} COP)"
    )
    if cps_budget is not None:
        if moneda_trabajo == "COP":
            cps_budget_fmt = f"{cps_budget:,.0f}"
        else:
            cps_budget_fmt = f"{cps_budget:.2f}"
        st.write(
            f"- Costo por SQL según budget ({budget_input:.2f} {moneda_trabajo}): "
            f"**{cps_budget_fmt} {moneda_trabajo}**"
        )

    # ------------------ OUTPUT FORMATO TEXTO ------------------ #
    # Budget que mostramos en el texto: si el usuario ingresó uno, ese; si no, el calculado
    if budget_input and budget_input > 0:
        budget_out = budget_input
    else:
        budget_out = costo_total_calc

    if moneda_trabajo == "COP":
        budget_str = f"{budget_out:,.0f}"
        costo_total_calc_str = f"{costo_total_calc:,.0f}"
        cps_calc_str = f"{cps_calc:,.0f}"
        cps_budget_str = f"{cps_budget:,.0f}" if cps_budget is not None else None
    else:
        budget_str = f"{budget_out:.2f}"
        costo_total_calc_str = f"{costo_total_calc:.2f}"
        cps_calc_str = f"{cps_calc:.2f}"
        cps_budget_str = f"{cps_budget:.2f}" if cps_budget is not None else None

    canales_nombres = ", ".join(sorted({r["canal"] for r in resultados_canales}))

    lines = []
    lines.append(f"País: {pais}")
    lines.append(f"Periodo de referencia: {periodo_cupo}")
    lines.append(f"Base: {
