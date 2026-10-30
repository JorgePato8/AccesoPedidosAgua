"""Capa de datos dual para AguaPotableLab.

- En Render, si existe DATABASE_URL, usa PostgreSQL (Neon).
- En desarrollo local, sin DATABASE_URL, conserva SQLite/agua_potable.db.

No incluye credenciales. La URL de conexión debe configurarse como variable
secreta de entorno en Render y, para pruebas locales, en un .env no versionado.
"""
from pathlib import Path
import os
import re
import sqlite3
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "agua_potable.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_RENDER = os.getenv("RENDER", "").lower() == "true"

if IS_RENDER and not DATABASE_URL:
    raise RuntimeError(
        "Falta configurar DATABASE_URL en Render. "
        "Por seguridad, AguaPotableLab no iniciará usando SQLite temporal."
    )


class _HybridRow(dict):
    """Fila que admite acceso por nombre (row['id']) y por posición (row[0])."""
    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                key = tuple(self.keys())[key]
            except IndexError:
                raise IndexError(key) from None
        return super().__getitem__(key)


class _PostgresCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def description(self):
        return self._cursor.description

    def _convert(self, row):
        if row is None:
            return None
        names = [column.name for column in self._cursor.description]
        return _HybridRow(zip(names, row))

    def fetchone(self):
        return self._convert(self._cursor.fetchone())

    def fetchall(self):
        return [self._convert(row) for row in self._cursor.fetchall()]


class _PostgresConnection:
    """Adaptador pequeño para mantener compatible el uso actual de execute()."""
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=None):
        sql = sql.strip()
        # El código original usa marcadores SQLite '?'. Psycopg usa '%s'.
        sql = sql.replace("?", "%s")
        # Mantiene las fechas de cierre como texto ISO UTC, igual que SQLite,
        # para que el filtro de pedidos recientes siga comparando correctamente.
        sql = re.sub(
            r"\bCURRENT_TIMESTAMP\b",
            "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')",
            sql,
            flags=re.I,
        )

        is_insert = bool(re.match(r"^INSERT\s+INTO\b", sql, flags=re.I))
        if is_insert and not re.search(r"\bRETURNING\b", sql, flags=re.I):
            sql = sql.rstrip().rstrip(";") + " RETURNING id"

        cursor = self._connection.cursor()
        if params is None:
            cursor.execute(sql)
        else:
            cursor.execute(sql, params)

        inserted_id = None
        if is_insert:
            returned = cursor.fetchone()
            if returned is not None:
                inserted_id = returned[0]

        return _PostgresCursor(cursor, lastrowid=inserted_id)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_connection():
    """Devuelve conexión PostgreSQL en Render o SQLite en desarrollo local."""
    if DATABASE_URL:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "Falta instalar psycopg. Agregue 'psycopg[binary]>=3.2,<4' "
                "a requirements.txt y vuelva a desplegar."
            ) from exc

        raw = psycopg.connect(
            DATABASE_URL,
            connect_timeout=15,
            autocommit=False,
            prepare_threshold=None,
        )
        return _PostgresConnection(raw)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# Esquema original del proyecto. Solo se ajustan los tipos y defaults que
