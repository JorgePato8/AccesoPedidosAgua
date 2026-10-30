import io
import os
import secrets
import time

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response
)

from pydantic import BaseModel

from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse
)

from fastapi.staticfiles import StaticFiles

from fastapi.templating import Jinja2Templates

from database import init_db, get_connection


# =========================================================
# CONFIGURACIÓN DE SEGURIDAD
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

CLAVE_OPERADORES = os.getenv(
    "AGUA_POTABLE_CLAVE_OPERADORES",
    ""
).strip()

SESIONES_OPERADORES = {}

DURACION_SESION_SEGUNDOS = 8 * 60 * 60


# Áreas institucionales autorizadas para realizar pedidos.
AREAS_UNIVERSIDAD = [
    'Administracion y Finanzas',
    'Asesoria legal',
    'Comunicacion y Marketing',
    'Contabilidad',
    'Directorio Ejecutivo',
    'Gestion de Calidad y Autoevaluacion',
    'Idiomas',
    'Investigacion',
    'Postgrado',
    'Pregrado - Administracion General',
    'Pregrado - Comercio Internacional',
    'Pregrado - Comunicacion Estrategica y Digital',
    'Pregrado - Derecho',
    'Pregrado - Ing. Mec. Automotriz y Agroindustrial',
    'Pregrado - Ingenieria Comercial',
    'Pregrado - Ingenieria de Sistemas',
    'Pregrado - Ingenieria Electrica',
    'Pregrado - Ingenieria Electronica y Sistemas',
    'Pregrado - Ingenieria en Marketing y Publicidad',
    'Pregrado - Ingenieria Financiera',
    'Pregrado - Ingenieria Industrial y Comercial',
    'Pregrado - Internacionalizacion',
    'Pregrado - Psicologia',
    'Pregrado - Relaciones Internacionales Carrera',
    'Pregrado - SAE - Servicio de Atencion al Estudiante',
    'Pregrado - Vicerrectorado Academico',
    'PRESIDENCIA',
    'Rectorado',
    'Recursos Humanos (RRHH)',
    'RSU - Responsabilidad Social Universitaria',
    'Secretaria General',
    'SEGURIDAD',
    'Tecnología de la informacion',
    'Vicerrectorado',
    'Enfermería',
    'Laboratorio de mecánica',
    'Laboratorio de eléctrica',
    'Laboratorio de Ciencias básicas',
    'Laboratorio de Psicología',
    'Consultorio jurídico',
    'Publicidad',
    'Sala de docentes',
    'CPE',
    'Defensa de grado',
    'Laboratorio de electrónica',
    'Laboratorio de sistemas',

]


class ControlTratamiento(BaseModel):
    sedimentos: Literal["Conforme", "No conforme"]
    carbon_activado: Literal["Conforme", "No conforme"]
    resina_sac: Literal["Conforme", "No conforme"]
    osmosis_inversa: Literal["Conforme", "No conforme"]
    bomba: Literal["Conforme", "No conforme"]
    observaciones: str = ""

class ControlTanque(BaseModel):
    estado_inicial: Literal[
        "Vacío",
        "Bajo",
        "Medio",
        "Alto",
        "Lleno"
    ]

    estado_final: Literal[
        "Vacío",
        "Bajo",
        "Medio",
        "Alto",
        "Lleno"
    ]

    hora_inicio: str = ""
    hora_final: str = ""

    limpieza_verificada: Literal[
        "Sí",
        "No"
    ]

    tapa: Literal[
        "Correcta",
        "Incorrecta"
    ]

    condicion_general: Literal[
        "Conforme",
        "No conforme"
    ]

    observaciones: str = ""

class ControlUV(BaseModel):
    uv_encendida: Literal["Sí", "No"]
    indicador_funcionamiento: Literal["Normal", "Alarma"]
    estado_lampara: Literal["Conforme", "Requiere revisión"]
    estado_camisa: Literal["Conforme", "Requiere limpieza"]
    observaciones: str = ""

class PreparacionGarrafones(BaseModel):
    cantidad_garrafones: int

    enjuague_1: Literal[
        "Realizado",
        "No realizado"
    ]

    enjuague_2: Literal[
        "Realizado",
        "No realizado"
    ]

    inspeccion_final: Literal[
        "Conforme",
        "No conforme"
    ]

    hora_inicio: str = ""
    hora_final: str = ""

    observaciones: str = ""

class RegistroLlenado(BaseModel):
    tipo_envase: Literal[
        "Garrafón",
        "Botella"
    ]

    hora_inicio: str
    hora_final: str

    fuga: Literal[
        "Sí",
        "No"
    ]

    condicion_llenado: Literal[
        "Conforme",
        "No conforme"
    ]

    observaciones: str = ""

class ControlCalidad(BaseModel):
    ph: float | None = None

    momento_muestreo: Literal[
        "2 días después del lavado del tanque",
        "1 mes después del lavado del tanque"
    ]

    cumplimiento: Literal[
        "Cumple",
        "No cumple",
        "Pendiente"
    ]

    observaciones: str = ""

class ControlLimpieza(BaseModel):
    operador_id: int
    lote_id: int | None = None

    elemento: str

    hora_inicio: str
    hora_final: str

    resultado: Literal[
        "Conforme",
        "No conforme"
    ]

    observaciones: str = ""

class RegistroMantenimiento(BaseModel):

    operador_id: int

    fecha_mantenimiento: str

    equipo: str

    tipo_mantenimiento: Literal[
        "Preventivo",
        "Correctivo",
        "Inspección"
    ]

    descripcion: str

    repuestos_materiales: str = ""

    hora_inicio: str

    hora_final: str

    estado_final: Literal[
        "Operativo",
        "Operativo con observaciones",
        "Fuera de servicio"
    ]

    fecha_proximo_mantenimiento: str | None = None

    observaciones: str = ""

class RegistroPedido(BaseModel):

    oficina: str

    solicitante: str

    garrafones: int = 0

    botellas: int = 0

    observacion: str = ""


class ActualizacionEstadoPedido(BaseModel):

    estado: Literal[
        "Pendiente",
        "En preparación",
        "Listo para entregar",
        "Entregado",
        "Cancelado"
    ]

class AccesoOperador(BaseModel):

    operador_id: int

    clave: str

app = FastAPI(title="Agua Potable Lab")


