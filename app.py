import os
from datetime import date
from flask import Flask, render_template, request ,redirect, url_for, session,flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import pytesseract
from rapidfuzz import process
import pymysql
from openai import OpenAI

pymysql.install_as_MySQLdb()
app = Flask(__name__)

# Configuración BD MySQL
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@localhost/medicamentos_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "secretpasswd"

db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

#Aqui va la ruta del programa de pyteseeract (cambiante)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract"

# Cliente GPT
client = OpenAI(api_key="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") 

# Dataset temporal (cambio a base de datos futuro)
medicamentos = [
    {"nombre": "Paracetamol", "dosis": "500mg", "descripcion": "Analgésico y antipirético"},
    {"nombre": "Ibuprofeno", "dosis": "400mg", "descripcion": "Antiinflamatorio"},
    {"nombre": "Amoxicilina", "dosis": "500mg", "descripcion": "Antibiótico de amplio espectro"}
]
nombres = [m["nombre"] for m in medicamentos]

# MODELOS
class User(db.Model, UserMixin):
    __tablename__ = "usuarios" 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    passwd = db.Column(db.String(200), nullable=False)
    consultas_hoy = db.Column(db.Integer, default=0)
    ultima_fecha = db.Column(db.Date, default=date.today)

# LOGIN MANAGER
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# FUNCIONES
def consultar_gpt(medicamento, descripcion_base):
    print(">>> Entrando a consultar_gpt con:", medicamento)

    # Filtro: solo dejamos pasar medicamentos de la lista
    if medicamento not in nombres:
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
        ruta_imagen = os.path.join("static", archivo.filename)
        archivo.save(ruta_imagen)

        # OCR
        texto_detectado = pytesseract.image_to_string(Image.open(ruta_imagen))
        palabra = texto_detectado.split()[0] if texto_detectado else ""

        # Coincidencia con dataset (base de datos futuro)
        if palabra:
            nombre, score, _ = process.extractOne(palabra, nombres)
            for m in medicamentos:
                if m["nombre"] == nombre:
                    explicacion_gpt = consultar_gpt(nombre, m["descripcion"])
                    resultado = {
                        "texto_detectado": texto_detectado,
                        "nombre": nombre,
                        "confianza": f"{score:.2f}%",
                        "dosis": m["dosis"],
                        "descripcion": m["descripcion"],
                        "chatgpt": explicacion_gpt
                    }
                    break
        else:
            resultado = {"error": "No se detectó texto"}

    return render_template("index.html", resultado=resultado)

#Ruta de chat
@app.route("/chat/<medicamento>", methods=["GET", "POST"])
def chat(medicamento):
    if medicamento not in nombres:
        return "Medicamento no válido."

    historial = session.get("historial_chat", [])

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

        # Guardamos el historial del chat en sesión
        historial.append({"usuario": pregunta, "bot": respuesta})
        session["historial_chat"] = historial

    return render_template("chat.html", medicamento=medicamento, historial=historial)

if __name__ == "__main__":
    app.run(debug=False)
