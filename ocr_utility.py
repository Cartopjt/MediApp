import io
import re
import os
import base64
import requests
import markdown   
from google.cloud import vision
from rapidfuzz import fuzz, process
from models import Medicamento
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
# ----------------------------
# Búsqueda fuzzy de medicamento
# ----------------------------
LISTA_NEGRA = {
    "mg", "ml", "tabletas", "comprimidos", "capsulas", "jarabe", "solucion",
    "via", "oral", "uso", "industria", "venta", "libre", "bayer",
    "argentina", "genfarc", "farmacia", "análgesico", "analgesico", 
    "antifebril"
}

def es_medicamento_gpt(texto):
    prompt = f"""
    Eres un filtro médico.
    Responde únicamente con "SI" si "{texto}" es un nombre de un medicamento válido,
    aunque esté mal escrito ligeramente (ej. paracitamol → paracetamol).
    Responde "NO" si no parece medicamento.
    No expliques nada, solo responde con SI o NO.
    """

    resp = client.chat.completions.create(
        model="gpt-4o", 
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    respuesta = resp.choices[0].message.content.strip().upper()
    return respuesta == "SI"


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

    if len(texto_filtrado) < 3:  # OCR basura
        return None, [], 0.0

    # Dividimos en palabras
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

    # Filtramos sugerencias útiles (>= 60)
    sugerencias = []
    vistos = set()
    for nombre, score, _ in candidatos:
        if score >= 60 and nombre not in vistos:
            sugerencias.append({"nombre": nombre, "confianza": round(score, 2)})
            vistos.add(nombre)
        if len(sugerencias) >= 5:
            break

    mejor = candidatos[0] if candidatos else None

    if mejor and mejor[1] >= 85:
        med = Medicamento.query.filter_by(nombre_medicamento=mejor[0]).first()
        return med, sugerencias, mejor[1]

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
    

def consultar_gpt(medicamento, descripcion_base):
    print(">>> Entrando a consultar_gpt con:", medicamento)

    # Filtro: solo dejamos pasar medicamentos de la lista
    if medicamento not in [m.nombre_medicamento for m in Medicamento.query.all()]:
        return "El texto detectado no corresponde a un medicamento válido."

    prompt = f"""
    Eres un asistente médico especializado exclusivamente en medicamentos.
    Solo debes responder información médica relacionada con {medicamento}.
    Si la consulta no está relacionada con medicamentos, responde con:
    '⚠️ Lo siento, solo puedo dar información sobre medicamentos.'
    
    Explica de forma clara y sencilla:
    - Qué es {medicamento}
    - Para qué sirve
    - Efectos secundarios comunes
    - Precauciones y contraindicaciones
    
    Información base: {descripcion_base}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Responde siempre en texto visible, claro y en español."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=500
        )

        print("=== Respuesta GPT ===")
        print(response)
        print("====================")

        contenido = response.choices[0].message.content
        if not contenido or contenido.strip() == "":
            contenido = "No se pudo generar información en este momento."
          
        return markdown.markdown(contenido)

    except Exception as e:
        print(" Error en la llamada a GPT:", e)
        return "Error al consultar información con GPT."
   