import io
import re
from google.cloud import vision
from rapidfuzz import fuzz, process
from models import Medicamento

# ----------------------------
# Lista negra y limpieza de texto
# ----------------------------
LISTA_NEGRA = {"mg", "ml", "tabletas", "recubiertas", "capsulas",
               "jarabe", "solucion", "via", "oral", "uso"}

def limpiar_texto(texto):
    """Limpia el texto manteniendo solo palabras útiles para búsqueda de medicamentos."""
    limpio = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\s]", " ", texto)
    limpio = re.sub(r"\s+", " ", limpio)
    limpio = limpio.lower().strip()
    palabras = [p for p in limpio.split() if len(p) > 1 and p not in LISTA_NEGRA]
    return palabras

# ----------------------------
# Búsqueda fuzzy de medicamento
# ----------------------------
def buscar_medicamento(texto_ocr):
    """Busca el medicamento más parecido en la base de datos."""
    medicamentos = [m.nombre_medicamento for m in Medicamento.query.all()]
    if not medicamentos:
        return None, 0

    candidatos = limpiar_texto(texto_ocr)
    mejor_nombre = None
    mejor_score = 0

    for candidato in candidatos:
        match = process.extractOne(candidato, medicamentos, scorer=fuzz.WRatio)
        if match:
            nombre, score, _ = match
            if score > mejor_score:
                mejor_nombre = nombre
                mejor_score = score

    if mejor_nombre:
        med = Medicamento.query.filter_by(nombre_medicamento=mejor_nombre).first()
        return med, mejor_score

    return None, 0

# ----------------------------
# OCR con Google Cloud Vision
# ----------------------------
def ocr_texto(ruta_imagen):
    """Detecta texto en la imagen usando Google Cloud Vision API."""
    client = vision.ImageAnnotatorClient()  # Usa automáticamente la variable de entorno

    with io.open(ruta_imagen, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    textos = response.text_annotations

    if textos:
        # El primer elemento contiene todo el texto detectado
        texto_detectado = textos[0].description
        return texto_detectado.strip()
    else:
        return ""