# =========================================================
# PROTECCIÓN DE RUTAS INTERNAS
# =========================================================

RUTAS_API_PUBLICAS = {
    ("GET", "/api/operadores"),
    ("GET", "/api/areas"),
    ("POST", "/api/acceso-operador"),
    ("POST", "/api/cerrar-sesion"),
    ("POST", "/api/pedidos"),
}


@app.middleware("http")
async def proteger_accesos(request: Request, call_next):

    ruta = request.url.path
    metodo = request.method.upper()

    token = request.cookies.get(
        "agua_potable_sesion"
    )

    sesion = (
        SESIONES_OPERADORES.get(token)
        if token
        else None
    )

    if (
        sesion is not None
        and sesion["expira"] <= time.time()
    ):

        SESIONES_OPERADORES.pop(
            token,
            None
        )

        sesion = None

    autenticado = sesion is not None


    # El panel interno no se sirve sin sesión de operador.

    if ruta == "/operacion" and not autenticado:

        return RedirectResponse(
            "/",
            status_code=303
        )


    # La documentación de la API también queda restringida.

    if ruta in {
        "/docs",
        "/redoc",
        "/openapi.json"
    } and not autenticado:

        return RedirectResponse(
            "/",
            status_code=303
        )


    # Por defecto, todas las API son privadas.
    # Solo se permiten las cuatro operaciones públicas
    # enumeradas al principio.

    if ruta.startswith("/api/"):

        es_publica = (
            metodo,
            ruta
        ) in RUTAS_API_PUBLICAS

        if not es_publica and not autenticado:

            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Debe iniciar sesión como operador "
                        "para realizar esta acción."
                    )
                }
            )


    return await call_next(request)


# Inicializar la base de datos
init_db()


# Archivos estáticos
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# Plantillas HTML
templates = Jinja2Templates(directory="templates")


# =========================================================
# INICIAR SESIÓN DE OPERADOR
# =========================================================

@app.post("/api/acceso-operador")
def acceso_operador(
    datos: AccesoOperador,
    response: Response
):

    if not CLAVE_OPERADORES:

        raise HTTPException(
            status_code=503,
            detail=(
                "No se ha configurado la contraseña "
                "de operadores en el archivo .env."
            )
        )

    clave_correcta = secrets.compare_digest(
        datos.clave.encode("utf-8"),
        CLAVE_OPERADORES.encode("utf-8")
    )

    if not clave_correcta:

        raise HTTPException(
            status_code=401,
            detail="Operador o contraseña incorrectos."
        )


    connection = get_connection()

    try:

        operador = connection.execute(
            """
            SELECT id, nombre
            FROM operadores
            WHERE id = ?
              AND activo = 1
            """,
            (datos.operador_id,)
        ).fetchone()

    finally:

        connection.close()


    if operador is None:

        raise HTTPException(
            status_code=401,
            detail="Operador o contraseña incorrectos."
        )


    token = secrets.token_urlsafe(32)

    nombre = operador["nombre"]

    SESIONES_OPERADORES[token] = {
        "operador_id": operador["id"],
        "operador_nombre": nombre,
        "expira": (
            time.time()
            + DURACION_SESION_SEGUNDOS
        )
    }


    response.set_cookie(
        key="agua_potable_sesion",
        value=token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=DURACION_SESION_SEGUNDOS,
        path="/"
    )

    return {
        "mensaje": "Inicio de sesión correcto.",
        "operador_id": operador["id"],
        "operador_nombre": nombre
    }


# =========================================================
# CONSULTAR LA SESIÓN ACTUAL
# =========================================================

@app.get("/api/sesion-operador")
def consultar_sesion_operador(
    request: Request
):

    token = request.cookies.get(
        "agua_potable_sesion"
    )

    sesion = SESIONES_OPERADORES.get(token)

    if sesion is None:

        raise HTTPException(
            status_code=401,
            detail="No hay una sesión de operador activa."
        )

    return {
        "operador_id": sesion["operador_id"],
        "operador_nombre": sesion["operador_nombre"]
    }


# =========================================================
# CERRAR SESIÓN
# =========================================================

@app.post("/api/cerrar-sesion")
def cerrar_sesion_operador(
    request: Request,
    response: Response
):

    token = request.cookies.get(
        "agua_potable_sesion"
    )

    if token:

        SESIONES_OPERADORES.pop(
            token,
            None
        )

    response.delete_cookie(
        key="agua_potable_sesion",
        path="/"
    )

    return {
        "mensaje": "Sesión cerrada correctamente."
    }

# =========================================================
# PÁGINA DE INICIO Y SELECCIÓN DE ACCESO
# =========================================================

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="inicio.html",
        context={}
    )


# =========================================================
# PÁGINA PÚBLICA DE SOLICITUDES
# =========================================================

@app.get("/solicitar", response_class=HTMLResponse)
def pagina_solicitante(
    request: Request,
    response: Response
):

    # Si este navegador conservaba una sesión de operador,
    # la cerramos al entrar a la página pública.

    token = request.cookies.get(
        "agua_potable_sesion"
    )

    if token:

        SESIONES_OPERADORES.pop(
            token,
            None
        )

    response.delete_cookie(
        key="agua_potable_sesion",
        path="/"
    )

    return templates.TemplateResponse(
        request=request,
        name="solicitante.html",
        context={}
    )


# =========================================================
# PANEL INTERNO DE OPERADORES
# =========================================================

