import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from fpdf import FPDF

# --------- CONFIG GENERAL ---------
st.set_page_config(page_title="Siigo Marketing Directo Hub", layout="wide")

DB_PATH = "mkt_directo.db"
TECHO_COSTO_SQL_DEFAULT = 80000.0


# --------- CONEXIÓN Y DB ---------
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    with conn:
        # Tabla canales
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS canales (
                id_canal INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_canal TEXT NOT NULL,
                pais TEXT NOT NULL,
                costo_unitario_envio REAL NOT NULL,
                moneda TEXT NOT NULL,
                notas TEXT,
                tasa_mql_default REAL,
                tasa_sql_default REAL,
                es_sql_directo INTEGER DEFAULT 0
            )
            """
        )

        # Tabla campañas
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campanas (
                id_campana INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_campana TEXT NOT NULL,
                fecha TEXT,
                objetivo TEXT,
                origen_base TEXT,
                pais TEXT,
                segmento TEXT,
                tamano_base INTEGER,
                techo_costo_sql REAL DEFAULT 80000,
                estado TEXT DEFAULT 'Planeada'
            )
            """
        )

        # Tabla relación canales por campaña (MIX)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS canales_campana (
                id_relacion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_campana INTEGER NOT NULL,
                id_canal INTEGER NOT NULL,
                volumen_planeado INTEGER,
                volumen_real INTEGER,
                tasa_mql_esperada REAL,
                tasa_sql_esperada REAL,
                mql_esperados REAL,
                sql_esperados REAL,
                mql_reales REAL,
                sql_reales REAL,
                tasa_sql_real REAL,
                costo_total REAL,
                costo_por_sql_esperado REAL,
                costo_por_sql_real REAL,
                cumple_techo INTEGER,
                FOREIGN KEY (id_campana) REFERENCES campanas (id_campana),
                FOREIGN KEY (id_canal) REFERENCES canales (id_canal)
            )
            """
        )

        # Tabla copies
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS copies (
                id_copy INTEGER PRIMARY KEY AUTOINCREMENT,
                id_campana INTEGER,
                id_canal INTEGER,
                copy_texto TEXT,
                tipo_mensaje TEXT,
                cta TEXT,
                link_landing TEXT,
                tasa_respuesta_real REAL,
                sql_generados REAL,
                es_ganador INTEGER,
                FOREIGN KEY (id_campana) REFERENCES campanas (id_campana),
                FOREIGN KEY (id_canal) REFERENCES canales (id_canal)
            )
            """
        )

        # Precarga de canales por defecto (COL)
        cur = conn.execute("SELECT COUNT(*) AS c FROM canales")
        if cur.fetchone()["c"] == 0:
            default_canales = [
                # nombre_canal, pais, costo_unitario_envio, moneda, notas, tasa_mql_default, tasa_sql_default, es_sql_directo
                ("WhatsApp", "COL", 280.0, "COP", "WhatsApp COL - SQL directo 3%", None, 0.03, 1),
                ("SMS", "COL", 4.0, "COP", "SMS COL - MQL 0.08%", 0.0008, None, 0),
                ("Email", "COL", 12.0, "COP", "Email COL - MQL 0.15%, SQL 13.4%", 0.0015, 0.134, 0),
                ("WF Demanda", "COL", 800.0, "COP", "Workflow demanda - costo por inscrito", 0.012, 0.268, 0),
            ]
            conn.executemany(
                """
                INSERT INTO canales
                    (nombre_canal, pais, costo_unitario_envio, moneda, notas,
                     tasa_mql_default, tasa_sql_default, es_sql_directo)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                default_canales,
            )


def fetch_df(query, params=()):
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


# --------- LÓGICA DE CÁLCULOS ---------
def compute_mix_preview(mix_df, techo_costo_sql):
    """Calcula SQL esperados, costo total y CPS a partir del MIX editable."""
    if mix_df.empty:
        return 0.0, 0.0, None, mix_df

    selected = mix_df[(mix_df["usar"]) & (mix_df["volumen_planeado"] > 0)]
    if selected.empty:
        return 0.0, 0.0, None, selected

    total_sql_esperados = 0.0
    total_costo = 0.0
    rows = []

    for _, r in selected.iterrows():
        vol = r["volumen_planeado"]
        costo_unit = r["costo_unitario_envio"]
        es_sql_directo = bool(r["es_sql_directo"])
        tasa_mql = r["tasa_mql_esperada"] or 0.0
        tasa_sql = r["tasa_sql_esperada"] or 0.0

        if es_sql_directo:
            # Ej: WhatsApp SQL directo
            mql_esp = vol
            sql_esp = vol * tasa_sql
        else:
            mql_esp = vol * tasa_mql
            sql_esp = mql_esp * tasa_sql

        costo_total = vol * costo_unit
        total_sql_esperados += sql_esp
        total_costo += costo_total

        rows.append(
            {
                "nombre_canal": r["nombre_canal"],
                "volumen_planeado": vol,
                "tasa_mql_esperada": tasa_mql,
                "tasa_sql_esperada": tasa_sql,
                "mql_esperados": mql_esp,
                "sql_esperados": sql_esp,
                "costo_total": costo_total,
            }
        )

    costo_por_sql = (total_costo / total_sql_esperados) if total_sql_esperados > 0 else None
    detalle = pd.DataFrame(rows)
    return total_sql_esperados, total_costo, costo_por_sql, detalle


# --------- PÁGINA: CANALES ---------
def page_canales():
    st.header("Configuración de canales")

    df = fetch_df("SELECT * FROM canales")
    st.subheader("Canales actuales")
    st.dataframe(df, use_container_width=True)

    st.markdown("### Editar canal existente")
    if not df.empty:
        canal_labels = df.apply(
            lambda r: f"{r['id_canal']} – {r['nombre_canal']} ({r['pais']})",
            axis=1,
        )
        selected_label = st.selectbox("Selecciona un canal", canal_labels)
        selected_id = int(selected_label.split("–")[0].strip())
        row = df[df["id_canal"] == selected_id].iloc[0]

        with st.form("edit_canal"):
            nombre = st.text_input("Nombre canal", value=row["nombre_canal"])
            pais = st.text_input("País", value=row["pais"])
            costo = st.number_input(
                "Costo unitario envío",
                value=float(row["costo_unitario_envio"]),
                min_value=0.0,
                step=1.0,
            )
            moneda = st.text_input("Moneda", value=row["moneda"])
            notas = st.text_area("Notas", value=row["notas"] or "")
            tasa_mql = st.number_input(
                "Tasa MQL default (0-1)",
                value=float(row["tasa_mql_default"] or 0.0),
                min_value=0.0,
                max_value=1.0,
                step=0.0001,
                format="%.4f",
            )
            tasa_sql = st.number_input(
                "Tasa SQL default (0-1)",
                value=float(row["tasa_sql_default"] or 0.0),
                min_value=0.0,
                max_value=1.0,
                step=0.0001,
                format="%.4f",
            )
            es_sql_directo = st.checkbox(
                "SQL directo (salta MQL)", value=bool(row["es_sql_directo"])
            )
            submitted = st.form_submit_button("Guardar cambios")

            if submitted:
                conn = get_connection()
                with conn:
                    conn.execute(
                        """
                        UPDATE canales
                        SET nombre_canal=?, pais=?, costo_unitario_envio=?, moneda=?,
                            notas=?, tasa_mql_default=?, tasa_sql_default=?, es_sql_directo=?
                        WHERE id_canal=?
                        """,
                        (
                            nombre,
                            pais,
                            costo,
                            moneda,
                            notas,
                            tasa_mql,
                            tasa_sql,
                            1 if es_sql_directo else 0,
                            selected_id,
                        ),
                    )
                st.success("Canal actualizado.")

    st.markdown("### Crear nuevo canal")
    with st.form("nuevo_canal"):
        nombre = st.text_input("Nombre canal nuevo")
        pais = st.text_input("País nuevo", value="COL")
        costo = st.number_input("Costo unitario envío nuevo", min_value=0.0, step=1.0)
        moneda = st.text_input("Moneda nueva", value="COP")
        notas = st.text_area("Notas nuevas", value="")
        tasa_mql = st.number_input(
            "Tasa MQL default nueva (0-1)",
            min_value=0.0,
            max_value=1.0,
            step=0.0001,
            format="%.4f",
        )
        tasa_sql = st.number_input(
            "Tasa SQL default nueva (0-1)",
            min_value=0.0,
            max_value=1.0,
            step=0.0001,
            format="%.4f",
        )
        es_sql_directo = st.checkbox("SQL directo (salta MQL) nuevo", value=False)
        submitted = st.form_submit_button("Crear canal")

        if submitted:
            if not nombre:
                st.error("El nombre del canal es obligatorio.")
            else:
                conn = get_connection()
                with conn:
                    conn.execute(
                        """
                        INSERT INTO canales
                            (nombre_canal, pais, costo_unitario_envio, moneda, notas,
                             tasa_mql_default, tasa_sql_default, es_sql_directo)
                        VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            nombre,
                            pais,
                            costo,
                            moneda,
                            notas,
                            tasa_mql or None,
                            tasa_sql or None,
                            1 if es_sql_directo else 0,
                        ),
                    )
                st.success("Canal creado correctamente.")


