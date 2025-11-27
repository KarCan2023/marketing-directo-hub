import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Marketing Directo – Calculadora SQL", layout="wide")

# ------------------ CONFIG CANALES BASE ------------------ #

CHANNELS = {
    "WhatsApp": {
        "moneda": "USD",
        "costo": 0.09,   # 0.09 USD por envío
        "tasa_mql": 0.0,
        "tasa_sql": 0.03,
    },
    "SMS": {
        "moneda": "COP",
        "costo": 4.0,      # 4 COP por SMS (solo fallback)
        "tasa_mql": 0.0,
        "tasa_sql": 0.0,
    },
    "Email": {
        "moneda": "COP",
        "costo": 12.0,      # 12 COP (fallback)
        "tasa_mql": 0.0015, # 0.15% MQL
        "tasa_sql": 0.134,  # 13.4% de los MQL pasan a SQL
    },
    "Call Blasting": {
        "moneda": "COP",
        "costo": 175.0,     # 175 COP (fallback)
        "tasa_mql": 0.0,
        "tasa_sql": 0.0,
    },
}

# ------------------ COSTOS POR PAÍS (SIEMPRE EN COP) ------------------ #

PAISES = ["Colombia", "México", "Ecuador", "Uruguay", "Chile"]

COSTO_WAPP_COP = {
    "Colombia": 320,
    "México": 320,
    "Ecuador": 320,
    "Uruguay": 320,
    "Chile": 800,
}

COSTO_EMAIL_COP = {
    "Colombia": 134,
    "México": 134,
    "Ecuador": 134,
    "Uruguay": 140,
    "Chile": 119,
}

COSTO_SMS_NUA_COP = {
    "Colombia": 18,
    "México": 18,
    "Ecuador": 18,
    "Uruguay": 18,
}

COSTO_SMS_MASIVE_COP = {
    "Colombia": 5,
    "México": 40,
    "Ecuador": 120,
    "Uruguay": 200,
}

COSTO_CB_COP = {
    "Colombia": 175,
    "México": 175,
    "Ecuador": 175,
    "Uruguay": 175,
    # Si luego defines CB para Chile, lo añades aquí
}

# ------------------ PPTOS DE ENVÍOS (CANTIDAD MÁXIMA) ------------------ #

BUDGET_ENVIOS = {
    "Colombia": {
        "Mensual": {
            "Empresarios": {"WAPP": 5326, "SMS": 26628, "CB": 6657},
            "Aliados": {"WAPP": 3550, "SMS": 17752, "CB": 4438},
        },
        "Anual": {
            "Empresarios": {"WAPP": 63912, "SMS": 319536, "CB": 79884},
            "Aliados": {"WAPP": 42600, "SMS": 213024, "CB": 53256},
        },
    },
    "México": {
        "Mensual": {
            "Empresarios": {"WAPP": 2580, "SMS": 16700, "CB": 2500},
            "Aliados": {"WAPP": 1435, "SMS": 8000, "CB": 2250},
        },
        "Anual": {
            "Empresarios": {"WAPP": 30960, "SMS": 200400, "CB": 30000},
            "Aliados": {"WAPP": 17220, "SMS": 96000, "CB": 27000},
        },
    },
    "Ecuador": {
        "Mensual": {
            "Empresarios": {"WAPP": 640, "SMS": 425, "CB": 155},
            "Aliados": {"WAPP": 640, "SMS": 425, "CB": 155},
        },
        "Anual": {
            "Empresarios": {"WAPP": 7680, "SMS": 5100, "CB": 1860},
            "Aliados": {"WAPP": 7680, "SMS": 5100, "CB": 1860},
        },
    },
    # Si luego tienes Uruguay / Chile aquí, los agregas igual
}