@app.get("/operacion", response_class=HTMLResponse)
def pagina_operacion(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# =========================================================
# LOTES
# =========================================================

@app.get("/api/lotes")
def obtener_lotes():

    connection = get_connection()

    filas = connection.execute(
        """
        SELECT
            lotes.id,
            lotes.codigo,
            lotes.fecha_creacion,
            lotes.estado,
            operadores.nombre AS operador
        FROM lotes
        LEFT JOIN operadores
            ON operadores.id = lotes.operador_id
        ORDER BY lotes.id DESC
        """
    ).fetchall()

    connection.close()

    return [
        {
            "id": fila["id"],
            "codigo": fila["codigo"],
            "fecha_creacion": fila["fecha_creacion"],
            "estado": fila["estado"],
            "operador": fila["operador"]
        }
        for fila in filas
    ]


# =========================================================
# CONTROL DEL TRATAMIENTO DEL AGUA
# =========================================================

@app.post("/api/lotes/{lote_id}/tratamiento")
def registrar_control_tratamiento(
    lote_id: int,
    datos: ControlTratamiento
):

    connection = get_connection()

    lote = connection.execute(
        """
        SELECT id, codigo
        FROM lotes
        WHERE id = ?
        """,
        (lote_id,)
    ).fetchone()

    if lote is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="El lote no existe."
        )

    estados = [
        datos.sedimentos,
        datos.carbon_activado,
        datos.resina_sac,
        datos.osmosis_inversa,
        datos.bomba
    ]

    resultado_general = (
        "Conforme"
        if all(estado == "Conforme" for estado in estados)
        else "No conforme"
    )

    cursor = connection.execute(
        """
        INSERT INTO controles_tratamiento (
            lote_id,
            sedimentos,
            carbon_activado,
            resina_sac,
            osmosis_inversa,
            bomba,
            resultado_general,
            observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lote_id,
            datos.sedimentos,
            datos.carbon_activado,
            datos.resina_sac,
            datos.osmosis_inversa,
            datos.bomba,
            resultado_general,
            datos.observaciones
        )
    )

    connection.commit()

    control_id = cursor.lastrowid

    connection.close()

    return {
        "id": control_id,
        "lote_id": lote_id,
        "lote": lote["codigo"],
        "resultado_general": resultado_general,
        "mensaje": "Control del tratamiento registrado correctamente."
    }

# =========================================================
# CONTROL DEL TANQUE
# =========================================================

@app.post("/api/lotes/{lote_id}/tanque")
def registrar_control_tanque(
    lote_id: int,
    datos: ControlTanque
):

    connection = get_connection()

    lote = connection.execute(
        """
        SELECT id, codigo
        FROM lotes
        WHERE id = ?
        """,
        (lote_id,)
    ).fetchone()

    if lote is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="El lote no existe."
        )

    cursor = connection.execute(
        """
        INSERT INTO controles_tanque (
            lote_id,
            estado_inicial,
            estado_final,
            hora_inicio,
            hora_final,
            limpieza_verificada,
            tapa,
            condicion_general,
            observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lote_id,
            datos.estado_inicial,
            datos.estado_final,
            datos.hora_inicio,
            datos.hora_final,
            datos.limpieza_verificada,
            datos.tapa,
            datos.condicion_general,
            datos.observaciones
        )
    )

    connection.commit()

    control_id = cursor.lastrowid

    connection.close()

    return {
        "id": control_id,
        "lote_id": lote_id,
        "lote": lote["codigo"],
        "mensaje": "Control del tanque registrado correctamente."
    }

# =========================================================
# CONTROL UV
# =========================================================

@app.post("/api/lotes/{lote_id}/uv")
def registrar_control_uv(
    lote_id: int,
    datos: ControlUV
):

    connection = get_connection()

    try:

        lote = connection.execute(
            """
            SELECT id
            FROM lotes
            WHERE id = ?
            """,
            (lote_id,)
        ).fetchone()

        if not lote:

            raise HTTPException(
                status_code=404,
                detail="El lote indicado no existe."
            )

        resultado_general = "Conforme"

        if (
            datos.uv_encendida == "No"
            or datos.indicador_funcionamiento == "Alarma"
            or datos.estado_lampara == "Requiere revisión"
            or datos.estado_camisa == "Requiere limpieza"
        ):

            resultado_general = "No conforme"

        cursor = connection.execute(
            """
            INSERT INTO controles_uv (
                lote_id,
                uv_encendida,
                indicador_funcionamiento,
                estado_lampara,
                estado_camisa,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lote_id,
                datos.uv_encendida,
                datos.indicador_funcionamiento,
                datos.estado_lampara,
                datos.estado_camisa,
                datos.observaciones.strip()
            )
        )

        connection.commit()

        registro_id = cursor.lastrowid

    finally:

        connection.close()

    return {
        "mensaje": "Control UV guardado correctamente.",
        "id": registro_id,
        "resultado_general": resultado_general
    }

# =========================================================
# PREPARACIÓN DE GARRAFONES
# =========================================================

@app.post("/api/lotes/{lote_id}/garrafones")
def registrar_preparacion_garrafones(
    lote_id: int,
    datos: PreparacionGarrafones
):

    if datos.cantidad_garrafones <= 0:

        raise HTTPException(
            status_code=400,
            detail="La cantidad de garrafones debe ser mayor que cero."
        )

    connection = get_connection()

    lote = connection.execute(
        """
        SELECT id, codigo
        FROM lotes
        WHERE id = ?
        """,
        (lote_id,)
    ).fetchone()

    if lote is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="El lote no existe."
        )

    cursor = connection.execute(
        """
        INSERT INTO preparacion_garrafones (
            lote_id,
            cantidad_garrafones,
            enjuague_1,
            enjuague_2,
            inspeccion_final,
            hora_inicio,
            hora_final,
            observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lote_id,
            datos.cantidad_garrafones,
            datos.enjuague_1,
            datos.enjuague_2,
            datos.inspeccion_final,
            datos.hora_inicio,
            datos.hora_final,
            datos.observaciones
        )
    )

    connection.commit()

    registro_id = cursor.lastrowid

    connection.close()

    return {
        "id": registro_id,
        "lote_id": lote_id,
        "lote": lote["codigo"],
        "cantidad_garrafones": datos.cantidad_garrafones,
        "mensaje": "Preparación de garrafones registrada correctamente."
    }

# =========================================================
# REGISTRO DE LLENADO
# =========================================================

