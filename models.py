from extension import db
from flask_login import UserMixin
from datetime import date

# MODELOS
class User(db.Model, UserMixin):
    __tablename__ = "usuarios" 
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    passwd = db.Column(db.String(200), nullable=False)
    consultas_hoy = db.Column(db.Integer, default=0)
    ultima_fecha = db.Column(db.Date, default=date.today)

class Medicamento(db.Model):
    __tablename__ = "medicamentos"
    id = db.Column(db.Integer, primary_key=True)
    nombre_medicamento = db.Column(db.String(100), nullable=False, unique=True)
    uso_clinico = db.Column(db.Text)
    dosis_pautas = db.Column(db.Text)
    contraindicaciones = db.Column(db.Text)
    precauciones = db.Column(db.Text)
    efectos_secundarios = db.Column(db.Text)
    interacciones = db.Column(db.Text)
    datos_farmaceuticos = db.Column(db.Text)
    presentaciones = db.Column(db.Text)

class Consulta(db.Model):
    __tablename__ = "consultas"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    medicamento_id = db.Column(db.Integer, db.ForeignKey("medicamentos.id"), nullable=False)
    fecha = db.Column(db.Date, default=date.today)