def _segmento_to_budget_key(segmento_ui: str):
    """
    Mapea el segmento UI a clave de budget (Empresarios/Aliados).
    Contadores los mapeo a Aliados.
    """
    if segmento_ui == "Empresarios":
        return "Empresarios"
    if segmento_ui in ("Contadores", "Aliados"):
        return "Aliados"
    return None

def _canal_to_budget_key(canal: str):
    canal_low = canal.lower()
    if "whatsapp" in canal_low or "wapp" in canal_low:
        return "WAPP"
    if "sms" in canal_low:
        return "SMS"
    if "call blasting" in canal_low or canal_low == "cb":
        return "CB"
    return None

def get_budget_envios_max(pais: str, periodo: str, segmento_ui: str, canal: str):
    """
    Devuelve el cupo máximo de envíos (int) o None si no hay dato.
    """
    seg_key = _segmento_to_budget_key(segmento_ui)
    canal_key = _canal_to_budget_key(canal)

    if not seg_key or not canal_key:
        return None

    pais_dict = BUDGET_ENVIOS.get(pais)
    if not pais_dict:
        return None

    periodo_dict = pais_dict.get(periodo)
    if not periodo_dict:
        return None

    seg_dict = periodo_dict.get(seg_key)
    if not seg_dict:
        return None

    return seg_dict.get(canal_key)

# ------------------ HELPERS DE COSTOS ------------------ #

def get_cost_cop(canal: str, fx: float, pais: str, proveedor_sms: str = "Masive") -> float:
    """
    Devuelve el costo por envío en COP para un canal dado,
    usando primero la tabla por país y, si no existe,
    la config base de CHANNELS.
    """
    if not pais:
        pais = "Colombia"
    pais = pais.strip()

    canal_low = canal.lower()
    base_cop = None

    if "whatsapp" in canal_low:
        base_cop = COSTO_WAPP_COP.get(pais)
    elif canal_low.startswith("email") or "correo" in canal_low:
        base_cop = COSTO_EMAIL_COP.get(pais)
    elif "call blasting" in canal_low or canal_low == "cb":
        base_cop = COSTO_CB_COP.get(pais)
    elif "sms" in canal_low:
        prov = (proveedor_sms or "Masive").lower()
        if prov == "nua":
            base_cop = COSTO_SMS_NUA_COP.get(pais)
        else:
            base_cop = COSTO_SMS_MASIVE_COP.get(pais)

    # Si tengo costo por país, lo uso
    if base_cop is not None:
        return float(base_cop)

    # Fallback: usa CHANNELS original
    info = CHANNELS.get(canal)
    if info is None:
        return 0.0
    if info["moneda"] == "COP":
        return float(info["costo"])
    # USD → COP
    return float(info["costo"]) * fx

def get_cost_display(
    canal: str,
    moneda_trabajo: str,
    fx: float,
    pais: str,
    proveedor_sms: str = "Masive",
) -> float:
    """
    Devuelve el costo unitario en la moneda de trabajo (COP / USD).
    Internamente siempre parte de COP.
    """
    costo_cop = get_cost_cop(canal, fx, pais, proveedor_sms)
    if moneda_trabajo == "COP":
        return costo_cop
    if fx <= 0:
        return 0.0
    return costo_cop / fx

# ------------------ PÁGINA: CALCULADORA ------------------ #