# --------- PÁGINA: NUEVA CAMPAÑA ---------
def page_nueva_campana():
    st.subheader("Crear nueva campaña (push de marketing directo)")

    nombre = st.text_input("Nombre de la campaña")
    fecha = st.date_input("Fecha", value=datetime.today())
    objetivo = st.selectbox("Objetivo", ["SQL", "MQL", "Asistencia", "Reactivación"])
    origen_base = st.text_input("Origen de la base", value="MQLs abiertos")
    pais = st.selectbox("País", ["COL", "MX", "EC", "PE"])
    segmento = st.selectbox("Segmento", ["Empresarios", "Contadores"])
    tamano_base = st.number_input("Tamaño de la base", min_value=0, step=100)
    techo_costo_sql = st.number_input(
        "Techo costo SQL (COP)",
        value=TECHO_COSTO_SQL_DEFAULT,
        min_value=0.0,
        step=1000.0,
    )
    estado = st.selectbox("Estado", ["Planeada", "Enviada", "Cerrada"])

    # Tomamos canales del país (o COL por defecto)
    canales_df = fetch_df(
        "SELECT * FROM canales WHERE pais = ? OR pais = 'COL'", (pais,)
    )
    if canales_df.empty:
        st.warning(
            "No hay canales configurados para este país. Configúralos en la sección 'Canales'."
        )
        return

    st.markdown("#### MIX de canales")

    base_mix = canales_df[
        [
            "id_canal",
            "nombre_canal",
            "costo_unitario_envio",
            "tasa_mql_default",
            "tasa_sql_default",
            "es_sql_directo",
        ]
    ].copy()
    base_mix["usar"] = False
    base_mix["volumen_planeado"] = 0
    base_mix["tasa_mql_esperada"] = base_mix["tasa_mql_default"].fillna(0.0)
    base_mix["tasa_sql_esperada"] = base_mix["tasa_sql_default"].fillna(0.0)

    edited_mix = st.data_editor(
        base_mix[
            [
                "usar",
                "id_canal",
                "nombre_canal",
                "volumen_planeado",
                "costo_unitario_envio",
                "tasa_mql_esperada",
                "tasa_sql_esperada",
                "es_sql_directo",
            ]
        ],
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_config={
            "usar": st.column_config.CheckboxColumn("Usar"),
            "volumen_planeado": st.column_config.NumberColumn("Volumen planeado"),
            "tasa_mql_esperada": st.column_config.NumberColumn(
                "Tasa MQL esp.", help="Ej: 0.03 = 3%"
            ),
            "tasa_sql_esperada": st.column_config.NumberColumn(
                "Tasa SQL esp.", help="Ej: 0.30 = 30%"
            ),
        },
    )

    total_sql_esp, total_costo, costo_por_sql, detalle_mix = compute_mix_preview(
        edited_mix, techo_costo_sql
    )

    st.markdown("#### Previsión en tiempo real")
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "SQL esperados totales",
        f"{int(total_sql_esp):,}" if total_sql_esp else "0",
    )
    col2.metric("Costo total estimado", f"{int(total_costo):,} COP")

    if costo_por_sql is not None:
        col3.metric("Costo por SQL estimado", f"{int(costo_por_sql):,} COP")
        if costo_por_sql <= techo_costo_sql:
            st.success("✅ Bajo techo de costo por SQL.")
        else:
            st.error("🔴 Sobre el techo de costo por SQL.")
    else:
        col3.metric("Costo por SQL estimado", "N/A")
        st.info("Define volúmenes y tasas para ver el costo por SQL.")

    if not detalle_mix.empty:
        st.markdown("#### Detalle del MIX")
        st.dataframe(detalle_mix, use_container_width=True)

    if st.button("Guardar campaña"):
        if not nombre:
            st.error("El nombre de la campaña es obligatorio.")
            return
        if detalle_mix.empty:
            st.error("Debes seleccionar al menos un canal con volumen > 0.")
            return

        conn = get_connection()
        with conn:
            # Insert campaña
            cur = conn.execute(
                """
                INSERT INTO campanas
                    (nombre_campana, fecha, objetivo, origen_base,
                     pais, segmento, tamano_base, techo_costo_sql, estado)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    nombre,
                    fecha.isoformat(),
                    objetivo,
                    origen_base,
                    pais,
                    segmento,
                    int(tamano_base),
                    float(techo_costo_sql),
                    estado,
                ),
            )
            id_campana = cur.lastrowid

            # Insert MIX canales
            for _, r in edited_mix.iterrows():
                if not r["usar"] or r["volumen_planeado"] <= 0:
                    continue

                vol = int(r["volumen_planeado"])
                costo_unit = float(r["costo_unitario_envio"])
                es_sql_directo = bool(r["es_sql_directo"])
                tasa_mql = float(r["tasa_mql_esperada"] or 0.0)
                tasa_sql = float(r["tasa_sql_esperada"] or 0.0)

                if es_sql_directo:
                    mql_esp = vol
                    sql_esp = vol * tasa_sql
                else:
                    mql_esp = vol * tasa_mql
                    sql_esp = mql_esp * tasa_sql

                costo_total = vol * costo_unit
                costo_sql_esp = (costo_total / sql_esp) if sql_esp > 0 else None

                conn.execute(
                    """
                    INSERT INTO canales_campana
                        (id_campana, id_canal, volumen_planeado, volumen_real,
                         tasa_mql_esperada, tasa_sql_esperada,
                         mql_esperados, sql_esperados,
                         mql_reales, sql_reales, tasa_sql_real,
                         costo_total, costo_por_sql_esperado,
                         costo_por_sql_real, cumple_techo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        id_campana,
                        int(r["id_canal"]),
                        vol,
                        vol,  # asumimos envío completo inicial
                        tasa_mql if not es_sql_directo else None,
                        tasa_sql,
                        mql_esp,
                        sql_esp,
                        None,
                        None,
                        None,
                        costo_total,
                        costo_sql_esp,
                        None,
                        None,
                    ),
                )

        st.success("Campaña creada correctamente.")