@app.post("/api/lotes/{lote_id}/llenado")
def registrar_llenado(
    lote_id: int,
    datos: RegistroLlenado
):

    connection = get_connection()

    # -----------------------------------------------------
    # Verificar que el lote exista
    # -----------------------------------------------------

    lote = connection.execute(
        """
        SELECT id, codigo
        FROM lotes
        WHERE id = ?
        """,
        (lote_id,)
    ).fetchone()

    if lote is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="El lote no existe."
        )


    # -----------------------------------------------------
    # Determinar automáticamente el volumen
    # -----------------------------------------------------

    if datos.tipo_envase == "Garrafón":

        volumen_nominal = 20.0

    else:

        volumen_nominal = 0.6


    # -----------------------------------------------------
    # Convertir las horas a tiempo
    # -----------------------------------------------------

    try:

        hora_inicio = datetime.strptime(
            datos.hora_inicio,
            "%H:%M:%S"
        )

        hora_final = datetime.strptime(
            datos.hora_final,
            "%H:%M:%S"
        )

    except ValueError:

        connection.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Las horas deben tener el formato "
                "HH:MM:SS."
            )
        )


    # -----------------------------------------------------
    # Calcular tiempo de llenado
    # -----------------------------------------------------

    tiempo_segundos = (
        hora_final - hora_inicio
    ).total_seconds()


    if tiempo_segundos < 0:

        connection.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "La hora final no puede ser "
                "anterior a la hora de inicio."
            )
        )


    tiempo_segundos = int(
        tiempo_segundos
    )


    # -----------------------------------------------------
    # Obtener el número consecutivo del envase
    # -----------------------------------------------------

    ultimo_envase = connection.execute(
        """
        SELECT MAX(numero_envase) AS ultimo
        FROM registros_llenado
        WHERE lote_id = ?
        """,
        (lote_id,)
    ).fetchone()


    if ultimo_envase["ultimo"] is None:

        numero_envase = 1

    else:

        numero_envase = (
            ultimo_envase["ultimo"] + 1
        )


    # -----------------------------------------------------
    # Guardar registro
    # -----------------------------------------------------

    cursor = connection.execute(
        """
        INSERT INTO registros_llenado (
            lote_id,
            numero_envase,
            tipo_envase,
            volumen_nominal,
            hora_inicio,
            hora_final,
            tiempo_segundos,
            fuga,
            condicion_llenado,
            observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lote_id,
            numero_envase,
            datos.tipo_envase,
            volumen_nominal,
            datos.hora_inicio,
            datos.hora_final,
            tiempo_segundos,
            datos.fuga,
            datos.condicion_llenado,
            datos.observaciones
        )
    )


    connection.commit()

    registro_id = cursor.lastrowid

    connection.close()


    # -----------------------------------------------------
    # Respuesta
    # -----------------------------------------------------

    return {
        "id": registro_id,
        "lote_id": lote_id,
        "lote": lote["codigo"],
        "numero_envase": numero_envase,
        "tipo_envase": datos.tipo_envase,
        "volumen_nominal": volumen_nominal,
        "hora_inicio": datos.hora_inicio,
        "hora_final": datos.hora_final,
        "tiempo_segundos": tiempo_segundos,
        "fuga": datos.fuga,
        "condicion_llenado": datos.condicion_llenado,
        "mensaje": "Registro de llenado guardado correctamente."
    }

# =========================================================
# CONTROL DE CALIDAD
# =========================================================

@app.post("/api/lotes/{lote_id}/calidad")
def registrar_control_calidad(
    lote_id: int,
    datos: ControlCalidad
):

    if datos.ph is not None:

        if datos.ph < 0 or datos.ph > 14:

            raise HTTPException(
                status_code=400,
                detail="El valor de pH debe estar entre 0 y 14."
            )

    connection = get_connection()

    try:

        lote = connection.execute(
            """
            SELECT id
            FROM lotes
            WHERE id = ?
            """,
            (lote_id,)
        ).fetchone()

        if not lote:

            raise HTTPException(
                status_code=404,
                detail="El lote indicado no existe."
            )

        cursor = connection.execute(
            """
            INSERT INTO controles_calidad (
                lote_id,
                punto_muestreo,
                momento_muestreo,
                ph,
                cumplimiento,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lote_id,
                "Agua tratada para consumo",
                datos.momento_muestreo,
                datos.ph,
                datos.cumplimiento,
                datos.observaciones.strip()
            )
        )

        connection.commit()

        registro_id = cursor.lastrowid

    finally:

        connection.close()

    return {
        "mensaje": "Control de calidad guardado correctamente.",
        "id": registro_id
    }