def page_calculadora():
    st.header("Calculadora de Marketing Directo (SQL y costos)")

    with st.form("calc_form"):
        # Moneda, tasa de cambio y país
        colm1, colm2, colm3 = st.columns(3)
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
        pais = colm3.selectbox(
            "País de la campaña",
            PAISES,
        )

        colp1, colp2 = st.columns(2)
        proveedor_sms = colp1.selectbox(
            "Proveedor SMS para esta campaña",
            ["Masive", "Nua"],
            index=0,
            help="Solo afecta el costo del canal SMS según país.",
        )
        periodo_ppto = colp2.selectbox(
            "Período de presupuesto para validar envíos",
            ["Mensual", "Anual"],
            index=0,
        )

        # Datos generales de la base / campaña
        st.markdown("### Datos de la campaña")

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
            ["Contadores", "Empresarios", "Empresarios y Contadores", "Aliados", "Otro"],
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
        costo_unit1_display = get_cost_display(
            canal1, moneda_trabajo, tipo_cambio, pais, proveedor_sms
        )
        if moneda_trabajo == "COP":
            costo1_fmt = f"{costo_unit1_display:,.0f}"
        else:
            costo1_fmt = f"{costo_unit1_display:.4f}"
        st.info(
            f"Costo unitario estimado Canal 1 ({canal1}): "
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

            costo_unit2_display = get_cost_display(
                canal2, moneda_trabajo, tipo_cambio, pais, proveedor_sms
            )
            if moneda_trabajo == "COP":
                costo2_fmt = f"{costo_unit2_display:,.0f}"
            else:
                costo2_fmt = f"{costo_unit2_display:.4f}"
            st.info(
                f"Costo unitario estimado Canal 2 ({canal2}): "
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
                    canal3, moneda_trabajo, tipo_cambio, pais, proveedor_sms
                )
                if moneda_trabajo == "COP":
                    costo3_fmt = f"{costo_unit3_display:,.0f}"
                else:
                    costo3_fmt = f"{costo_unit3_display:.4f}"
                st.info(
                    f"Costo unitario estimado Canal 3 ({canal3}): "
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
        costo_unit_cop = get_cost_cop(canal, tipo_cambio, pais, proveedor_sms)
        costo_canal_cop = envios * costo_unit_cop

        # Funnel por canal
        if tipo_funnel == "Directo a SQL":
            mql = math.floor(base * tasa_sql)  # contactos efectivos
            sql = mql                          # MQL = SQL
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

        cps_canal_cop = costo_canal_cop / sql if sql > 0 else 0.0

        resultados_canales.append(
            {
                "segmento": segmento,
                "canal": canal,
                "base": base,
                "envios": int(envios),
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

    # ------------------ USO DE CUPOS VS PPTOS ------------------ #
    st.markdown("#### Uso de cupos de envíos vs presupuesto")

    cap_rows = []
    for r in resultados_canales:
        cap_max = get_budget_envios_max(pais, periodo_ppto, segmento, r["canal"])
        envios_campania = r["envios"]

        if cap_max is None:
            cap_rows.append(
                {
                    "pais": pais,
                    "periodo": periodo_ppto,
                    "segmento": segmento,
                    "canal": r["canal"],
                    "envios_campaña": envios_campania,
                    "cupo_disponible": None,
                    "%_uso": None,
                    "envios_restantes": None,
                }
            )
        else:
            restante = max(cap_max - envios_campania, 0)
            pct = (envios_campania / cap_max * 100.0) if cap_max > 0 else 0.0

            cap_rows.append(
                {
                    "pais": pais,
                    "periodo": periodo_ppto,
                    "segmento": segmento,
                    "canal": r["canal"],
                    "envios_campaña": envios_campania,
                    "cupo_disponible": cap_max,
                    "%_uso": round(pct, 1),
                    "envios_restantes": restante,
                }
            )

            if envios_campania > cap_max:
                st.error(
                    f"⚠ El canal {r['canal']} en {pais} ({segmento}, {periodo_ppto}) "
                    f"supera el cupo de {cap_max:,} envíos (campaña: {envios_campania:,})."
                )

    if cap_rows:
        st.dataframe(pd.DataFrame(cap_rows), use_container_width=True)

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
    lines.append(f"Base: {base_label}")
    lines.append(f"Cantidad: {int(total_base):,}")
    lines.append(f"Canales: {canales_nombres}")
    lines.append(f"Cantidad de envíos: {num_envios_contacto:.0f} envío(s)")
    lines.append(f"Budget: {budget_str} {moneda_trabajo}")
    lines.append("Funnel * validado por segmentos sin nuestro ok")

    for r in resultados_canales:
        lines.append(f"{r['segmento']} – {r['canal']}:")
        lines.append(
            f"                                                              i.      Base {int(r['base'])} contactos"
        )
        lines.append(
            f"                                                            ii.      Envíos: {int(r['envios'])} {r['canal'].lower()}"
        )
        lines.append(
            f"                                                          iii.      MQLs: {int(r['mql'])}"
        )
        lines.append(
            f"                                                           iv.      SQLs: {int(r['sql'])} -> {r['nota']}"
        )
        lines.append("")

    lines.append("Costos:")
    lines.append(f"SQLs totales: {int(total_sql)}")
    lines.append(
        f"Costo total estimado: {costo_total_calc_str} {moneda_trabajo} (~{total_costo_cop:,.0f} COP)"
    )
    lines.append(f"Costo por sql: {cps_calc_str} {moneda_trabajo}")
    if cps_budget_str is not None:
        lines.append(
            f"Costo por sql (según budget {budget_str} {moneda_trabajo}): {cps_budget_str} {moneda_trabajo}"
        )

    output_text = "\n".join(lines)

    st.markdown("### Output en formato texto para copiar")
    st.text_area("Formato calculado", value=output_text, height=360)

    st.markdown("### Detalle de la campaña (por canal)")
    st.dataframe(
        pd.DataFrame(resultados_canales),
        use_container_width=True,
    )

# ------------------ PÁGINA: COPIES (SIN BASE) ------------------ #

def page_copies():
    st.header("Vista de copies (solo referencia, sin base de datos)")
    st.info(
        "Aquí puedes registrar copies y sus resultados de campañas anteriores. "
        "La información solo vive en esta sesión (no se guarda en ninguna base)."
    )

    # Inicializar con campaña histórica si NO existe o está vacía
    if "copies_df" not in st.session_state or st.session_state.copies_df.empty:
        campaña_hist = {
            "campaña": "wa_col_pos_850cop_emp_20112025_vn",
            "canal": "WhatsApp",
            "pais": "Colombia",
            "segmento": "Empresarios",
            "objetivo": (
                "Push POS $850/día fin de año – directo a SQL. "
                "Planeado: 5.000 envíos, 150 MQL/SQL (3% leads→SQL). "
                "Resultado: 4.933 usuarios, 3.996 entregados, 359 respuestas (9% resp). "
                "Creativo: video Nico."
            ),
            "copy_texto": (
                "¡Hola, {{hubspot_firstname}}! Esta temporada tu negocio puede estar "
                "*lleno… y bajo control* 🎉\n\n"
                "Con un POS desde *$850 al día* facturas electrónicamente, manejas "
                "inventario y evitas errores en caja.\n\n"
                "Por ser fin de año, te damos una asesoría GRATIS 👉\n\n"
                "Empieza aquí"
            ),
            "tasa_respuesta": 0.09,  # 9% real (359 / 3.996 aprox)
            # Puedes dejar 150 (objetivo) o 0 para que lo llenes después
            "sql_generados": 150,
            "es_ganador": True,
        }

        st.session_state.copies_df = pd.DataFrame(
            [campaña_hist],
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
            ],
        )

    # Editor interactivo
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

# ------------------ PÁGINA: SIMULACIONES ------------------ #

def page_simulaciones():
    st.header("Simulaciones de budget y objetivos")

    st.markdown("### Configuración del canal para las simulaciones")

    col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns(4)
    moneda_trabajo = col_cfg1.selectbox(
        "Moneda de trabajo",
        ["COP", "USD"],
        key="sim_moneda",
    )
    tipo_cambio = col_cfg2.number_input(
        "Tasa de cambio USD → COP",
        min_value=1.0,
        value=4000.0,
        step=50.0,
        key="sim_fx",
    )
    pais = col_cfg3.selectbox(
        "País",
        PAISES,
        key="sim_pais",
    )
    canal = col_cfg4.selectbox(
        "Canal",
        list(CHANNELS.keys()),
        key="sim_canal",
    )

    col_sms1, col_sms2 = st.columns(2)
    proveedor_sms = col_sms1.selectbox(
        "Proveedor SMS",
        ["Masive", "Nua"],
        index=0,
        key="sim_proveedor_sms",
    )

    info_default = CHANNELS[canal]
    col_r1, col_r2 = st.columns(2)
    tasa_mql = col_r1.number_input(
        "Tasa MQL (0-1, editable)",
        min_value=0.0,
        max_value=1.0,
        step=0.0001,
        value=float(info_default["tasa_mql"]),
        format="%.4f",
        key="sim_tasa_mql",
        help="Solo aplica en funnel MQL → SQL.",
    )
    tasa_sql = col_r2.number_input(
        "Tasa SQL (0-1, editable)",
        min_value=0.0,
        max_value=1.0,
        step=0.0001,
        value=float(info_default["tasa_sql"]),
        format="%.4f",
        key="sim_tasa_sql",
        help="En Directo: base→SQL. En MQL→SQL: MQL→SQL.",
    )

    tipo_funnel = st.radio(
        "Tipo de funnel",
        ["Directo a SQL", "MQL → SQL"],
        index=0,
        horizontal=True,
        key="sim_funnel",
    )

    costo_unit_cop = get_cost_cop(canal, tipo_cambio, pais, proveedor_sms)
    costo_unit_display = get_cost_display(
        canal, moneda_trabajo, tipo_cambio, pais, proveedor_sms
    )
    if moneda_trabajo == "COP":
        costo_fmt = f"{costo_unit_display:,.0f}"
    else:
        costo_fmt = f"{costo_unit_display:.4f}"
    st.info(
        f"Costo unitario estimado para {canal}: **{costo_fmt} {moneda_trabajo}** "
        f"(~{costo_unit_cop:,.0f} COP)"
    )

    st.markdown("---")

    # --------- SIMULACIÓN 1: con este budget, ¿cuántos MQL / SQL? --------- #
    st.markdown("### 1. Con este presupuesto, ¿cuántos MQL / SQL podemos alcanzar?")

    col_b1, col_b2 = st.columns(2)
    budget_sim = col_b1.number_input(
        f"Budget disponible ({moneda_trabajo})",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="sim_budget",
    )
    calc_sim1 = col_b2.button("Calcular simulación 1", key="btn_sim1")

    if calc_sim1:
        if budget_sim <= 0:
            st.warning("Ingresa un budget mayor a 0.")
        elif costo_unit_cop <= 0:
            st.warning("El costo unitario del canal es 0; no se puede simular.")
        else:
            budget_cop = (
                budget_sim * tipo_cambio if moneda_trabajo == "USD" else budget_sim
            )
            envios = math.floor(budget_cop / costo_unit_cop)
            base = envios  # asumimos 1 envío por contacto

            if envios <= 0:
                st.warning("Con ese budget no alcanzas ni un envío.")
            else:
                if tipo_funnel == "Directo a SQL":
                    mql = math.floor(base * tasa_sql)
                    sql = mql
                else:
                    mql = math.floor(base * tasa_mql)
                    sql = math.floor(mql * tasa_sql)

                if sql > 0:
                    cps_cop = budget_cop / sql
                else:
                    cps_cop = 0.0

                if moneda_trabajo == "COP":
                    budget_fmt = f"{budget_sim:,.0f}"
                    cps_fmt = f"{cps_cop:,.0f}" if sql > 0 else "N/A"
                else:
                    budget_fmt = f"{budget_sim:.2f}"
                    cps_fmt = (
                        f"{(cps_cop / tipo_cambio if tipo_cambio > 0 else 0.0):.2f}"
                        if sql > 0
                        else "N/A"
                    )

                st.write(
                    f"- Envíos posibles: **{envios:,}**\n"
                    f"- Base aproximada: **{base:,} contactos**"
                )
                st.write(
                    f"- MQL esperados: **{mql:,}**\n"
                    f"- SQL esperados: **{sql:,}**"
                )
                st.write(
                    f"- Budget usado: **{budget_fmt} {moneda_trabajo}** "
                    f"(~{budget_cop:,.0f} COP)"
                )
                st.write(
                    f"- Costo por SQL aproximado: **{cps_fmt} {moneda_trabajo}**"
                )

    st.markdown("---")

    # --------- SIMULACIÓN 2: objetivo MQL / SQL → budget necesario --------- #
    st.markdown("### 2. Tenemos que alcanzar X MQL / SQL, ¿cuánto necesitamos?")

    col_o1, col_o2, col_o3 = st.columns(3)
    mql_obj = col_o1.number_input(
        "MQL objetivo",
        min_value=0,
        value=0,
        step=10,
        key="sim_mql_obj",
    )
    sql_obj = col_o2.number_input(
        "SQL objetivo",
        min_value=0,
        value=0,
        step=10,
        key="sim_sql_obj",
    )
    calc_sim2 = col_o3.button("Calcular simulación 2", key="btn_sim2")

    if calc_sim2:
        if costo_unit_cop <= 0:
            st.warning("El costo unitario del canal es 0; no se puede simular.")
        else:
            # --- Desde SQL objetivo --- #
            if sql_obj > 0:
                if tipo_funnel == "Directo a SQL":
                    if tasa_sql <= 0:
                        st.warning(
                            "Tasa SQL = 0. No se puede calcular base para el SQL objetivo."
                        )
                    else:
                        base_needed_sql = math.ceil(sql_obj / tasa_sql)
                        envios_sql = base_needed_sql
                        budget_sql_cop = envios_sql * costo_unit_cop
                        budget_sql = (
                            budget_sql_cop
                            if moneda_trabajo == "COP"
                            else (budget_sql_cop / tipo_cambio if tipo_cambio > 0 else 0.0)
                        )
                        mql_from_sql = sql_obj  # en directo, MQL=SQL

                        if moneda_trabajo == "COP":
                            budget_sql_fmt = f"{budget_sql:,.0f}"
                        else:
                            budget_sql_fmt = f"{budget_sql:.2f}"

                        st.write(
                            f"**Para {sql_obj:,} SQL (SQL objetivo):**\n"
                            f"- Base necesaria: **{base_needed_sql:,} contactos**\n"
                            f"- Envíos estimados: **{envios_sql:,}**\n"
                            f"- MQL esperados (≈SQL): **{mql_from_sql:,}**\n"
                            f"- Budget requerido: **{budget_sql_fmt} {moneda_trabajo}** "
                            f"(~{budget_sql_cop:,.0f} COP)"
                        )
                else:
                    # MQL → SQL
                    if tasa_mql <= 0 or tasa_sql <= 0:
                        st.warning(
                            "Tasa MQL o SQL = 0. No se puede calcular base para el SQL objetivo."
                        )
                    else:
                        base_needed_sql = math.ceil(sql_obj / (tasa_mql * tasa_sql))
                        envios_sql = base_needed_sql
                        mql_from_sql = math.ceil(base_needed_sql * tasa_mql)
                        budget_sql_cop = envios_sql * costo_unit_cop
                        budget_sql = (
                            budget_sql_cop
                            if moneda_trabajo == "COP"
                            else (budget_sql_cop / tipo_cambio if tipo_cambio > 0 else 0.0)
                        )

                        if moneda_trabajo == "COP":
                            budget_sql_fmt = f"{budget_sql:,.0f}"
                        else:
                            budget_sql_fmt = f"{budget_sql:.2f}"

                        st.write(
                            f"**Para {sql_obj:,} SQL (SQL objetivo):**\n"
                            f"- Base necesaria: **{base_needed_sql:,} contactos**\n"
                            f"- Envíos estimados: **{envios_sql:,}**\n"
                            f"- MQL esperados: **{mql_from_sql:,}**\n"
                            f"- Budget requerido: **{budget_sql_fmt} {moneda_trabajo}** "
                            f"(~{budget_sql_cop:,.0f} COP)"
                        )

            # --- Desde MQL objetivo --- #
            if mql_obj > 0:
                if tipo_funnel == "Directo a SQL":
                    # En directo, MQL = SQL efectivos
                    if tasa_sql <= 0:
                        st.warning(
                            "Tasa SQL = 0. No se puede calcular base para el MQL objetivo en funnel directo."
                        )
                    else:
                        base_needed_mql = math.ceil(mql_obj / tasa_sql)
                        envios_mql = base_needed_mql
                        sql_from_mql = mql_obj
                        budget_mql_cop = envios_mql * costo_unit_cop
                        budget_mql = (
                            budget_mql_cop
                            if moneda_trabajo == "COP"
                            else (budget_mql_cop / tipo_cambio if tipo_cambio > 0 else 0.0)
                        )

                        if moneda_trabajo == "COP":
                            budget_mql_fmt = f"{budget_mql:,.0f}"
                        else:
                            budget_mql_fmt = f"{budget_mql:.2f}"

                        st.write(
                            f"**Para {mql_obj:,} MQL (en funnel directo):**\n"
                            f"- Base necesaria: **{base_needed_mql:,} contactos**\n"
                            f"- Envíos estimados: **{envios_mql:,}**\n"
                            f"- SQL esperados (≈MQL): **{sql_from_mql:,}**\n"
                            f"- Budget requerido: **{budget_mql_fmt} {moneda_trabajo}** "
                            f"(~{budget_mql_cop:,.0f} COP)"
                        )
                else:
                    # MQL → SQL
                    if tasa_mql <= 0:
                        st.warning(
                            "Tasa MQL = 0. No se puede calcular base para el MQL objetivo."
                        )
                    else:
                        base_needed_mql = math.ceil(mql_obj / tasa_mql)
                        envios_mql = base_needed_mql
                        sql_from_mql = math.floor(mql_obj * tasa_sql)
                        budget_mql_cop = envios_mql * costo_unit_cop
                        budget_mql = (
                            budget_mql_cop
                            if moneda_trabajo == "COP"
                            else (budget_mql_cop / tipo_cambio if tipo_cambio > 0 else 0.0)
                        )

                        if moneda_trabajo == "COP":
                            budget_mql_fmt = f"{budget_mql:,.0f}"
                        else:
                            budget_mql_fmt = f"{budget_mql:.2f}"

                        st.write(
                            f"**Para {mql_obj:,} MQL (en funnel MQL → SQL):**\n"
                            f"- Base necesaria: **{base_needed_mql:,} contactos**\n"
                            f"- Envíos estimados: **{envios_mql:,}**\n"
                            f"- SQL esperados: **{sql_from_mql:,}**\n"
                            f"- Budget requerido: **{budget_mql_fmt} {moneda_trabajo}** "
                            f"(~{budget_mql_cop:,.0f} COP)"
                        )

            if mql_obj == 0 and sql_obj == 0:
                st.info("Ingresa al menos un objetivo (MQL o SQL) para esta simulación.")

# ------------------ MAIN ------------------ #

def main():
    st.title("Marketing Directo – Calculadora rápida")

    page = st.sidebar.radio("Navegación", ["Calculadora", "Simulaciones", "Copies"])
    if page == "Calculadora":
        page_calculadora()
    elif page == "Simulaciones":
        page_simulaciones()
    else:
        page_copies()

if __name__ == "__main__":
    main()
