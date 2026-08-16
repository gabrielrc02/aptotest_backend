from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Table, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import datetime

# Tabla intermedia para la relación muchos a muchos entre Usuarios y Oposiciones contratadas
usuario_oposiciones = Table(
    'usuario_oposiciones',
    Base.metadata,
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), primary_key=True),
    Column('oposicion_id', Integer, ForeignKey('oposiciones.id'), primary_key=True)
)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    stripe_subscription_id = Column(String, nullable=True)

    examenes = relationship("ExamenRealizado", back_populates="usuario")

    # NUEVO: Oposiciones que este usuario tiene contratadas
    oposiciones = relationship("Oposicion", secondary=usuario_oposiciones, back_populates="usuarios")
    suscripciones = relationship("Suscripcion", back_populates="usuario", cascade="all, delete-orphan")


class Oposicion(Base):
    __tablename__ = "oposiciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)  # Ej: "Técnico ADIF"
    codigo = Column(String, unique=True, index=True)  # Ej: "tecnico_adif"
    stripe_price_id = Column(String, nullable=True)

    preguntas = relationship("Pregunta", back_populates="oposicion")
    usuarios = relationship("Usuario", secondary=usuario_oposiciones, back_populates="oposiciones")
    examenes = relationship("ExamenRealizado", back_populates="oposicion")


class Suscripcion(Base):
    __tablename__ = "suscripciones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    oposicion_id = Column(Integer, ForeignKey("oposiciones.id"))

    # Cada relación tiene su propio ID de Stripe y su propio estado de cancelación
    stripe_subscription_id = Column(String, unique=True, index=True)
    cancel_at_period_end = Column(Boolean, default=False)

    usuario = relationship("Usuario", back_populates="suscripciones")
    oposicion = relationship("Oposicion")


class Pregunta(Base):
    __tablename__ = "preguntas"

    id = Column(Integer, primary_key=True, index=True)
    oposicion_id = Column(Integer, ForeignKey("oposiciones.id"))  # NUEVO
    rama_destino = Column(String, index=True)
    tema = Column(String, index=True)
    enunciado = Column(String)
    opcion_a = Column(String)
    opcion_b = Column(String)
    opcion_c = Column(String)
    opcion_d = Column(String)
    respuesta_correcta = Column(String)
    justificacion = Column(String)
    origen = Column(String, nullable=True)

    oposicion = relationship("Oposicion", back_populates="preguntas")


class ExamenRealizado(Base):
    __tablename__ = "examenes_realizados"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    oposicion_id = Column(Integer, ForeignKey("oposiciones.id"), nullable=True)  # NUEVO
    fecha = Column(DateTime, default=datetime.datetime.utcnow)
    aciertos = Column(Integer)
    fallos = Column(Integer)
    blancos = Column(Integer)
    nota = Column(Float, default=0.0)

    usuario = relationship("Usuario", back_populates="examenes")
    oposicion = relationship("Oposicion", back_populates="examenes")
    detalles = relationship("DetalleExamen", back_populates="examen", cascade="all, delete-orphan")


class DetalleExamen(Base):
    __tablename__ = "detalles_examen"

    id = Column(Integer, primary_key=True, index=True)
    examen_id = Column(Integer, ForeignKey("examenes_realizados.id"))
    pregunta_id = Column(Integer, ForeignKey("preguntas.id"))

    tema = Column(String, index=True)
    resultado = Column(String)
    respuesta_usuario = Column(String, nullable=True)

    examen = relationship("ExamenRealizado", back_populates="detalles")
    pregunta = relationship("Pregunta")


class IntentoPruebaGratis(Base):
    """Un único simulacro de demostración, elegido y controlado por usuario."""
    __tablename__ = "intentos_prueba_gratis"
    __table_args__ = (UniqueConstraint("usuario_id", name="uq_intento_prueba_usuario"),)

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    oposicion_id = Column(Integer, ForeignKey("oposiciones.id"), nullable=False, index=True)
    preguntas_ids = Column(String, nullable=False)
    preguntas_generadas = Column(String, nullable=False)
    iniciada_en = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    finalizada_en = Column(DateTime, nullable=True)
    examen_id = Column(Integer, ForeignKey("examenes_realizados.id"), nullable=True, unique=True)

    usuario = relationship("Usuario")
    oposicion = relationship("Oposicion")
    examen = relationship("ExamenRealizado")
