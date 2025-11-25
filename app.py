import streamlit as st

st.set_page_config(page_title="Siigo - Marketing Directo", layout="centered")

st.title("🧮 Siigo – Calculadora de Marketing Directo")
st.caption("Estimación rápida de funnel y costo por SQL para pushes de marketing directo.")

st.markdown("----")

# --------- CONFIGURACIÓN GENERAL ---------
st.header("1. Datos generales de la campaña")

col1, col2 = st.columns(2)
with col1:
    base_nombre = st.text_input(
        "Base origen",
        value="MQLs abiertos de Empresarios y Contadores"
    )
with col2:
    base_total = st.number_input(
        "Cantidad total de contactos en base",
        min_value=0, value=2858, step=1
    )

col3, col4 = st.columns(2)
with col3:
    canal_nombre = st.text_input("Canal principal", value="Wapp")
with col4:
    moneda = st.text_input("Moneda (ej: USD, COP)", value="USD")

costo_unitario = st.number_input(
    f"Costo por envío ({moneda})",
    min_value=0.0, value=0.07, step=0.01, format="%.4f"
)

st.markdown("----")

# --------- SEGMENTOS ---------
st.header("2. Segmentos y funnel esperado")

st.write("Define hasta 3 segmentos (ej: Contadores, Empresarios). Puedes dejar en 0 los que no uses.")

segment_default_names = ["Contadores", "Empresarios", "Otro"]

segmentos_data = []

for i in range(3):
    st.subheader(f"Segmento {i+1}")
    with st.expander(f"Configurar segmento {i+1}", expanded=(i < 2)):
        nombre = st.text_input(
            f"Nombre segmento {i+1}",
            value=segment_default_names[i],
            key=f"seg_nombre_{i}"
        )
        col_a, col_b = st.columns(2)
        with col_a:
            base_seg = st.number_input(
                f"Base {nombre}",
                min_value=0,
                value=0 if i == 2 else (1833 if i == 0 else 1025),
                step=1,
                key=f"seg_base_{i}"
            )
        with col_b:
            envios_seg = st.number_input(
                f"Envíos {nombre}",
                min_value=0,
                value=0 if i == 2 else (1833 if i == 0 else 1025),
                step=1,
                key=f"seg_envios_{i}"
            )

        st.markdown("**Funnel esperado**")
        col_c, col_d, col_e = st.columns(3)
        with col_c:
            tasa_mql = st.number_input(
                f"% paso a MQL ({nombre})",
                min_value=0.0,
                max_value=100.0,
                value=3.5 if i == 0 else (3.5 if i == 1 else 0.0),
                step=0.1,
                key=f"seg_tasa_mql_{i}"
            )
        with col_d:
            directo_sql = st.checkbox(
                f"Reacción = SQL directo ({nombre})",
                value=True,
                key=f"seg_directo_sql_{i}"
            )
        with col_e:
            tasa_sql = st.number_input(
                f"% MQL→SQL ({nombre})",
                min_value=0.0,
                max_value=100.0,
                value=100.0 if directo_sql else 30.0,
                step=0.1,
                key=f"seg_tasa_sql_{i}"
            )

        # Cálculos por segmento (esperados)
        mqls = round(envios_seg * (tasa_mql / 100.0)) if envios_seg > 0 else 0
        sqls = round(mqls * (tasa_sql / 100.0)) if mqls > 0 else 0

        st.write(f"**MQLs esperados {nombre}:** {mqls}")
        st.write(f"**SQLs esperados {nombre}:** {sqls}")

        segmentos_data.append(
            {
                "nombre": nombre,
                "base": base_seg,
                "envios": envios_seg,
                "mqls": mqls,
                "sqls": sqls,
                "tasa_mql": tasa_mql,
                "tasa_sql": tasa_sql,
                "directo_sql": directo_sql,
            }
        )

st.markdown("----")

# --------- CÁLCULOS TOTALES ---------
st.header("3. Resumen y formato para enviar")

total_envios = sum(s["envios"] for s in segmentos_data)
total_sqls = sum(s["sqls"] for s in segmentos_data)

budget_total = total_envios * costo_unitario
costo_sql = budget_total / total_sqls if total_sqls > 0 else 0

st.subheader("Resumen numérico")
col_r1, col_r2, col_r3 = st.columns(3)
with col_r1:
    st.metric("Total envíos", value=total_envios)
with col_r2:
    st.metric("SQLs totales esperados", value=total_sqls)
with col_r3:
    st.metric(f"Costo por SQL ({moneda})", value=f"{costo_sql:,.2f}" if total_sqls > 0 else "-")

st.subheader("Formato tipo Gus")

# Construcción del texto
lineas = []

lineas.append(f"Base: {base_nombre}")
lineas.append(f"Cantidad: {base_total}")
lineas.append(f"Canales: {canal_nombre}")
lineas.append(f"Cantidad de envíos: 1 envío" if total_envios == base_total else f"Cantidad de envíos: {total_envios} envíos")
lineas.append(f"Budget: {budget_total:,.2f} {moneda}")
lineas.append("Funnel * validado por segmentos sin nuestro ok")

for seg in segmentos_data:
    if seg["envios"] <= 0:
        continue
    lineas.append(f"{seg['nombre']}:")
    lineas.append(f"                                                              i.      Base {seg['base']} contactos")
    lineas.append(f"                                                            ii.      Envíos: {seg['envios']} {canal_nombre}")
    lineas.append(f"                                                          iii.      MQLs: {seg['mqls']}")
    if seg["directo_sql"]:
        lineas.append(
            f"                                                           iv.      SQLs: {seg['sqls']} -> todos los contactos efectivos pasan a directo a comercial (paso MQL-SQL 100%)"
        )
    else:
        lineas.append(
            f"                                                           iv.      SQLs: {seg['sqls']} (paso MQL-SQL {seg['tasa_sql']:.1f}%)"
        )

lineas.append("")
lineas.append("Costos:")
lineas.append(f"SQLs totales: {total_sqls}")
if total_sqls > 0:
    lineas.append(f"Costo por sql: {costo_sql:,.2f} {moneda}")
else:
    lineas.append("Costo por sql: N/A (SQLs esperados = 0)")

formato_final = "\n".join(lineas)

st.text_area("Copia y pega este bloque en tu mail / Teams:", value=formato_final, height=350)

st.markdown("----")
st.caption("Versión 1.0 – Calculadora básica de pushes de marketing directo (Siigo).")