# --------- RESUMEN DE CAMPAÑAS ---------
def get_resumen_campanas():
    query = """
    SELECT
        c.id_campana,
        c.nombre_campana,
        c.fecha,
        c.pais,
        c.segmento,
        c.objetivo,
        c.estado,
        c.techo_costo_sql,
        SUM(cc.sql_esperados) AS sql_esperados,
        SUM(cc.sql_reales) AS sql_reales,
        SUM(cc.costo_total) AS costo_total,
        CASE WHEN SUM(cc.sql_esperados) > 0
             THEN SUM(cc.costo_total) / SUM(cc.sql_esperados) END AS cps_esperado,
        CASE WHEN SUM(cc.sql_reales) > 0
             THEN SUM(cc.costo_total) / SUM(cc.sql_reales) END AS cps_real
    FROM campanas c
    LEFT JOIN canales_campana cc ON c.id_campana = cc.id_campana
    GROUP BY c.id_campana, c.nombre_campana, c.fecha, c.pais,
             c.segmento, c.objetivo, c.estado, c.techo_costo_sql
    ORDER BY date(c.fecha) DESC
    """
    return fetch_df(query)


def page_listado_campanas():
    st.subheader("Listado de campañas")
    df = get_resumen_campanas()
    if df.empty:
        st.info("Todavía no hay campañas.")
        return

    def semaforo(row):
        if pd.isna(row["cps_real"]):
            return "Pendiente"
        if row["cps_real"] <= row["techo_costo_sql"]:
            return "✅ OK"
        return "🔴 Sobre techo"

    df["semaforo"] = df.apply(semaforo, axis=1)

    st.dataframe(
        df[
            [
                "id_campana",
                "nombre_campana",
                "fecha",
                "pais",
                "segmento",
                "objetivo",
                "estado",
                "sql_esperados",
                "sql_reales",
                "costo_total",
                "cps_real",
                "semaforo",
            ]
        ],
        use_container_width=True,
    )


