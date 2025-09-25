import io
import re
from google.cloud import vision
from rapidfuzz import fuzz, process
from models import Medicamento

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
        return None, [], 0.0  # <-- añadimos score 0

    texto_filtrado = limpiar_texto(texto_ocr)

    # Buscar top 5 coincidencias
    matches = process.extract(
        texto_filtrado,
        medicamentos,
        scorer=fuzz.WRatio,
        limit=5
    )

    sugerencias = [{"nombre": m[0], "confianza": round(m[1], 2)} for m in matches]

    mejor = matches[0] if matches else None

    if mejor:
        score = mejor[1]  # <-- aquí tenemos el score
        if score >= 80:   # <-- aceptamos con margen del 80%
            med = Medicamento.query.filter_by(nombre_medicamento=mejor[0]).first()
            return med, sugerencias, score

    # Si no hay match fuerte
    return None, sugerencias, 0.0


# ----------------------------
# OCR con Google Cloud Vision
# ----------------------------
def ocr_texto(ruta_imagen):

    client = vision.ImageAnnotatorClient()

    with io.open(ruta_imagen, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    if response.error.message:
        raise Exception(f"OCR Error: {response.error.message}")

    textos = response.text_annotations

    if textos:
        # El primer elemento contiene todo el texto detectado
        texto_detectado = textos[0].description
        print(">>> TEXTO DETECTADO PRINCIPAL:", texto_detectado)

        # Extra: palabras individuales
        for idx, t in enumerate(textos[1:], start=1):
            print(f"[{idx}] '{t.description}' -> bounding box: {t.bounding_poly.vertices}")

        return texto_detectado.strip()

    return ""