from pathlib import Path
import sqlite3


# Carpeta donde está nuestro proyecto
BASE_DIR = Path(__file__).resolve().parent

# Archivo de base de datos
DB_PATH = BASE_DIR / "agua_potable.db"


def get_connection():
    """
    Crea una conexión con la base de datos SQLite.
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """
    Crea las tablas necesarias si todavía no existen.
    """
    connection = get_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS operadores (
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
        );
        """
    )

    # -------------------------------------------------
    # MIGRACIÓN: momento del muestreo de calidad
    # -------------------------------------------------

    columnas_calidad = {
        fila["name"]
        for fila in connection.execute(
            "PRAGMA table_info(controles_calidad)"
        ).fetchall()
    }

    if "momento_muestreo" not in columnas_calidad:

        connection.execute(
            """
            ALTER TABLE controles_calidad
            ADD COLUMN momento_muestreo TEXT
            """
        )

    # -------------------------------------------------
    # MIGRACIÓN: fecha y hora en que se finaliza un pedido
    # -------------------------------------------------
    # Agrega la columna sin borrar ni recrear la tabla, por lo que conserva
    # todos los pedidos existentes en la base de datos.
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

    connection.commit()
    connection.close()
    