# --------- DETALLE DE CAMPAÑA + PDF ---------
def get_detalle_campana(id_campana: int):
    conn = get_connection()
    camp = conn.execute(
        "SELECT * FROM campanas WHERE id_campana = ?", (id_campana,)
    ).fetchone()

    canales = fetch_df(
        """
        SELECT
            cc.*,
            ca.nombre_canal,
            ca.costo_unitario_envio,
            ca.es_sql_directo
        FROM canales_campana cc
        JOIN canales ca ON cc.id_canal = ca.id_canal
        WHERE cc.id_campana = ?
        """,
        (id_campana,),
    )

    copies = fetch_df(
        """
        SELECT cp.*, ca.nombre_canal
        FROM copies cp
        LEFT JOIN canales ca ON cp.id_canal = ca.id_canal
        WHERE cp.id_campana = ?
        """,
        (id_campana,),
    )

    return camp, canales, copies


def build_campaign_pdf(id_campana: int):
    camp, canales, copies = get_detalle_campana(id_campana)
    if camp is None:
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Reporte de campaña", ln=1)

    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Nombre: {camp['nombre_campana']}", ln=1)
    pdf.cell(
        0,
        8,
        f"Fecha: {camp['fecha']}    País: {camp['pais']}    Segmento: {camp['segmento']}",
        ln=1,
    )
    pdf.cell(
        0,
        8,
        f"Objetivo: {camp['objetivo']}    Origen base: {camp['origen_base']}",
        ln=1,
    )
    pdf.ln(4)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "MIX de canales", ln=1)

    pdf.set_font("Arial", "", 11)
    for _, r in canales.iterrows():
        pdf.cell(
            0,
            6,
            f"- {r['nombre_canal']}: vol plan {int(r['volumen_planeado'] or 0)}, "
            f"vol real {int(r['volumen_real'] or 0)}",
            ln=1,
        )
        pdf.cell(
            0,
            6,
            f"  SQL esp: {int(r['sql_esperados'] or 0)}, "
            f"SQL reales: {int(r['sql_reales'] or 0)}",
            ln=1,
        )
        cps_real = r["costo_por_sql_real"] or 0
        pdf.cell(
            0,
            6,
            f"  Costo total: {int(r['costo_total'] or 0)}  "
            f"CPS real: {int(cps_real) if cps_real else 0}",
            ln=1,
        )

    if not copies.empty:
        pdf.ln(4)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "Copies usados", ln=1)
        pdf.set_font("Arial", "", 11)
        for _, r in copies.iterrows():
            txt = (r["copy_texto"] or "")[:200]
            pdf.multi_cell(
                0,
                6,
                f"- Canal {r['nombre_canal']} ({r['tipo_mensaje']}): {txt}",
            )

    return pdf.output(dest="S").encode("latin1")