@app.post("/api/limpieza")
def registrar_limpieza(
    datos: ControlLimpieza
):

    if not datos.elemento.strip():

        raise HTTPException(
            status_code=400,
            detail="Debe indicar el elemento intervenido."
        )

    if not datos.hora_inicio:

        raise HTTPException(
            status_code=400,
            detail="Debe registrar la hora de inicio."
        )

    if not datos.hora_final:

        raise HTTPException(
            status_code=400,
            detail="Debe registrar la hora final."
        )

    try:

        inicio = datetime.strptime(
            datos.hora_inicio,
            "%H:%M:%S"
        )

        final = datetime.strptime(
            datos.hora_final,
            "%H:%M:%S"
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Las horas deben tener formato HH:MM:SS."
        )

    tiempo_segundos = int(
        (final - inicio).total_seconds()
    )

    if tiempo_segundos < 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "La hora final no puede ser anterior "
                "a la hora de inicio."
            )
        )

    connection = get_connection()

    try:

        operador = connection.execute(
            """
            SELECT id
            FROM operadores
            WHERE id = ?
              AND activo = 1
            """,
            (datos.operador_id,)
        ).fetchone()

        if not operador:

            raise HTTPException(
                status_code=400,
                detail=(
                    "El operador seleccionado "
                    "no existe o está inactivo."
                )
            )

        if datos.lote_id is not None:

            lote = connection.execute(
                """
                SELECT id
                FROM lotes
                WHERE id = ?
                """,
                (datos.lote_id,)
            ).fetchone()

            if not lote:

                raise HTTPException(
                    status_code=400,
                    detail="El lote indicado no existe."
                )

        cursor = connection.execute(
            """
            INSERT INTO controles_limpieza (
                operador_id,
                lote_id,
                tipo_actividad,
                elemento,
                producto_utilizado,
                dosis_cantidad,
                hora_inicio,
                hora_final,
                tiempo_segundos,
                resultado,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datos.operador_id,
                datos.lote_id,
                "Limpieza",
                datos.elemento.strip(),
                "",
                "",
                datos.hora_inicio,
                datos.hora_final,
                tiempo_segundos,
                datos.resultado,
                datos.observaciones.strip()
            )
        )

        connection.commit()

        registro_id = cursor.lastrowid

    finally:

        connection.close()

    return {
        "mensaje": "Registro de limpieza guardado correctamente.",
        "id": registro_id,
        "tiempo_segundos": tiempo_segundos
    }

# =========================================================
# MANTENIMIENTO
# =========================================================

def parsear_hora_mantenimiento(
    valor: str,
    campo: str
):
    for formato in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            pass

    raise HTTPException(
        status_code=400,
        detail=(
            f"La {campo} debe tener el formato "
            "HH:MM o HH:MM:SS."
        )
    )


@app.post("/api/mantenimientos")
def registrar_mantenimiento(
    datos: RegistroMantenimiento
):

    fecha = datos.fecha_mantenimiento.strip()

    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="La fecha del mantenimiento no es válida."
        )

    equipo = datos.equipo.strip()
    descripcion = datos.descripcion.strip()

    if not equipo:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar el equipo intervenido."
        )

    if not descripcion:
        raise HTTPException(
            status_code=400,
            detail="Debe describir el trabajo realizado."
        )

    fecha_proximo = (
        datos.fecha_proximo_mantenimiento or ""
    ).strip() or None

    if fecha_proximo:

        try:
            datetime.strptime(
                fecha_proximo,
                "%Y-%m-%d"
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "La fecha del próximo mantenimiento "
                    "no es válida."
                )
            )

        if fecha_proximo < fecha:
            raise HTTPException(
                status_code=400,
                detail=(
                    "La fecha del próximo mantenimiento "
                    "no puede ser anterior a la fecha "
                    "de la intervención registrada."
                )
            )

    inicio = parsear_hora_mantenimiento(
        datos.hora_inicio,
        "hora de inicio"
    )

    final = parsear_hora_mantenimiento(
        datos.hora_final,
        "hora de finalización"
    )

    inicio = inicio.replace(
        year=2000,
        month=1,
        day=1
    )

    final = final.replace(
        year=2000,
        month=1,
        day=1
    )

    segundos_inicio = (
        inicio.hour * 3600
        + inicio.minute * 60
        + inicio.second
    )

    segundos_final = (
        final.hour * 3600
        + final.minute * 60
        + final.second
    )

    tiempo_segundos = (
        segundos_final - segundos_inicio
    )

    # Permite una intervención que termine después
    # de la medianoche.
    if tiempo_segundos < 0:
        tiempo_segundos += 24 * 60 * 60

    connection = get_connection()

    operador = connection.execute(
        """
        SELECT id
        FROM operadores
        WHERE id = ? AND activo = 1
        """,
        (datos.operador_id,)
    ).fetchone()

    if operador is None:
        connection.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "El operador seleccionado no existe "
                "o se encuentra inactivo."
            )
        )

    cursor = connection.execute(
        """
        INSERT INTO mantenimientos (
            fecha_mantenimiento,
            operador_id,
            equipo,
            tipo_mantenimiento,
            descripcion,
            repuestos_materiales,
            hora_inicio,
            hora_final,
            tiempo_segundos,
            estado_final,
            fecha_proximo_mantenimiento,
            observaciones
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fecha,
            datos.operador_id,
            equipo,
            datos.tipo_mantenimiento,
            descripcion,
            datos.repuestos_materiales.strip(),
            inicio.strftime("%H:%M:%S"),
            final.strftime("%H:%M:%S"),
            tiempo_segundos,
            datos.estado_final,
            fecha_proximo,
            datos.observaciones.strip()
        )
    )

    connection.commit()

    registro_id = cursor.lastrowid

    connection.close()

    return {
        "mensaje": (
            "Mantenimiento registrado correctamente."
        ),
        "id": registro_id,
        "tiempo_segundos": tiempo_segundos
    }


@app.get("/api/mantenimientos")
def obtener_mantenimientos():

    connection = get_connection()

    hoy = datetime.now().date()
    fecha_hoy = hoy.isoformat()
    fecha_limite = (hoy + timedelta(days=30)).isoformat()

    filas = connection.execute(
        """
        SELECT
            m.id,
            m.fecha_mantenimiento,
            m.fecha_registro,
            m.equipo,
            m.tipo_mantenimiento,
            m.descripcion,
            m.repuestos_materiales,
            m.hora_inicio,
            m.hora_final,
            m.tiempo_segundos,
            m.estado_final,
            m.fecha_proximo_mantenimiento,
            m.observaciones,
            o.nombre AS operador_nombre,

            CASE
                WHEN m.fecha_proximo_mantenimiento IS NULL
                     OR TRIM(m.fecha_proximo_mantenimiento) = ''
                THEN 'Sin programar'
                WHEN m.fecha_proximo_mantenimiento < ?
                THEN 'Vencido'
                WHEN m.fecha_proximo_mantenimiento <= ?
                THEN 'Próximo'
                ELSE 'Programado'
            END AS estado_programacion

        FROM mantenimientos m
        INNER JOIN operadores o ON o.id = m.operador_id
        ORDER BY m.fecha_mantenimiento DESC, m.id DESC
        """,
        (fecha_hoy, fecha_limite)
    ).fetchall()

    connection.close()

    return [
        dict(fila)
        for fila in filas
    ]


# =========================================================
# PEDIDOS
# =========================================================


@app.get("/api/areas")
def obtener_areas_universidad():
    """Devuelve la lista fija de áreas permitidas para las solicitudes."""
    return AREAS_UNIVERSIDAD


@app.post("/api/pedidos")
def crear_pedido(datos: RegistroPedido):

    oficina = datos.oficina.strip()
    solicitante = datos.solicitante.strip()
    observacion = datos.observacion.strip()

    if not oficina:
        raise HTTPException(
            status_code=400,
            detail="Debe seleccionar el área solicitante."
        )

    # Validación en el servidor: no se aceptan áreas escritas libremente
    # ni valores que no estén incluidos en la lista institucional.
    if oficina not in AREAS_UNIVERSIDAD:
        raise HTTPException(
            status_code=400,
            detail="Seleccione un área válida de la lista."
        )

    if not solicitante:
        raise HTTPException(
            status_code=400,
            detail="Debe indicar el nombre del solicitante."
        )

    if datos.garrafones < 0 or datos.botellas < 0:
        raise HTTPException(
            status_code=400,
            detail="Las cantidades no pueden ser negativas."
        )

    if datos.garrafones == 0 and datos.botellas == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Debe solicitar al menos un bidón de 20 L "
                "o una botella de 600 mL."
            )
        )

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            INSERT INTO pedidos (
                oficina,
                solicitante,
                garrafones,
                botellas,
                observacion
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                oficina,
                solicitante,
                datos.garrafones,
                datos.botellas,
                observacion
            )
        )

        connection.commit()

        pedido_id = cursor.lastrowid

    finally:
        connection.close()

    return {
        "id": pedido_id,
        "oficina": oficina,
        "solicitante": solicitante,
        "garrafones": datos.garrafones,
        "botellas": datos.botellas,
        "estado": "Pendiente",
        "mensaje": "Solicitud registrada correctamente."
    }


