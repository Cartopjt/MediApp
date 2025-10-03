import os
import markdown
from datetime import date,datetime
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
        contenido_html = markdown.markdown(contenido)    
        return contenido_html

    except Exception as e:
        print(" Error en la llamada a GPT:", e)
        return "Error al consultar información con GPT."

    

# RUTAS DE AUTENTICACIÓN
#Registro
@app.route("/register", methods=["GET", "POST"])
def register():
    errors = {}
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        # Validaciones
        if not email:
            errors["email"] = "El correo es obligatorio"
        elif User.query.filter_by(email=email).first():
            errors["email"] = "El usuario ya existe"

        if not password:
            errors["password"] = "La contraseña es obligatoria"
        elif len(password) < 6:
            errors["password"] = "La contraseña debe tener al menos 6 caracteres"

        if not errors:  # Si no hay errores, registramos
            nuevo = User(email=email, passwd=generate_password_hash(password))
            db.session.add(nuevo)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template("register.html", errors=errors)

#Login
@app.route("/login", methods=["GET", "POST"])
def login():
    email_error = None
    password_error = None
    email_value = ""

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        # para mantener el valor escrito
        email_value = email 

        user = User.query.filter_by(email=email).first()

        if not user:
            email_error = "El correo no está registrado"
        elif not check_password_hash(user.passwd, password):
            password_error = "La contraseña es incorrecta"
        else:
            login_user(user)
            return redirect(url_for("index"))

    # Pasamos los errores y el email ingresado al template
    return render_template("login.html",
                           email_error=email_error,
                           password_error=password_error,
                           email=email_value)
    
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
        ext = os.path.splitext(archivo.filename)[1]  # conserva extensión original (.png, .jpg, etc.)
        filename = f"imagen_{timestamp}{ext}"
        ruta_imagen = os.path.join("static", filename)
        archivo.save(ruta_imagen)

        # OCR
        texto_detectado = ocr_texto(ruta_imagen)

        # Fuzzy matching en BD 
        medicamento, sugerencias,score = buscar_medicamento(texto_detectado)

        resultado = {
            "imagen": filename,
            "texto_detectado": texto_detectado,
            "sugerencias": sugerencias  
        }

        # Coincidencia con dataset (base de datos futuro)
        if medicamento and score >= 80:
            explicacion_gpt = consultar_gpt(medicamento.nombre_medicamento, medicamento.uso_clinico or "")  
            resultado.update({
                "imagen": filename, 
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
            })

            if current_user.is_authenticated:
                consulta = Consulta(usuario_id=current_user.id,medicamento_id=medicamento.id,imagen_subida=filename,chatgpt=explicacion_gpt)
                db.session.add(consulta)
                db.session.commit()    
        else:
            if not sugerencias:
                resultado["error"] = "Medicamento no encontrado."
            else: 
                resultado["error"] = "No se detectó coincidencia exacta, prueba otra vez"

        session["ultimo_resultado"] = {
            "nombre": resultado.get("nombre"),
            "imagen": filename
        }
        session["ultima_imagen"] = filename

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
            "chatgpt": consulta.chatgpt 
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
    medicamento = Medicamento.query.filter_by(nombre_medicamento=nombre).first()
    if not medicamento:
        flash("El medicamento no existe en la base de datos")
        return redirect(url_for("index"))

    imagen = session.get("ultima_imagen")
    session["medicamento_actual"] = nombre

    # Generar explicación GPT
    explicacion_gpt = consultar_gpt(medicamento.nombre_medicamento, medicamento.uso_clinico or "")

    resultado = {
        "imagen": imagen, 
        "nombre": medicamento.nombre_medicamento,
        "confianza": "Aceptado manualmente",
        "uso_clinico": medicamento.uso_clinico,
        "dosis_pautas": medicamento.dosis_pautas,
        "contraindicaciones": medicamento.contraindicaciones,
        "precauciones": medicamento.precauciones,
        "efectos_secundarios": medicamento.efectos_secundarios,
        "interacciones": medicamento.interacciones,
        "datos_farmaceuticos": medicamento.datos_farmaceuticos,
        "chatgpt": explicacion_gpt,
        "sugerencias": []
    }
    session["ultimo_resultado"] = resultado
    return render_template("index.html", resultado=resultado)


#Ruta de chat
@app.route("/chat/<medicamento>", methods=["GET", "POST"])
def chat(medicamento):
    med_sesion = session.get("medicamento_actual")
    if med_sesion:
        medicamento = med_sesion
        
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
