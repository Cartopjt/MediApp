import io
import re
import os
import base64
import requests
from google.cloud import vision
from rapidfuzz import fuzz, process
from models import Medicamento
from dotenv import load_dotenv

load_dotenv()
# ----------------------------
# Búsqueda fuzzy de medicamento
# ----------------------------
LISTA_NEGRA = {
    "mg", "ml", "tabletas", "comprimidos", "capsulas", "jarabe", "solucion",
    "via", "oral", "uso", "industria", "venta", "libre", "bayer",
    "argentina", "genfarc", "farmacia", "análgesico", "analgesico", 
    "antifebril"
}

def limpiar_texto(texto):
    limpio = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚñÑ0-9\s]", " ", texto)
    limpio = re.sub(r"\s+", " ", limpio).lower().strip()
    palabras = [p for p in limpio.split() if len(p) > 2 and p not in LISTA_NEGRA]
    return " ".join(palabras)   # devolvemos texto limpio entero



def buscar_medicamento(texto_ocr):
    medicamentos = [m.nombre_medicamento for m in Medicamento.query.all()]
    if not medicamentos:
        return None, [], 0.0

    texto_filtrado = limpiar_texto(texto_ocr)

    # Dividimos en palabras para buscar coincidencias también
    palabras = texto_filtrado.split()

    candidatos = []
    for palabra in palabras:
        matches = process.extract(
            palabra,
            medicamentos,
            scorer=fuzz.partial_ratio,
            limit=3
        )
        candidatos.extend(matches)

    # También probamos con la frase entera
    matches_full = process.extract(
        texto_filtrado,
        medicamentos,
        scorer=fuzz.WRatio,
        limit=5
    )
    candidatos.extend(matches_full)

    # Ordenamos por score
    candidatos = sorted(candidatos, key=lambda x: x[1], reverse=True)

    # Preparamos sugerencias únicas
    sugerencias = []
    vistos = set()
    for nombre, score, _ in candidatos:
        if nombre not in vistos:
            sugerencias.append({"nombre": nombre, "confianza": round(score, 2)})
            vistos.add(nombre)
        if len(sugerencias) >= 5:
            break

    mejor = candidatos[0] if candidatos else None

    if mejor:
        score = mejor[1]
        if score >= 70:
            med = Medicamento.query.filter_by(nombre_medicamento=mejor[0]).first()
            return med, sugerencias, score

    return None, sugerencias, 0.0


# ----------------------------
# OCR con Google Cloud Vision
# ----------------------------
def ocr_texto(ruta_imagen):
    api_key = os.getenv("GOOGLE_VISION_KEY")
    if not api_key:
        raise Exception("No se encontró GOOGLE_VISION_KEY en .env")

    with io.open(ruta_imagen, "rb") as image_file:
        content = base64.b64encode(image_file.read()).decode("utf-8")

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

    payload = {
        "requests": [
            {
                "image": {"content": content},
                "features": [{"type": "TEXT_DETECTION"}]
            }
        ]
    }

    response = requests.post(url, json=payload)
    result = response.json()

    if "error" in result:
        raise Exception(f"OCR Error: {result['error']}")

    try:
        return result["responses"][0]["textAnnotations"][0]["description"].strip()
    except (KeyError, IndexError):
        return ""