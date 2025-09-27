import os
from datetime import date
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request ,redirect, url_for, session,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from rapidfuzz import process
import pymysql
from openai import OpenAI

#Modelos y el ORC
from extension import db
from models import User, Medicamento, Consulta
from ocr_utility import ocr_texto, buscar_medicamento

pymysql.install_as_MySQLdb()
app = Flask(__name__)

# Configuración BD MySQL
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@localhost/medicamentos_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "secretpasswd"

db.init_app(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Cliente GPT
client = OpenAI(api_key="") 

# LOGIN MANAGER
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# FUNCIONES
# Dataset temporal (cambio a base de datos futuro)
def obtener_medicamentos():
    return Medicamento.query.all()

def obtener_nombres():
    return [m.nombre_medicamento for m in Medicamento.query.all()]

def consultar_gpt(medicamento, descripcion_base):
    print(">>> Entrando a consultar_gpt con:", medicamento)

    # Filtro: solo dejamos pasar medicamentos de la lista
    if medicamento not in obtener_nombres():
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
        return contenido

    except Exception as e:
        print(" Error en la llamada a GPT:", e)
        return "Error al consultar información con GPT."

    

# RUTAS DE AUTENTICACIÓN
#Registro
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            return "El usuario ya existe"

        nuevo = User(email=email, passwd=generate_password_hash(password))
        db.session.add(nuevo)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

#Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.passwd, password):
            login_user(user)
            return redirect(url_for("index"))
        else:
            return "Credenciales inválidas"

    return render_template("login.html")

#Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# Ruta principal
MAX_CONSULTAS_INVITADO = 3

@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None

    if request.method == "POST":
        if current_user.is_authenticated:
            # Usuario registrado -> consultas ilimitadas
            current_user.consultas_hoy += 1
            db.session.commit()

        else:
            # Invitado tiene 3 consultas y reinicio de 24 horas
            hoy = str(date.today())
            if "consultas_invitado" not in session or session.get("ultima_fecha") != hoy:
                session["consultas_invitado"] = MAX_CONSULTAS_INVITADO
                session["ultima_fecha"] = hoy

            if session["consultas_invitado"] <= 0:
                flash("Se agotaron tus consultas gratis. Regístrate para continuar.")
                return redirect(url_for("login"))

            session["consultas_invitado"] -= 1
        
        if "imagen" not in request.files:
            return "No se envió archivo"

        archivo = request.files["imagen"]

        if archivo.filename == "":
            return "No seleccionaste archivo"

        # Guardar temporalmente la imagen
        filename = secure_filename(archivo.filename)
        ruta_imagen = os.path.join("static", archivo.filename)
        archivo.save(ruta_imagen)

        # OCR
        texto_detectado = ocr_texto(ruta_imagen)

        # Fuzzy matching en BD 
        medicamento, sugerencias,score = buscar_medicamento(texto_detectado)

        # Coincidencia con dataset (base de datos futuro)
        if medicamento and score >= 80:
            explicacion_gpt = consultar_gpt(medicamento.nombre_medicamento, medicamento.uso_clinico or "")  
            resultado = {
                "imagen": filename, # la ruta de la foto subida
                "nombre": medicamento.nombre_medicamento,
                "confianza": f"{score:.2f}%",
                "uso_clinico": medicamento.uso_clinico,
                "dosis_pautas": medicamento.dosis_pautas,
                "contraindicaciones": medicamento.contraindicaciones,
                "precauciones": medicamento.precauciones,
                "efectos_secundarios": medicamento.efectos_secundarios,
                "interacciones": medicamento.interacciones,
                "datos_farmaceuticos": medicamento.datos_farmaceuticos,
                "chatgpt": explicacion_gpt,
            }
            if current_user.is_authenticated:
                consulta = Consulta(usuario_id=current_user.id,medicamento_id=medicamento.id,imagen_subida=filename,chatgpt=explicacion_gpt)
                db.session.add(consulta)
                db.session.commit()    
                session["ultimo_resultado"] = resultado
        else:
            if sugerencias:
                resultado = {
                    "imagen": filename,
                    "texto_detectado": texto_detectado,
                    "error": "No se detectó coincidencia exacta, prueba otra vez",
                    "sugerencias": sugerencias
                }
            else: 
                resultado = {
                    "texto_detectado": texto_detectado,
                    "error": "Medicamento no encontrado."
                }

    return render_template("index.html", resultado=resultado)


#Volver a consulta
@app.route("/consulta")
def volver_consulta():
    if current_user.is_authenticated:
        consulta = Consulta.query.filter_by(usuario_id=current_user.id).order_by(Consulta.id.desc()).first()
        if not consulta:
            flash("No hay consultas previas.")
            return redirect(url_for("index"))

        med = Medicamento.query.get(consulta.medicamento_id)
        resultado = {
            "imagen": consulta.imagen_subida,
            "nombre": med.nombre_medicamento,
            "uso_clinico": med.uso_clinico,
            "dosis_pautas": med.dosis_pautas,
            "contraindicaciones": med.contraindicaciones,
            "precauciones": med.precauciones,
            "efectos_secundarios": med.efectos_secundarios,
            "interacciones": med.interacciones,
            "datos_farmaceuticos": med.datos_farmaceuticos,
            "chatgpt": consulta.chatgpt  # Aquí cargamos la respuesta guardada
        }
    else:
        resultado = session.get("ultimo_resultado")
        if not resultado:
            flash("No hay consultas previas.")
            return redirect(url_for("index"))

    return render_template("index.html", resultado=resultado)


#Ruta alternativa
@app.route("/medicamento/<nombre>")
def ver_medicamento(nombre):
    med = Medicamento.query.filter_by(nombre_medicamento=nombre).first()
    if not med:
        return "Medicamento no encontrado", 404

    explicacion_gpt = consultar_gpt(med.nombre_medicamento, med.uso_clinico or "")

    resultado = {
        "texto_detectado": nombre,
        "nombre": med.nombre_medicamento,
        "confianza": "100%",
        "dosis": med.dosis_pautas,
        "descripcion": med.uso_clinico,
        "chatgpt": explicacion_gpt
    }

    return render_template("index.html", resultado=resultado)

#Ruta de chat
@app.route("/chat/<medicamento>", methods=["GET", "POST"])
def chat(medicamento):
    if medicamento not in obtener_nombres():
        return "Medicamento no válido."

    # Reiniciamos historial en cada nueva consulta
    historial = []

    # Agregamos el mensaje inicial del bot
    from datetime import datetime
    hora = datetime.now().hour

    if hora < 12:
        saludo = f"Buenos días, ¿qué quiere saber sobre {medicamento}?"
    elif hora < 19:
        saludo = f"Buenas tardes, ¿qué quiere saber sobre {medicamento}?"
    else:
        saludo = f"Buenas noches, ¿qué quiere saber sobre {medicamento}?"

    historial.append({"usuario": "", "bot": saludo})

    if request.method == "POST":
        pregunta = request.form["mensaje"]

        prompt = f"""
        Eres un asistente médico especializado exclusivamente en el medicamento {medicamento}.
        Responde SOLO sobre este medicamento.
        Si la consulta no está relacionada con medicamentos, responde con:
        '⚠️ Lo siento, solo puedo dar información sobre medicamentos.'
        Pregunta del usuario: {pregunta}
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responde en español, de forma clara y sencilla."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=400
            )
            respuesta = response.choices[0].message.content
        except Exception as e:
            respuesta = f"Error al consultar IA: {e}"

        # Guardamos en historial (solo de la sesión actual)
        historial.append({"usuario": pregunta, "bot": respuesta})

    return render_template("chat.html", medicamento=medicamento, historial=historial)


if __name__ == "__main__":
    app.run(debug=False)