@app.get("/api/pedidos")
def obtener_pedidos():

    connection = get_connection()

    try:

        # En la tabla principal solo se muestran los pedidos activos y los
        # finalizados durante las últimas dos horas. Los registros permanecen
        # guardados en la base de datos; únicamente se ocultan de esta consulta.
        filas = connection.execute(
            """
            SELECT
                id,
                oficina,
                solicitante,
                garrafones,
                botellas,
                observacion,
                fecha_solicitud,
                estado,
                fecha_cierre
            FROM pedidos
            WHERE
                estado NOT IN ('Entregado', 'Cancelado')
                OR (
                    estado IN ('Entregado', 'Cancelado')
                    AND fecha_cierre IS NOT NULL
                    AND fecha_cierre >= ?
                )
            ORDER BY id DESC
            """,
            ((datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),)
        ).fetchall()

        return [
            dict(fila)
            for fila in filas
        ]

    finally:
        connection.close()


@app.patch("/api/pedidos/{pedido_id}/estado")
def actualizar_estado_pedido(
    pedido_id: int,
    datos: ActualizacionEstadoPedido
):

    connection = get_connection()

    try:

        pedido = connection.execute(
            """
            SELECT id, estado, fecha_cierre
            FROM pedidos
            WHERE id = ?
            """,
            (pedido_id,)
        ).fetchone()

        if pedido is None:
            raise HTTPException(
                status_code=404,
                detail="El pedido indicado no existe."
            )

        connection.execute(
            """
            UPDATE pedidos
            SET
                estado = ?,
                fecha_cierre = CASE
                    WHEN ? IN ('Entregado', 'Cancelado') THEN
                        CASE
                            WHEN estado != ? OR fecha_cierre IS NULL
                            THEN CURRENT_TIMESTAMP
                            ELSE fecha_cierre
                        END
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (
                datos.estado,
                datos.estado,
                datos.estado,
                pedido_id
            )
        )

        connection.commit()

        return {
            "id": pedido_id,
            "estado": datos.estado,
            "mensaje": "Estado del pedido actualizado correctamente."
        }

    finally:
        connection.close()

# =========================================================
# OPERADORES
# =========================================================

@app.get("/api/operadores")
def obtener_operadores():

    connection = get_connection()

    filas = connection.execute(
        """
        SELECT id, nombre
        FROM operadores
        WHERE activo = 1
        ORDER BY nombre
        """
    ).fetchall()

    connection.close()

    return [
        {
            "id": fila["id"],
            "nombre": fila["nombre"]
        }
        for fila in filas
    ]


@app.post("/api/operadores")
def crear_operador(datos: dict):

    nombre = datos.get("nombre", "").strip()

    if not nombre:
        raise HTTPException(
            status_code=400,
            detail="El nombre del operador es obligatorio."
        )

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO operadores (nombre)
        VALUES (?)
        """,
        (nombre,)
    )

    connection.commit()

    operador_id = cursor.lastrowid

    connection.close()

    return {
        "id": operador_id,
        "nombre": nombre
    }


# =========================================================
# CREAR LOTE
# =========================================================

@app.post("/api/lotes")
def crear_lote(datos: dict):

    operador_id = datos.get("operador_id")

    if not operador_id:
        raise HTTPException(
            status_code=400,
            detail="Debe seleccionar un operador."
        )

    connection = get_connection()

    operador = connection.execute(
        """
        SELECT id, nombre
        FROM operadores
        WHERE id = ? AND activo = 1
        """,
        (operador_id,)
    ).fetchone()

    if operador is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="El operador seleccionado no existe."
        )

    fecha = datetime.now()

    prefijo = fecha.strftime("%Y%m%d")

    cantidad_hoy = connection.execute(
        """
        SELECT COUNT(*)
        FROM lotes
        WHERE codigo LIKE ?
        """,
        (f"{prefijo}-%",)
    ).fetchone()[0]

    consecutivo = cantidad_hoy + 1

    codigo = f"{prefijo}-{consecutivo:03d}"

    cursor = connection.execute(
        """
        INSERT INTO lotes
        (
            codigo,
            operador_id,
            estado
        )
        VALUES (?, ?, ?)
        """,
        (
            codigo,
            operador_id,
            "En proceso"
        )
    )

    connection.commit()

    lote_id = cursor.lastrowid

    connection.close()

    return {
        "id": lote_id,
        "codigo": codigo,
        "operador": operador["nombre"],
        "estado": "En proceso"
    }
# =========================================================
# EXPORTACIÓN DE REGISTROS A EXCEL
# =========================================================

