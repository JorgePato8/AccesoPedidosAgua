from pathlib import Path
from datetime import datetime
import shutil

"""Actualiza únicamente las etiquetas visibles en templates/index.html.
Conserva los nombres internos de variables y valores que usa la API.
"""

base = Path(__file__).resolve().parent
ruta = base / "templates" / "index.html"

if not ruta.exists():
    raise SystemExit(
        "No se encontró templates/index.html. Ejecute este archivo desde la carpeta raíz de AguaPotableLab."
    )

contenido = ruta.read_text(encoding="utf-8")
reemplazos = [
    ("<title>Agua Potable Lab</title>", "<title>Agua Filtrada | Laboratorio de Procesos Industriales</title>"),
    ("<h1>Agua Potable Lab</h1>", "<h1>Agua Filtrada</h1>"),
    ("Sistema de registro y control del proceso", "Laboratorio de Procesos Industriales · Sistema de registro y control"),
    ("<th>Oficina</th>", "<th>Área</th>"),
    ("<th>Garrafones</th>", "<th>Bidones (20 L)</th>"),
    ("Preparación y desinfección de garrafones", "Preparación y desinfección de bidones (20 L)"),
    ("Cantidad de garrafones", "Cantidad de bidones (20 L)"),
    ("Desinfección del garrafón", "Desinfección del bidón (20 L)"),
    ("2 gotas por garrafón", "2 gotas por bidón (20 L)"),
    ("Inspección final del garrafón", "Inspección final del bidón (20 L)"),
    ("Garrafón · 20 L", "Bidón (20 L)"),
    ("Preparación de garrafones guardada correctamente.", "Preparación de bidones (20 L) guardada correctamente."),
    ("Debe solicitar al menos un garrafón ", "Debe solicitar al menos un bidón (20 L) "),
]

nuevo = contenido
cambios = []
for antiguo, nuevo_texto in reemplazos:
    cantidad = nuevo.count(antiguo)
    if cantidad:
        nuevo = nuevo.replace(antiguo, nuevo_texto)
        cambios.append((antiguo, cantidad))

if nuevo == contenido:
    print("No se encontró ninguna etiqueta que necesitara cambio. No se modificó el archivo.")
    raise SystemExit(0)

marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
respaldo = ruta.with_name(f"index.html.respaldo_{marca_tiempo}")
shutil.copy2(ruta, respaldo)
ruta.write_text(nuevo, encoding="utf-8")

print("Se actualizaron las etiquetas visibles de templates/index.html.")
print(f"Respaldo creado: {respaldo.name}")
print("Cambios aplicados:")
for texto, cantidad in cambios:
    print(f" - {texto!r}: {cantidad} coincidencia(s)")
print("Nota: se dejaron intactos los valores internos como 'Garrafón' y 'garrafones' que la API y SQLite todavía usan internamente.")