# requieren PostgreSQL; se conservan nombres, columnas y restricciones.
_POSTGRES_SCHEMA = r"""CREATE TABLE IF NOT EXISTS operadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            operador_id INTEGER,
            estado TEXT NOT NULL DEFAULT 'En proceso',

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id)
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oficina TEXT NOT NULL,
            solicitante TEXT NOT NULL,
            garrafones INTEGER NOT NULL DEFAULT 0,
            botellas INTEGER NOT NULL DEFAULT 0,
            observacion TEXT,
            fecha_solicitud TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'Pendiente'
        );
                CREATE TABLE IF NOT EXISTS controles_tratamiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            sedimentos TEXT NOT NULL
                CHECK (sedimentos IN ('Conforme', 'No conforme')),

            carbon_activado TEXT NOT NULL
                CHECK (carbon_activado IN ('Conforme', 'No conforme')),

            resina_sac TEXT NOT NULL
                CHECK (resina_sac IN ('Conforme', 'No conforme')),

            osmosis_inversa TEXT NOT NULL
                CHECK (osmosis_inversa IN ('Conforme', 'No conforme')),

            bomba TEXT NOT NULL
                CHECK (bomba IN ('Conforme', 'No conforme')),

            resultado_general TEXT NOT NULL
                CHECK (resultado_general IN ('Conforme', 'No conforme')),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_tanque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            estado_inicial TEXT NOT NULL
                CHECK (
                    estado_inicial IN (
                        'Vacío',
                        'Bajo',
                        'Medio',
                        'Alto',
                        'Lleno'
                    )
                ),

            estado_final TEXT NOT NULL
                CHECK (
                    estado_final IN (
                        'Vacío',
                        'Bajo',
                        'Medio',
                        'Alto',
                        'Lleno'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            limpieza_verificada TEXT NOT NULL
                CHECK (
                    limpieza_verificada IN (
                        'Sí',
                        'No'
                    )
                ),

            tapa TEXT NOT NULL
                CHECK (
                    tapa IN (
                        'Correcta',
                        'Incorrecta'
                    )
                ),

            condicion_general TEXT NOT NULL
                CHECK (
                    condicion_general IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_uv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            uv_encendida TEXT NOT NULL
                CHECK (
                    uv_encendida IN (
                        'Sí',
                        'No'
                    )
                ),

            indicador_funcionamiento TEXT NOT NULL
                CHECK (
                    indicador_funcionamiento IN (
                        'Normal',
                        'Alarma'
                    )
                ),

            estado_lampara TEXT NOT NULL
                CHECK (
                    estado_lampara IN (
                        'Conforme',
                        'Requiere revisión'
                    )
                ),

            estado_camisa TEXT NOT NULL
                CHECK (
                    estado_camisa IN (
                        'Conforme',
                        'Requiere limpieza'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS preparacion_garrafones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            cantidad_garrafones INTEGER NOT NULL,

            dosis_dioxido_cloro TEXT NOT NULL DEFAULT '2 gotas por garrafón',

            enjuague_1 TEXT NOT NULL
                CHECK (
                    enjuague_1 IN (
                        'Realizado',
                        'No realizado'
                    )
                ),

            enjuague_2 TEXT NOT NULL
                CHECK (
                    enjuague_2 IN (
                        'Realizado',
                        'No realizado'
                    )
                ),

            inspeccion_final TEXT NOT NULL
                CHECK (
                    inspeccion_final IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS registros_llenado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            numero_envase INTEGER NOT NULL,

            tipo_envase TEXT NOT NULL
                CHECK (
                    tipo_envase IN (
                        'Garrafón',
                        'Botella'
                    )
                ),

            volumen_nominal REAL NOT NULL
                CHECK (
                    volumen_nominal > 0
                ),

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (
                    tiempo_segundos >= 0
                ),

            fuga TEXT NOT NULL
                CHECK (
                    fuga IN (
                        'Sí',
                        'No'
                    )
                ),

            condicion_llenado TEXT NOT NULL
                CHECK (
                    condicion_llenado IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            fecha_hora_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_calidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            punto_muestreo TEXT NOT NULL
                DEFAULT 'Agua tratada para consumo',

            ph REAL,

            temperatura REAL,

            resultado_microbiologico TEXT,

            cumplimiento TEXT NOT NULL
                CHECK (
                    cumplimiento IN (
                        'Cumple',
                        'No cumple',
                        'Pendiente'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_limpieza (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            operador_id INTEGER NOT NULL,

            lote_id INTEGER,

            tipo_actividad TEXT NOT NULL
                CHECK (
                    tipo_actividad IN (
                        'Limpieza',
                        'Desinfección'
                    )
                ),

            elemento TEXT NOT NULL,

            producto_utilizado TEXT,

            dosis_cantidad TEXT,

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (tiempo_segundos >= 0),

            resultado TEXT NOT NULL
                CHECK (
                    resultado IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id),

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS mantenimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fecha_mantenimiento TEXT NOT NULL,

            fecha_registro TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            operador_id INTEGER NOT NULL,

            equipo TEXT NOT NULL,

            tipo_mantenimiento TEXT NOT NULL
                CHECK (
                    tipo_mantenimiento IN (
                        'Preventivo',
                        'Correctivo',
                        'Inspección'
                    )
                ),

            descripcion TEXT NOT NULL,

            repuestos_materiales TEXT,

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (tiempo_segundos >= 0),

            estado_final TEXT NOT NULL
                CHECK (
                    estado_final IN (
                        'Operativo',
                        'Operativo con observaciones',
                        'Fuera de servicio'
                    )
                ),

            fecha_proximo_mantenimiento TEXT,

            observaciones TEXT,

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id)
        );"""
_POSTGRES_SCHEMA = _POSTGRES_SCHEMA.replace(
    "INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY"
)
_POSTGRES_SCHEMA = re.sub(
    r"\b(lote_id|operador_id) INTEGER\b", r"\1 BIGINT", _POSTGRES_SCHEMA
)
_POSTGRES_SCHEMA = _POSTGRES_SCHEMA.replace(
    "DEFAULT CURRENT_TIMESTAMP", "DEFAULT (CURRENT_TIMESTAMP::text)"
)