@app.get("/api/exportar-excel")
def exportar_excel():
    """Genera un libro Excel con los registros completos de la base de datos.

    Esta ruta es privada: el middleware exige una sesión de operador.
    La exportación solo lee información y no modifica los registros.
    """
    try:
        import xlsxwriter
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Falta instalar XlsxWriter. Active el entorno virtual y ejecute: "
                "python -m pip install XlsxWriter"
            )
        )

    consultas = [
        (
            "Pedidos",
            """
            SELECT
                id AS 'N.º de pedido',
                oficina AS 'Área',
                solicitante AS 'Solicitante',
                garrafones AS 'Bidones (20 L)',
                botellas AS 'Botellas (600 mL)',
                observacion AS 'Observaciones',
                fecha_solicitud AS 'Fecha de solicitud',
                estado AS 'Estado',
                fecha_cierre AS 'Fecha de cierre'
            FROM pedidos
            ORDER BY id DESC
            """
        ),
        (
            "Lotes",
            """
            SELECT
                l.id AS 'ID de lote',
                l.codigo AS 'Código de lote',
                l.fecha_creacion AS 'Fecha de creación',
                o.nombre AS 'Operador responsable',
                l.estado AS 'Estado'
            FROM lotes l
            LEFT JOIN operadores o ON o.id = l.operador_id
            ORDER BY l.id DESC
            """
        ),
        (
            "Operadores",
            """
            SELECT
                id AS 'ID de operador',
                nombre AS 'Nombre',
                CASE WHEN activo = 1 THEN 'Activo' ELSE 'Inactivo' END AS 'Estado'
            FROM operadores
            ORDER BY nombre
            """
        ),
        (
            "Tratamiento",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora AS 'Fecha y hora',
                o.nombre AS 'Operador responsable',
                c.sedimentos AS 'Filtro de sedimentos',
                c.carbon_activado AS 'Carbón activado',
                c.resina_sac AS 'Resina catiónica SAC',
                c.osmosis_inversa AS 'Ósmosis inversa',
                c.bomba AS 'Bomba',
                c.resultado_general AS 'Resultado general',
                c.observaciones AS 'Observaciones'
            FROM controles_tratamiento c
            INNER JOIN lotes l ON l.id = c.lote_id
            LEFT JOIN operadores o ON o.id = l.operador_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Tanque",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora AS 'Fecha y hora',
                c.estado_inicial AS 'Nivel inicial',
                c.estado_final AS 'Nivel final',
                c.hora_inicio AS 'Hora de inicio',
                c.hora_final AS 'Hora final',
                c.limpieza_verificada AS 'Limpieza verificada',
                c.tapa AS 'Condición de la tapa',
                c.condicion_general AS 'Condición general',
                c.observaciones AS 'Observaciones'
            FROM controles_tanque c
            INNER JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Control UV",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora AS 'Fecha y hora',
                c.uv_encendida AS 'Unidad UV encendida',
                c.indicador_funcionamiento AS 'Indicador',
                c.estado_lampara AS 'Estado de lámpara',
                c.estado_camisa AS 'Estado de camisa de cuarzo',
                c.observaciones AS 'Observaciones'
            FROM controles_uv c
            INNER JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Preparación envases",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora AS 'Fecha y hora',
                c.cantidad_garrafones AS 'Bidones preparados (20 L)',
                c.dosis_dioxido_cloro AS 'Dosis de desinfectante registrada',
                c.enjuague_1 AS 'Primer enjuague',
                c.enjuague_2 AS 'Segundo enjuague',
                c.inspeccion_final AS 'Inspección final',
                c.hora_inicio AS 'Hora de inicio',
                c.hora_final AS 'Hora final',
                c.observaciones AS 'Observaciones'
            FROM preparacion_garrafones c
            INNER JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Llenado",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora_registro AS 'Fecha y hora de registro',
                c.numero_envase AS 'Número de envase',
                CASE
                    WHEN c.tipo_envase = 'Garrafón' THEN 'Bidón (20 L)'
                    ELSE 'Botella (600 mL)'
                END AS 'Tipo de envase',
                c.volumen_nominal AS 'Volumen nominal (L)',
                c.hora_inicio AS 'Hora de inicio',
                c.hora_final AS 'Hora final',
                c.tiempo_segundos AS 'Tiempo (segundos)',
                c.fuga AS '¿Se presentó fuga?',
                c.condicion_llenado AS 'Condición del llenado',
                c.observaciones AS 'Observaciones'
            FROM registros_llenado c
            INNER JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Calidad",
            """
            SELECT
                c.id AS 'ID de registro',
                l.codigo AS 'Lote',
                c.fecha_hora AS 'Fecha y hora',
                c.punto_muestreo AS 'Punto de muestreo',
                c.momento_muestreo AS 'Momento del muestreo',
                c.ph AS 'pH',
                c.temperatura AS 'Temperatura (°C)',
                c.resultado_microbiologico AS 'Resultado microbiológico',
                c.cumplimiento AS 'Cumplimiento',
                c.observaciones AS 'Observaciones'
            FROM controles_calidad c
            INNER JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Limpieza",
            """
            SELECT
                c.id AS 'ID de registro',
                c.fecha_hora AS 'Fecha y hora',
                o.nombre AS 'Operador',
                l.codigo AS 'Lote',
                c.tipo_actividad AS 'Tipo de actividad',
                c.elemento AS 'Elemento intervenido',
                c.producto_utilizado AS 'Producto utilizado',
                c.dosis_cantidad AS 'Dosis o cantidad',
                c.hora_inicio AS 'Hora de inicio',
                c.hora_final AS 'Hora final',
                c.tiempo_segundos AS 'Tiempo (segundos)',
                c.resultado AS 'Resultado',
                c.observaciones AS 'Observaciones'
            FROM controles_limpieza c
            INNER JOIN operadores o ON o.id = c.operador_id
            LEFT JOIN lotes l ON l.id = c.lote_id
            ORDER BY c.id DESC
            """
        ),
        (
            "Mantenimiento",
            """
            SELECT
                m.id AS 'ID de registro',
                m.fecha_mantenimiento AS 'Fecha de mantenimiento',
                m.fecha_registro AS 'Fecha de registro',
                o.nombre AS 'Operador responsable',
                m.equipo AS 'Equipo o elemento',
                m.tipo_mantenimiento AS 'Tipo de intervención',
                m.descripcion AS 'Trabajo realizado',
                m.repuestos_materiales AS 'Repuestos y materiales',
                m.hora_inicio AS 'Hora de inicio',
                m.hora_final AS 'Hora final',
                m.tiempo_segundos AS 'Tiempo (segundos)',
                m.estado_final AS 'Estado final del equipo',
                m.fecha_proximo_mantenimiento AS 'Próximo mantenimiento',
                m.observaciones AS 'Observaciones'
            FROM mantenimientos m
            INNER JOIN operadores o ON o.id = m.operador_id
            ORDER BY m.fecha_mantenimiento DESC, m.id DESC
            """
        ),
    ]

    datos_hojas = {}
    connection = get_connection()
    try:
        for nombre_hoja, consulta in consultas:
            cursor = connection.execute(consulta)
            encabezados = [columna.name if hasattr(columna, "name") else columna[0] for columna in cursor.description]
            filas = [tuple(fila.values()) if hasattr(fila, "values") else tuple(fila) for fila in cursor.fetchall()]
            datos_hojas[nombre_hoja] = (encabezados, filas)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "No se pudo preparar la exportación. "
                "Revise que la base de datos esté actualizada. "
                f"Detalle: {error}"
            )
        )
    finally:
        connection.close()

    salida = io.BytesIO()
    libro = xlsxwriter.Workbook(
        salida,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        }
    )

    formato_titulo = libro.add_format({
        "bold": True,
        "font_size": 16,
        "font_color": "#FFFFFF",
        "bg_color": "#174A63",
        "align": "left",
        "valign": "vcenter",
    })
    formato_subtitulo = libro.add_format({
        "font_color": "#405466",
        "italic": True,
        "text_wrap": True,
        "valign": "top",
    })
    formato_encabezado = libro.add_format({
        "bold": True,
        "font_color": "#FFFFFF",
        "bg_color": "#1E647E",
        "border": 1,
        "text_wrap": True,
        "valign": "vcenter",
    })
    formato_celda = libro.add_format({
        "border": 1,
        "border_color": "#D9E2E8",
        "valign": "top",
        "text_wrap": True,
    })
    formato_numero = libro.add_format({
        "border": 1,
        "border_color": "#D9E2E8",
        "valign": "top",
        "num_format": "0.00",
    })
    formato_metrica = libro.add_format({
        "bold": True,
        "bg_color": "#E9F1F5",
        "border": 1,
        "border_color": "#D9E2E8",
        "text_wrap": True,
    })

    resumen = libro.add_worksheet("Resumen")
    resumen.hide_gridlines(2)
    resumen.set_column("A:A", 34)
    resumen.set_column("B:B", 24)
    resumen.set_column("C:C", 75)
    resumen.merge_range("A1:C1", "AGUA FILTRADA | LABORATORIO DE PROCESOS INDUSTRIALES", formato_titulo)
    resumen.set_row(0, 30)
    resumen.merge_range(
        "A2:C2",
        "Exportación de registros guardados en AguaPotableLab. Cada hoja contiene todos los registros del módulo, incluidos los pedidos finalizados que ya no aparecen en la tabla principal.",
        formato_subtitulo,
    )
    resumen.set_row(1, 42)
    resumen.write("A4", "Fecha y hora de exportación", formato_metrica)
    resumen.write("B4", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), formato_celda)
    resumen.write("A6", "Indicador", formato_encabezado)
    resumen.write("B6", "Cantidad", formato_encabezado)
    resumen.write("C6", "Descripción", formato_encabezado)

    filas_pedidos = datos_hojas["Pedidos"][1]
    pedidos_estado = [str(fila[7] or "") for fila in filas_pedidos]
    indicadores = [
        ("Pedidos registrados", len(filas_pedidos), "Todos los pedidos guardados."),
        ("Pedidos activos", sum(estado not in ("Entregado", "Cancelado") for estado in pedidos_estado), "No están entregados ni cancelados."),
        ("Pedidos entregados", pedidos_estado.count("Entregado"), "Incluye los que ya no aparecen en la tabla principal."),
        ("Pedidos cancelados", pedidos_estado.count("Cancelado"), "Incluye los que ya no aparecen en la tabla principal."),
        ("Lotes", len(datos_hojas["Lotes"][1]), "Lotes registrados en el sistema."),
        ("Controles de tratamiento", len(datos_hojas["Tratamiento"][1]), "Registros del tratamiento del agua."),
        ("Controles del tanque", len(datos_hojas["Tanque"][1]), "Registros del tanque de almacenamiento."),
        ("Controles UV", len(datos_hojas["Control UV"][1]), "Registros de inspección de la unidad UV."),
        ("Preparaciones de envases", len(datos_hojas["Preparación envases"][1]), "Registros de preparación y enjuague de envases."),
        ("Registros de llenado", len(datos_hojas["Llenado"][1]), "Registros individuales de llenado."),
        ("Controles de calidad", len(datos_hojas["Calidad"][1]), "Registros de pH y cumplimiento."),
        ("Registros de limpieza", len(datos_hojas["Limpieza"][1]), "Actividades registradas de limpieza."),
        ("Mantenimientos", len(datos_hojas["Mantenimiento"][1]), "Intervenciones y próximas fechas."),
        ("Operadores registrados", len(datos_hojas["Operadores"][1]), "Incluye operadores activos e inactivos."),
    ]
    for numero_fila, (indicador, cantidad, descripcion) in enumerate(indicadores, start=6):
        resumen.write(numero_fila, 0, indicador, formato_metrica)
        resumen.write_number(numero_fila, 1, cantidad, formato_celda)
        resumen.write(numero_fila, 2, descripcion, formato_celda)
    resumen.freeze_panes(6, 0)
    resumen.autofilter(5, 0, 5 + len(indicadores), 2)

    for nombre_hoja, (encabezados, filas) in datos_hojas.items():
        hoja = libro.add_worksheet(nombre_hoja)
        hoja.hide_gridlines(2)
        hoja.freeze_panes(1, 0)
        hoja.set_row(0, 32, formato_encabezado)
        hoja.write_row(0, 0, encabezados, formato_encabezado)

        for indice_fila, fila in enumerate(filas, start=1):
            for indice_columna, valor in enumerate(fila):
                if valor is None:
                    hoja.write_blank(indice_fila, indice_columna, None, formato_celda)
                elif isinstance(valor, bool):
                    hoja.write_boolean(indice_fila, indice_columna, valor, formato_celda)
                elif isinstance(valor, (int, float)):
                    fmt = formato_numero if isinstance(valor, float) else formato_celda
                    hoja.write_number(indice_fila, indice_columna, valor, fmt)
                else:
                    hoja.write_string(indice_fila, indice_columna, str(valor), formato_celda)

        if encabezados:
            hoja.autofilter(0, 0, max(1, len(filas)), len(encabezados) - 1)
            for col_idx, encabezado in enumerate(encabezados):
                longitud = len(str(encabezado))
                # Examina un conjunto acotado para definir anchos prácticos.
                for fila in filas[:250]:
                    if col_idx < len(fila) and fila[col_idx] is not None:
                        longitud = max(longitud, min(len(str(fila[col_idx])), 42))
                ancho = max(12, min(longitud + 2, 38))
                hoja.set_column(col_idx, col_idx, ancho)

    libro.close()
    salida.seek(0)
    nombre_archivo = datetime.now().strftime("AguaPotableLab_registros_%Y%m%d_%H%M%S.xlsx")

    return StreamingResponse(
        salida,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre_archivo}"',
            "Cache-Control": "no-store",
        },
    )