def page_detalle_campana():
    st.subheader("Detalle de campaña")

    df = get_resumen_campanas()
    if df.empty:
        st.info("No hay campañas para mostrar.")
        return

    opciones = df.apply(
        lambda r: f"{r['id_campana']} – {r['nombre_campana']}", axis=1
    )
    selected = st.selectbox("Selecciona campaña", opciones)
    id_campana = int(selected.split("–")[0].strip())

    camp, canales, copies = get_detalle_campana(id_campana)
    if camp is None:
        st.error("Campaña no encontrada.")
        return

    st.markdown(f"### {camp['nombre_campana']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("País", camp["pais"])
    col2.metric("Segmento", camp["segmento"])
    col3.metric("Estado", camp["estado"])

    st.markdown("#### MIX de canales")
    if not canales.empty:
        st.dataframe(
            canales[
                [
                    "nombre_canal",
                    "volumen_planeado",
                    "volumen_real",
                    "mql_esperados",
                    "sql_esperados",
                    "mql_reales",
                    "sql_reales",
                    "costo_total",
                    "costo_por_sql_real",
                ]
            ],
            use_container_width=True,
        )

    st.markdown("#### Actualizar resultados reales")
    if not canales.empty:
        conn = get_connection()
        updated_values = []

        with st.form("actualizar_reales"):
            for _, r in canales.iterrows():
                st.markdown(f"**{r['nombre_canal']}**")
                vol_real = st.number_input(
                    "Volumen real (entregados)",
                    key=f"vol_real_{r['id_relacion']}",
                    value=int(
                        r["volumen_real"] or r["volumen_planeado"] or 0
                    ),
                    min_value=0,
                    step=100,
                )
                mql_real = st.number_input(
                    "MQL reales",
                    key=f"mql_real_{r['id_relacion']}",
                    value=int(r["mql_reales"] or 0),
                    min_value=0,
                    step=10,
                )
                sql_real = st.number_input(
                    "SQL reales",
                    key=f"sql_real_{r['id_relacion']}",
                    value=int(r["sql_reales"] or 0),
                    min_value=0,
                    step=5,
                )
                updated_values.append(
                    {
                        "id_relacion": int(r["id_relacion"]),
                        "id_canal": int(r["id_canal"]),
                        "volumen_real": vol_real,
                        "mql_reales": mql_real,
                        "sql_reales": sql_real,
                        "costo_unitario_envio": float(
                            r["costo_unitario_envio"]
                        ),
                        "es_sql_directo": bool(r["es_sql_directo"]),
                    }
                )

            submitted = st.form_submit_button("Guardar resultados")

        if submitted:
            with conn:
                for item in updated_values:
                    vol_real = item["volumen_real"]
                    mql_real = item["mql_reales"]
                    sql_real = item["sql_reales"]
                    costo_total = vol_real * item["costo_unitario_envio"]

                    if item["es_sql_directo"]:
                        tasa_sql_real = (
                            sql_real / vol_real if vol_real > 0 else None
                        )
                    else:
                        tasa_sql_real = (
                            sql_real / mql_real if mql_real > 0 else None
                        )

                    costo_sql_real = (
                        costo_total / sql_real if sql_real > 0 else None
                    )
                    cumple = None
                    if costo_sql_real is not None:
                        techo = camp["techo_costo_sql"]
                        cumple = 1 if costo_sql_real <= techo else 0

                    conn.execute(
                        """
                        UPDATE canales_campana
                        SET volumen_real=?, mql_reales=?, sql_reales=?,
                            tasa_sql_real=?, costo_total=?,
                            costo_por_sql_real=?, cumple_techo=?
                        WHERE id_relacion=?
                        """,
                        (
                            vol_real,
                            mql_real,
                            sql_real,
                            tasa_sql_real,
                            costo_total,
                            costo_sql_real,
                            cumple,
                            item["id_relacion"],
                        ),
                    )

            st.success("Resultados reales actualizados.")
            st.experimental_rerun()

    st.markdown("#### Copies de la campaña")
    if copies.empty:
        st.info("No hay copies guardados para esta campaña.")
    else:
        st.dataframe(
            copies[
                [
                    "nombre_canal",
                    "tipo_mensaje",
                    "cta",
                    "tasa_respuesta_real",
                    "sql_generados",
                    "es_ganador",
                    "copy_texto",
                ]
            ],
            use_container_width=True,
        )

    pdf_bytes = build_campaign_pdf(id_campana)
    if pdf_bytes:
        st.download_button(
            "Exportar reporte PDF",
            data=pdf_bytes,
            file_name=f"campana_{id_campana}.pdf",
            mime="application/pdf",
        )


def page_campanas():
    tab1, tab2, tab3 = st.tabs(["Listado", "Nueva campaña", "Detalle"])
    with tab1:
        page_listado_campanas()
    with tab2:
        page_nueva_campana()
    with tab3:
        page_detalle_campana()


# --------- DASHBOARD PRINCIPAL ---------
def page_dashboard():
    st.header("Dashboard principal")

    df = get_resumen_campanas()
    if df.empty:
        st.info("Todavía no hay datos para el dashboard.")
        return

    df["fecha"] = pd.to_datetime(df["fecha"])

    sql_por_mes = fetch_df(
        """
        SELECT substr(c.fecha, 1, 7) AS mes, SUM(cc.sql_reales) AS sql_reales
        FROM campanas c
        JOIN canales_campana cc ON c.id_campana = cc.id_campana
        GROUP BY substr(c.fecha, 1, 7)
        ORDER BY mes
        """
    )

    col1, col2, col3 = st.columns(3)
    total_sql = df["sql_reales"].sum()
    total_costo = df["costo_total"].sum()
    cps_global = (total_costo / total_sql) if total_sql > 0 else 0

    col1.metric("SQL reales totales", int(total_sql))
    col2.metric("Costo total", f"{int(total_costo):,} COP")
    col3.metric(
        "Costo por SQL global",
        f"{int(cps_global):,} COP" if cps_global else "N/A",
    )

    st.subheader("SQL generados por mes")
    if not sql_por_mes.empty:
        sql_por_mes.set_index("mes", inplace=True)
        st.bar_chart(sql_por_mes["sql_reales"])

    st.subheader("Costo total por campaña")
    st.bar_chart(df.set_index("nombre_campana")["costo_total"])

    st.subheader("Ranking de campañas por eficiencia (CPS real)")
    df_eff = df.copy()
    df_eff = df_eff[~df_eff["cps_real"].isna()].sort_values("cps_real").head(10)
    st.dataframe(
        df_eff[
            [
                "nombre_campana",
                "pais",
                "segmento",
                "sql_reales",
                "costo_total",
                "cps_real",
                "techo_costo_sql",
            ]
        ],
        use_container_width=True,
    )


# --------- LIBRERÍA DE COPIES ---------
def page_copies():
    st.header("Librería de copies")

    df = fetch_df(
        """
        SELECT
            cp.id_copy,
            cp.copy_texto,
            cp.tipo_mensaje,
            cp.cta,
            cp.link_landing,
            cp.tasa_respuesta_real,
            cp.sql_generados,
            cp.es_ganador,
            ca.nombre_campana,
            ca.pais,
            ca.segmento,
            ca.objetivo,
            cn.nombre_canal
        FROM copies cp
        LEFT JOIN campanas ca ON cp.id_campana = ca.id_campana
        LEFT JOIN canales cn ON cp.id_canal = cn.id_canal
        """
    )

    if df.empty:
        df = pd.DataFrame(
            columns=[
                "id_copy",
                "copy_texto",
                "tipo_mensaje",
                "cta",
                "link_landing",
                "tasa_respuesta_real",
                "sql_generados",
                "es_ganador",
                "nombre_campana",
                "pais",
                "segmento",
                "objetivo",
                "nombre_canal",
            ]
        )

    col1, col2, col3, col4, col5 = st.columns(5)
    canal_f = col1.selectbox(
        "Canal", ["Todos"] + sorted(df["nombre_canal"].dropna().unique().tolist())
    )
    pais_f = col2.selectbox(
        "País", ["Todos"] + sorted(df["pais"].dropna().unique().tolist())
    )
    objetivo_f = col3.selectbox(
        "Objetivo", ["Todos"] + sorted(df["objetivo"].dropna().unique().tolist())
    )
    segmento_f = col4.selectbox(
        "Segmento", ["Todos"] + sorted(df["segmento"].dropna().unique().tolist())
    )
    solo_ganadores = col5.checkbox("Solo ganadores")

    mask = pd.Series([True] * len(df))
    if canal_f != "Todos":
        mask &= df["nombre_canal"] == canal_f
    if pais_f != "Todos":
        mask &= df["pais"] == pais_f
    if objetivo_f != "Todos":
        mask &= df["objetivo"] == objetivo_f
    if segmento_f != "Todos":
        mask &= df["segmento"] == segmento_f
    if solo_ganadores:
        mask &= df["es_ganador"] == 1

    st.subheader("Listado de copies")
    st.dataframe(
        df.loc[
            mask,
            [
                "nombre_campana",
                "nombre_canal",
                "pais",
                "segmento",
                "objetivo",
                "tipo_mensaje",
                "cta",
                "tasa_respuesta_real",
                "sql_generados",
                "es_ganador",
                "copy_texto",
            ],
        ],
        use_container_width=True,
    )

    st.markdown("### Crear nuevo copy")
    conn = get_connection()
    campanas_df = fetch_df(
        "SELECT id_campana, nombre_campana FROM campanas ORDER BY fecha DESC"
    )
    canales_df = fetch_df("SELECT id_canal, nombre_canal FROM canales")

    if campanas_df.empty or canales_df.empty:
        st.info(
            "Necesitas al menos una campaña y un canal configurados para crear copies."
        )
        return

    campana_label = st.selectbox(
        "Campaña",
        campanas_df.apply(
            lambda r: f"{r['id_campana']} – {r['nombre_campana']}", axis=1
        ),
    )
    id_campana = int(campana_label.split("–")[0].strip())

    canal_label = st.selectbox(
        "Canal",
        canales_df.apply(
            lambda r: f"{r['id_canal']} – {r['nombre_canal']}", axis=1
        ),
    )
    id_canal = int(canal_label.split("–")[0].strip())

    with st.form("nuevo_copy"):
        tipo_mensaje = st.selectbox(
            "Tipo de mensaje", ["Promo", "Nutrición", "Reactivación", "Evento"]
        )
        cta = st.text_input("CTA principal")
        link_landing = st.text_input("Link landing")
        copy_texto = st.text_area("Texto completo del mensaje")
        tasa_respuesta_real = st.number_input(
            "Tasa de respuesta real (0-1)",
            min_value=0.0,
            max_value=1.0,
            step=0.0001,
            format="%.4f",
        )
        sql_generados = st.number_input(
            "SQL generados (si aplica)", min_value=0, step=1
        )
        es_ganador = st.checkbox("Es ganador")
        submitted = st.form_submit_button("Guardar copy")

        if submitted:
            with conn:
                conn.execute(
                    """
                    INSERT INTO copies
                        (id_campana, id_canal, copy_texto, tipo_mensaje,
                         cta, link_landing, tasa_respuesta_real,
                         sql_generados, es_ganador)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        id_campana,
                        id_canal,
                        copy_texto,
                        tipo_mensaje,
                        cta,
                        link_landing,
                        tasa_respuesta_real or None,
                        sql_generados or None,
                        1 if es_ganador else 0,
                    ),
                )
            st.success("Copy guardado correctamente.")


# --------- MAIN ---------
def main():
    init_db()
    st.title("Siigo Marketing Directo Hub")

    page = st.sidebar.radio(
        "Navegación",
        ("Dashboard", "Campañas", "Librería de copies", "Canales"),
    )

    if page == "Dashboard":
        page_dashboard()
    elif page == "Campañas":
        page_campanas()
    elif page == "Librería de copies":
        page_copies()
    elif page == "Canales":
        page_canales()


if __name__ == "__main__":
    main()