def _ensure_initial_operator(connection, postgres=False):
    """Crea el primer operador solo si la tabla está vacía y se configuró su nombre."""
    nombre = os.getenv("AGUA_POTABLE_OPERADOR_INICIAL", "").strip()
    if not nombre:
        return

    count = connection.execute("SELECT COUNT(*) FROM operadores").fetchone()[0]
    if count == 0:
        placeholder = "%s" if postgres else "?"
        connection.execute(
            f"INSERT INTO operadores (nombre) VALUES ({placeholder})",
            (nombre,),
        )


def _init_postgres_db():
    import psycopg

    # Ejecutar cada CREATE TABLE en su propia instrucción.
    with psycopg.connect(DATABASE_URL, connect_timeout=15) as connection:
        for statement in _POSTGRES_SCHEMA.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)

        columnas_calidad = {
            row[0]
            for row in connection.execute(
                """SELECT column_name
                   FROM information_schema.columns
                   WHERE table_schema = current_schema()
                     AND table_name = 'controles_calidad'"""
            ).fetchall()
        }
        if "momento_muestreo" not in columnas_calidad:
            connection.execute(
                "ALTER TABLE controles_calidad ADD COLUMN momento_muestreo TEXT"
            )

        columnas_pedidos = {
            row[0]
            for row in connection.execute(
                """SELECT column_name
                   FROM information_schema.columns
                   WHERE table_schema = current_schema()
                     AND table_name = 'pedidos'"""
            ).fetchall()
        }
        if "fecha_cierre" not in columnas_pedidos:
            connection.execute(
                "ALTER TABLE pedidos ADD COLUMN fecha_cierre TEXT"
            )

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_pedidos_estado_cierre "
            "ON pedidos (estado, fecha_cierre)"
        )
        _ensure_initial_operator(connection, postgres=True)


