import os
import re
import glob
import time
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Falta la variable de entorno GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# 1. Recopilar scripts del repositorio (.gs, .py, .yml)
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

# 2. Descubrir modelos disponibles automáticamente
print("Buscando modelos compatibles en la cuenta...")
modelos_candidatos = []
try:
    for m in client.models.list():
        nombre = getattr(m, "name", "")
        n = nombre.lower().replace("models/", "")
        # Descartar modelos que no sean para generación de texto
        if "gemini" in n and not any(x in n for x in ["tts", "embedding", "imagen", "audio", "vision"]):
            modelos_candidatos.append(n)
except Exception as e:
    print(f"Aviso al listar modelos: {e}")

# Fallback con los modelos disponibles si la API no permite listar
if not modelos_candidatos:
    modelos_candidatos = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]

# Ordenar dando prioridad a lite y luego a flash (para evitar saturación)
def ordenar_prioridad(nombre):
    score = 10
    if "lite" in nombre:
        score = 1
    elif "flash" in nombre:
        score = 2
    return score

modelos_candidatos = sorted(list(set(modelos_candidatos)), key=ordenar_prioridad)
print(f"Modelos detectados (orden de prueba): {modelos_candidatos}")

# 3. Llamar a la API probando alternativas ante saturación (503)
respuesta = None
for modelo in modelos_candidatos:
    print(f"Probando modelo: {modelo}...")
    try:
        res = client.models.generate_content(
            model=modelo,
            contents=prompt
        )
        if res and res.text:
            respuesta = res
            print(f"-> ¡Éxito generando con {modelo}!")
            break
    except Exception as e:
        print(f"Aviso con {modelo}: {e}. Pasando al siguiente...")
        time.sleep(2)

if not respuesta:
    raise RuntimeError("No se pudo obtener respuesta de ningún modelo disponible.")

bloque_mermaid = respuesta.text.strip()
if not bloque_mermaid.startswith("```mermaid"):
    match = re.search(r"```mermaid[\s\S]*?```", bloque_mermaid)
    if match:
        bloque_mermaid = match.group(0)

# 4. Actualizar README.md
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

print("¡README.md actualizado con éxito!")
