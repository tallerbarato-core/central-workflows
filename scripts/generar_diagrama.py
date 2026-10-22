import os
import re
import glob
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Falta la variable de entorno GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# Recopilar scripts del repositorio analizado (.gs, .py, .yml)
extensiones = ("*.gs", "*.py", ".github/workflows/*.yml")
archivos = []
for ext in extensiones:
    archivos.extend(glob.glob(ext))

contenido_scripts = ""
for ruta in archivos:
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
            contenido_scripts += f"\n--- ARCHIVO: {ruta} ---\n{f.read()}\n"

if not contenido_scripts.strip():
    print("No se encontraron scripts relevantes para diagramar.")
    exit(0)

prompt = f"""
Eres un arquitecto de software experto en diagramas Mermaid.js.
Analiza los scripts del repositorio y genera UNICAMENTE un diagrama 'flowchart TD' en sintaxis Mermaid.
Mapea claramente triggers, funciones, filtros, conexiones externas (APIs/FTP/Gmail) y hojas de cálculo.

REGLAS ESTRICTAS:
- Devuelve SOLO el bloque delimitado por ```mermaid y ```.
- Cero explicaciones, cero saludos, cero comentarios adicionales fuera del bloque.
- Subgraphs claros por cada archivo o servicio.

Scripts:
{contenido_scripts}
"""

print("Consultando a Gemini...")
respuesta = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt
)

bloque_mermaid = respuesta.text.strip()
if not bloque_mermaid.startswith("```mermaid"):
    match = re.search(r"```mermaid[\s\S]*?```", bloque_mermaid)
    if match:
        bloque_mermaid = match.group(0)

# Actualizar el README.md del repositorio objetivo
archivo_readme = "README.md"
tag_inicio = "<!-- MERMAID_START -->"
tag_fin = "<!-- MERMAID_END -->"

if os.path.exists(archivo_readme):
    with open(archivo_readme, "r", encoding="utf-8") as f:
        readme_texto = f.read()
else:
    readme_texto = f"# Documentación\n\n{tag_inicio}\n{tag_fin}\n"

patron = re.compile(f"{re.escape(tag_inicio)}[\\s\\S]*?{re.escape(tag_fin)}")
nuevo_bloque = f"{tag_inicio}\n\n{bloque_mermaid}\n\n{tag_fin}"

if patron.search(readme_texto):
    readme_actualizado = patron.sub(nuevo_bloque, readme_texto)
else:
    readme_actualizado = f"{readme_texto}\n\n## Diagrama de Flujo del Sistema\n\n{nuevo_bloque}\n"

with open(archivo_readme, "w", encoding="utf-8") as f:
    f.write(readme_actualizado)

print("¡README.md actualizado correctamente con el nuevo diagrama!")
