from pathlib import Path
import shutil
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "templates" / "index.html"

BOTON = '''        <div class="control-item bloque-exportacion-excel">
            <h3>Exportación de registros</h3>
            <p class="texto-ayuda">
                Descargue un libro Excel con los datos guardados en todos los módulos.
                Incluye también los pedidos finalizados que ya no aparecen en la tabla principal.
            </p>
            <button
                type="button"
                class="btn-principal btn-guardar"
                onclick="window.location.href='/api/exportar-excel'"
            >
                DESCARGAR EXCEL ACTUALIZADO
            </button>
        </div>

'''

if not INDEX_PATH.exists():
    raise SystemExit(
        f"No se encontró {INDEX_PATH}. Ejecuta este archivo desde la carpeta principal de AguaPotableLab."
    )

html = INDEX_PATH.read_text(encoding="utf-8")
if "/api/exportar-excel" in html:
    print("El botón de exportación ya existe en index.html. No se hicieron cambios.")
    raise SystemExit(0)

panel_inicio = html.find('id="panel-pedidos"')
if panel_inicio == -1:
    raise SystemExit(
        "No se encontró el panel de pedidos. No se modificó index.html. "
        "Adjunta tu versión actual para adaptar el cambio."
    )

pos_titulo = html.find("</h2>", panel_inicio)
if pos_titulo == -1:
    raise SystemExit(
        "No se encontró el título dentro del panel de pedidos. No se modificó index.html."
    )

respaldo = INDEX_PATH.with_name(
    f"index.html.respaldo_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)
shutil.copy2(INDEX_PATH, respaldo)
html = html[:pos_titulo + len("</h2>")] + "\n\n" + BOTON + html[pos_titulo + len("</h2>"):]
INDEX_PATH.write_text(html, encoding="utf-8")
print("Botón de exportación añadido correctamente.")
print(f"Copia de seguridad creada: {respaldo.name}")
