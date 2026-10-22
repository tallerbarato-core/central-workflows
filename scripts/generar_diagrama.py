import os
import re
import time
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Falta la variable de entorno GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# 1. Carpetas y extensiones a excluir (ruido, binarios y librerías)
CARPETAS_IGNORADAS = {
    ".git", ".github", ".central-tools", "node_modules", "vendor",
    "venv", ".venv", "__pycache__", "dist", "build"
}

EXTENSIONES_IGNORADAS = {
    # Documentación y estilos visuales
    ".md", ".css", ".scss", ".less", ".txt", ".json", ".lock",
    # Imágenes y multimedia
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf",
    # Archivos comprimidos y ejecutables
    ".zip", ".tar", ".gz", ".rar", ".exe", ".bin"
}

archivos_proyecto = []

# Recorrer todo el árbol de carpetas del repositorio
for raiz, carpetas, ficheros in os.walk("."):
    # Filtrar carpetas excluidas sobre la marcha
    carpetas[:] = [c for c in carpetas if c not in CARPETAS_IGNORADAS]
    
    for f in ficheros:
        nombre_completo = os.path.join(raiz, f)
        _, ext = os.path.splitext(f)
        
        if ext.lower() in EXTENSIONES_IGNORADAS:
            continue
        if f.lower() in {"readme.md", "license"}:
            continue
            
        archivos_proyecto.append(nombre_completo)

# 2. Leer contenido de los scripts encontrados
contenido_scripts = ""
for ruta in archivos_proyecto:
    try:
        with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
            texto = archivo.read()
            # Omitir archivos gigantescos o minificados
            if len(texto) > 100000:
                texto = texto[:100000] + "\n...[archivo truncado por tamaño]..."
            contenido_scripts += f"\n--- ARCHIVO: {ruta} ---\n{texto}\n"
    except Exception as e:
        print(f"Omitiendo {ruta}: {e}")

if not contenido_scripts.strip():
    print("No se encontraron scripts funcionales para procesar.")
    exit(0)

# 3. Prompt para Gemini
prompt = f"""
Eres un arquitecto de software experto en diagramas Mermaid.js.
Analiza todos los archivos de código del proyecto y genera UNICAMENTE un diagrama de arquitectura y flujo 'flowchart TD' en sintaxis Mermaid.

REGLAS DE SINTAXIS ESTRICTAS PARA MERMAID (EVITAR ERRORES DE PARSEO):
1. Devuelve SOLO el bloque delimitado por ```mermaid y ```. Cero texto fuera.
2. NUNCA uses paréntesis, corchetes, barras ni símbolos especiales sin comillas en las etiquetas de conexión.
   INCORRECTO: -->|POST (medida)|
   CORRECTO:   -->|"POST (medida)"| o -->|POST medida|
3. Todos los textos con saltos de línea dentro de nodos deben usar comillas dobles y comillas simples en el nodo:
   N_ID["Nombre del nodo<br>Detalle"]
4. No uses caracteres conflictivos como comillas dobles dentro de otras comillas dobles.
5. Crea subgraphs claros para separar frontend, backend, APIs externas, base de datos y salidas.

Código del proyecto:
{contenido_scripts}
"""

# 4. Detección automática y ordenación de modelos
print("Buscando modelos compatibles...")
modelos_candidatos = []
try:
    for m in client.models.list():
        nombre = getattr(m, "name", "")
        n = nombre.lower().replace("models/", "")
        if "gemini" in n and not any(x in n for x in ["tts", "embedding", "imagen", "audio", "vision"]):
            modelos_candidatos.append(n)
except Exception as e:
    print(f"Aviso al listar modelos: {e}")

if not modelos_candidatos:
    modelos_candidatos = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]

def ordenar_prioridad(nombre):
    if "lite" in nombre:
        return 1
    if "flash" in nombre:
        return 2
    return 3

modelos_candidatos = sorted(list(set(modelos_candidatos)), key=ordenar_prioridad)

# 5. Generación del diagrama
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
            print(f"-> Generado con éxito usando {modelo}")
            break
    except Exception as e:
        print(f"Aviso con {modelo}: {e}. Probando siguiente...")
        time.sleep(2)

if not respuesta:
    raise RuntimeError("No se pudo obtener respuesta de ningún modelo disponible.")

bloque_mermaid = respuesta.text.strip()
if not bloque_mermaid.startswith("```mermaid"):
    match = re.search(r"```mermaid[\s\S]*?```", bloque_mermaid)
    if match:
        bloque_mermaid = match.group(0)

# 6. Actualizar README.md
archivo_readme = "README.md"
tag_inicio = "<!-- MERMAID_START -->"
tag_fin = "<!-- MERMAID_END -->"

if os.path.exists(archivo_readme):
    with open(archivo_readme, "r", encoding="utf-8") as f:
        readme_texto = f.read()
else:
    readme_texto = f"# Documentación del Repositorio\n\n{tag_inicio}\n{tag_fin}\n"

patron = re.compile(f"{re.escape(tag_inicio)}[\\s\\S]*?{re.escape(tag_fin)}")
nuevo_bloque = f"{tag_inicio}\n\n{bloque_mermaid}\n\n{tag_fin}"

if patron.search(readme_texto):
    readme_actualizado = patron.sub(nuevo_bloque, readme_texto)
else:
    readme_actualizado = f"{readme_texto}\n\n## Diagrama de Flujo del Sistema\n\n{nuevo_bloque}\n"

with open(archivo_readme, "w", encoding="utf-8") as f:
    f.write(readme_actualizado)

print("¡README.md actualizado con éxito!")