def init_db():
    """Crea el esquema si no existe y aplica las migraciones conocidas."""
    if DATABASE_URL:
        _init_postgres_db()
        return

    connection = get_connection()
    connection.executescript(
        """CREATE TABLE IF NOT EXISTS operadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            operador_id INTEGER,
            estado TEXT NOT NULL DEFAULT 'En proceso',

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id)
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oficina TEXT NOT NULL,
            solicitante TEXT NOT NULL,
            garrafones INTEGER NOT NULL DEFAULT 0,
            botellas INTEGER NOT NULL DEFAULT 0,
            observacion TEXT,
            fecha_solicitud TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT 'Pendiente'
        );
                CREATE TABLE IF NOT EXISTS controles_tratamiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            sedimentos TEXT NOT NULL
                CHECK (sedimentos IN ('Conforme', 'No conforme')),

            carbon_activado TEXT NOT NULL
                CHECK (carbon_activado IN ('Conforme', 'No conforme')),

            resina_sac TEXT NOT NULL
                CHECK (resina_sac IN ('Conforme', 'No conforme')),

            osmosis_inversa TEXT NOT NULL
                CHECK (osmosis_inversa IN ('Conforme', 'No conforme')),

            bomba TEXT NOT NULL
                CHECK (bomba IN ('Conforme', 'No conforme')),

            resultado_general TEXT NOT NULL
                CHECK (resultado_general IN ('Conforme', 'No conforme')),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_tanque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            estado_inicial TEXT NOT NULL
                CHECK (
                    estado_inicial IN (
                        'Vacío',
                        'Bajo',
                        'Medio',
                        'Alto',
                        'Lleno'
                    )
                ),

            estado_final TEXT NOT NULL
                CHECK (
                    estado_final IN (
                        'Vacío',
                        'Bajo',
                        'Medio',
                        'Alto',
                        'Lleno'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            limpieza_verificada TEXT NOT NULL
                CHECK (
                    limpieza_verificada IN (
                        'Sí',
                        'No'
                    )
                ),

            tapa TEXT NOT NULL
                CHECK (
                    tapa IN (
                        'Correcta',
                        'Incorrecta'
                    )
                ),

            condicion_general TEXT NOT NULL
                CHECK (
                    condicion_general IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_uv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            uv_encendida TEXT NOT NULL
                CHECK (
                    uv_encendida IN (
                        'Sí',
                        'No'
                    )
                ),

            indicador_funcionamiento TEXT NOT NULL
                CHECK (
                    indicador_funcionamiento IN (
                        'Normal',
                        'Alarma'
                    )
                ),

            estado_lampara TEXT NOT NULL
                CHECK (
                    estado_lampara IN (
                        'Conforme',
                        'Requiere revisión'
                    )
                ),

            estado_camisa TEXT NOT NULL
                CHECK (
                    estado_camisa IN (
                        'Conforme',
                        'Requiere limpieza'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS preparacion_garrafones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            cantidad_garrafones INTEGER NOT NULL,

            dosis_dioxido_cloro TEXT NOT NULL DEFAULT '2 gotas por garrafón',

            enjuague_1 TEXT NOT NULL
                CHECK (
                    enjuague_1 IN (
                        'Realizado',
                        'No realizado'
                    )
                ),

            enjuague_2 TEXT NOT NULL
                CHECK (
                    enjuague_2 IN (
                        'Realizado',
                        'No realizado'
                    )
                ),

            inspeccion_final TEXT NOT NULL
                CHECK (
                    inspeccion_final IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            hora_inicio TEXT,

            hora_final TEXT,

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS registros_llenado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            numero_envase INTEGER NOT NULL,

            tipo_envase TEXT NOT NULL
                CHECK (
                    tipo_envase IN (
                        'Garrafón',
                        'Botella'
                    )
                ),

            volumen_nominal REAL NOT NULL
                CHECK (
                    volumen_nominal > 0
                ),

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (
                    tiempo_segundos >= 0
                ),

            fuga TEXT NOT NULL
                CHECK (
                    fuga IN (
                        'Sí',
                        'No'
                    )
                ),

            condicion_llenado TEXT NOT NULL
                CHECK (
                    condicion_llenado IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            fecha_hora_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_calidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lote_id INTEGER NOT NULL,

            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            punto_muestreo TEXT NOT NULL
                DEFAULT 'Agua tratada para consumo',

            ph REAL,

            temperatura REAL,

            resultado_microbiologico TEXT,

            cumplimiento TEXT NOT NULL
                CHECK (
                    cumplimiento IN (
                        'Cumple',
                        'No cumple',
                        'Pendiente'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS controles_limpieza (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            operador_id INTEGER NOT NULL,

            lote_id INTEGER,

            tipo_actividad TEXT NOT NULL
                CHECK (
                    tipo_actividad IN (
                        'Limpieza',
                        'Desinfección'
                    )
                ),

            elemento TEXT NOT NULL,

            producto_utilizado TEXT,

            dosis_cantidad TEXT,

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (tiempo_segundos >= 0),

            resultado TEXT NOT NULL
                CHECK (
                    resultado IN (
                        'Conforme',
                        'No conforme'
                    )
                ),

            observaciones TEXT,

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id),

            FOREIGN KEY (lote_id)
                REFERENCES lotes(id)
        );
                CREATE TABLE IF NOT EXISTS mantenimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fecha_mantenimiento TEXT NOT NULL,

            fecha_registro TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            operador_id INTEGER NOT NULL,

            equipo TEXT NOT NULL,

            tipo_mantenimiento TEXT NOT NULL
                CHECK (
                    tipo_mantenimiento IN (
                        'Preventivo',
                        'Correctivo',
                        'Inspección'
                    )
                ),

            descripcion TEXT NOT NULL,

            repuestos_materiales TEXT,

            hora_inicio TEXT NOT NULL,

            hora_final TEXT NOT NULL,

            tiempo_segundos INTEGER NOT NULL
                CHECK (tiempo_segundos >= 0),

            estado_final TEXT NOT NULL
                CHECK (
                    estado_final IN (
                        'Operativo',
                        'Operativo con observaciones',
                        'Fuera de servicio'
                    )
                ),

            fecha_proximo_mantenimiento TEXT,

            observaciones TEXT,

            FOREIGN KEY (operador_id)
                REFERENCES operadores(id)
        );"""
    )

    columnas_calidad = {
        fila["name"]
        for fila in connection.execute(
            "PRAGMA table_info(controles_calidad)"
        ).fetchall()
    }
    if "momento_muestreo" not in columnas_calidad:
        connection.execute(
            "ALTER TABLE controles_calidad ADD COLUMN momento_muestreo TEXT"
        )

    columnas_pedidos = {
        fila["name"]
        for fila in connection.execute(
            "PRAGMA table_info(pedidos)"
        ).fetchall()
    }
    if "fecha_cierre" not in columnas_pedidos:
        connection.execute(
            "ALTER TABLE pedidos ADD COLUMN fecha_cierre TEXT"
        )

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_pedidos_estado_cierre "
        "ON pedidos (estado, fecha_cierre)"
    )
    _ensure_initial_operator(connection, postgres=False)
    connection.commit()
    connection.close()
