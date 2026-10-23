from datetime import datetime
from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "templates" / "index.html"
MARCADOR = "// AGUA_POTABLE_LAB_AUTOACTUALIZAR_PEDIDOS_2_HORAS"

if not INDEX_PATH.exists():
    raise SystemExit(
        "No encontré templates/index.html. Copia este archivo a la carpeta "
        "principal de AguaPotableLab y vuelve a ejecutarlo."
    )

contenido = INDEX_PATH.read_text(encoding="utf-8")

if MARCADOR in contenido:
    print("La actualización automática de pedidos ya está instalada. No hice cambios.")
    raise SystemExit(0)

ancla = "verificarSesionOperador();"
posicion = contenido.rfind(ancla)
if posicion < 0:
    raise SystemExit(
        "No encontré la llamada final a verificarSesionOperador() en index.html. "
        "No se modificó ningún archivo. Envíame el index.html actual para adaptarlo."
    )

fin = posicion + len(ancla)
bloque = f"""

{MARCADOR}
// Consulta el historial cada minuto para retirar automáticamente de la tabla
// los pedidos Entregados/Cancelados que ya cumplieron dos horas.
setInterval(() => {{
    if (
        document.visibilityState === "visible" &&
        !document.querySelector("#panel-pedidos select:focus, #panel-pedidos button:focus")
    ) {{
        cargarPedidos();
    }}
}}, 60 * 1000);

// Al volver a esta pestaña, actualiza enseguida el historial si pasó tiempo.
document.addEventListener("visibilitychange", () => {{
    if (document.visibilityState === "visible") {{
        cargarPedidos();
    }}
}});
"""

respaldo = INDEX_PATH.with_name(
    f"index.html.respaldo_pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)
shutil.copy2(INDEX_PATH, respaldo)
INDEX_PATH.write_text(contenido[:fin] + bloque + contenido[fin:], encoding="utf-8")

print("Actualización instalada correctamente.")
print(f"Respaldo creado: {respaldo.name}")
print("El historial se actualizará cada minuto y al volver a la pestaña.")
