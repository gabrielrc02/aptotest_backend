from fastapi import FastAPI, Depends, HTTPException, status, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import Optional, List
from pydantic import BaseModel
from passlib.context import CryptContext
import stripe
import random

import models
from database import engine, SessionLocal
import os
from dotenv import load_dotenv

# Configura la clave leyendo la variable de entorno
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = "price_1U0RZlDyM24mNBUXuDyVBgzJ"  # Pega aquí tu ID de Stripe
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Define la URL base del frontend usando un valor por defecto para local
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Esto crea físicamente el archivo de base de datos y las tablas si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AptoTest ADIF API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que cualquier web se conecte (luego en producción pondremos tu dominio real)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependencia para obtener la sesión de la base de datos en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# NUEVO: Modelo de Pydantic para validar los datos que envía el frontend al registrarse
class UsuarioRegistro(BaseModel):
    nombre: str
    email: str
    password: str

class RegistroSchema(BaseModel):
    nombre: str
    email: str
    password: str


def barajar_opciones_pregunta(pregunta):
    # Guardamos las opciones originales con sus letras asociadas
    opciones = [
        ('A', pregunta.opcion_a),
        ('B', pregunta.opcion_b),
        ('C', pregunta.opcion_c),
        ('D', pregunta.opcion_d)
    ]

    correcta_original = pregunta.respuesta_correcta

    # Barajamos el orden de las opciones de forma aleatoria
    random.shuffle(opciones)

    letras = ['A', 'B', 'C', 'D']
    nueva_respuesta = ''

    # Creamos un diccionario o estructura con las nuevas posiciones
    resultado = {
        "id": pregunta.id,
        "enunciado": pregunta.enunciado,
        "tema": pregunta.tema,
        "origen": pregunta.origen,
        "justificacion": pregunta.justificacion,
    }

    for i, (letra_vieja, texto) in enumerate(opciones):
        nueva_letra = letras[i]
        resultado[f"opcion_{nueva_letra.lower()}"] = texto

        # Si esta opción era la correcta original, guardamos su nueva letra asignada
        if letra_vieja == correcta_original:
            nueva_respuesta = nueva_letra

    resultado["respuesta_correcta"] = nueva_respuesta
    return resultado


# NUEVO: Endpoint de Registro
@app.post("/api/registro")
def registrar_usuario(datos: RegistroSchema, db: Session = Depends(get_db)):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == datos.email).first()
    if usuario_existente:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    nuevo_usuario = models.Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password=datos.password
    )
    # Sin oposiciones asignadas al nacer
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return {"mensaje": "Usuario registrado con éxito"}


# NUEVO: Modelo para los datos que nos enviarán al hacer login
class UsuarioLogin(BaseModel):
    email: str
    password: str


# NUEVO: Endpoint de Login
@app.post("/api/login")
def iniciar_sesion(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    # 1. Buscar al usuario en la base de datos por su email
    db_user = db.query(models.Usuario).filter(models.Usuario.email == usuario.email).first()

    # 2. Si no existe el usuario, o si la contraseña no coincide...
    # (Usamos pwd_context.verify para comparar la contraseña plana con el hash guardado)
    if not db_user or db_user.password != usuario.password:  # O usando verify si usas passlib
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")

    # 3. Si todo es correcto, le damos acceso
    return {
        "mensaje": "¡Login correcto!",
        "usuario": {
            "id": db_user.id,
            "nombre": db_user.nombre,
            "email": db_user.email
        }
    }


@app.get("/api/temas")
def obtener_temas(oposicion_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Pregunta.rama_destino, models.Pregunta.tema)
    if oposicion_id:
        query = query.filter(models.Pregunta.oposicion_id == oposicion_id)

    resultados = query.distinct().all()

    agrupados = {}
    for rama, tema in resultados:
        rama_key = rama if rama else "Común"
        if tema:
            if rama_key not in agrupados:
                agrupados[rama_key] = []
            if tema not in agrupados[rama_key]:
                agrupados[rama_key].append(tema)

    return agrupados


@app.get("/")
def inicio():
    return {"mensaje": "Servidor y Base de Datos de ADIF conectados correctamente 🚀"}


# Endpoint para insertar una pregunta de prueba
@app.post("/api/crear-pregunta-prueba")
def crear_pregunta_prueba(db: Session = Depends(get_db)):
    # Comprobamos si ya existe para no duplicarla
    existe = db.query(models.Pregunta).first()
    if existe:
        return {"mensaje": "Ya hay preguntas en la base de datos."}

    # Creamos una pregunta de ejemplo basada en el temario de ADIF
    nueva_pregunta = models.Pregunta(
        tema="Estatuto ADIF",
        enunciado="¿A quién corresponde la aprobación del Estatuto de ADIF?",
        opcion_a="Al Ministerio de Transportes",
        opcion_b="Al Presidente de ADIF",
        opcion_c="Al Consejo de Ministros",
        opcion_d="A las Cortes Generales",
        respuesta_correcta="C",
        justificacion="Art. 1.3 RD 2395/2004: Los estatutos se aprobarán por Real Decreto del Consejo de Ministros.",
        rama_destino="Común"
    )

    db.add(nueva_pregunta)
    db.commit()
    db.refresh(nueva_pregunta)

    return {"mensaje": "¡Pregunta de prueba creada con éxito!", "pregunta_id": nueva_pregunta.id}


# Endpoint para ver todas las preguntas guardadas
@app.get("/api/preguntas")
def listar_preguntas(db: Session = Depends(get_db)):
    preguntas = db.query(models.Pregunta).all()
    return preguntas


# ACTUALIZADO: Endpoint para generar test con filtro opcional de temas
# 6. ACTUALIZADO: Generar test filtrando por la Oposición Activa
@app.get("/api/generar-test")
def generar_test(
        cantidad: int = 10,
        oposicion_id: int = None,
        temas: list[str] = Query(None),
        origenes: list[str] = Query(None),  # <--- Nuevo parámetro opcional
        db: Session = Depends(get_db)
):
    query = db.query(models.Pregunta)
    if oposicion_id:
        query = query.filter(models.Pregunta.oposicion_id == oposicion_id)
    if temas:
        query = query.filter(models.Pregunta.tema.in_(temas))
    if origenes:  # <--- Nuevo filtro por origen
        query = query.filter(models.Pregunta.origen.in_(origenes))

    preguntas_db = query.all()

    if not preguntas_db:
        raise HTTPException(status_code=404, detail="No hay preguntas que coincidan con los filtros seleccionados.")

    seleccionadas = random.sample(preguntas_db, min(len(preguntas_db), cantidad))
    preguntas_barajadas = [barajar_opciones_pregunta(p) for p in seleccionadas]

    return {"preguntas": preguntas_barajadas}

# NUEVO: Modelos para recibir los datos del examen desde el frontend
class DetalleExamenSchema(BaseModel):
    pregunta_id: int
    tema: str
    resultado: str  # Esperamos recibir "acierto", "fallo" o "blanco"
    respuesta_usuario: Optional[str] = None


class GuardarExamenSchema(BaseModel):
    usuario_id: int
    oposicion_id: Optional[int] = None
    aciertos: int
    fallos: int
    blancos: int
    detalles: List[DetalleExamenSchema]  # Una lista con el desglose


# 7. ACTUALIZADO: Guardar examen asignándole la oposición activa
@app.post("/api/guardar-examen")
def guardar_examen(datos: GuardarExamenSchema, db: Session = Depends(get_db)):
    nota_calculada = round(max(0.0, datos.aciertos - (datos.fallos / 3)), 2)
    nuevo_examen = models.ExamenRealizado(
        usuario_id=datos.usuario_id,
        oposicion_id=datos.oposicion_id,
        aciertos=datos.aciertos,
        fallos=datos.fallos,
        nota=nota_calculada,
        blancos=datos.blancos
    )
    db.add(nuevo_examen)
    db.commit()
    db.refresh(nuevo_examen)

    for detalle in datos.detalles:
        nuevo_detalle = models.DetalleExamen(
            examen_id=nuevo_examen.id,
            pregunta_id=detalle.pregunta_id,
            tema=detalle.tema,
            resultado=detalle.resultado,
            respuesta_usuario=detalle.respuesta_usuario
        )
        db.add(nuevo_detalle)

    db.commit()
    return {"mensaje": "Examen guardado con éxito", "examen_id": nuevo_examen.id}


# 8. ACTUALIZADO: Estadísticas filtradas por oposición activa
@app.get("/api/estadisticas/{usuario_id}")
def obtener_estadisticas(usuario_id: int, oposicion_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.ExamenRealizado).filter(models.ExamenRealizado.usuario_id == usuario_id)
    if oposicion_id:
        query = query.filter(models.ExamenRealizado.oposicion_id == oposicion_id)

    examenes = query.all()

    if not examenes:
        return {
            "total_examenes": 0, "aciertos_totales": 0, "fallos_totales": 0, "blancos_totales": 0, "por_tema": {}
        }

    total_examenes = len(examenes)
    aciertos_totales = sum(e.aciertos for e in examenes)
    fallos_totales = sum(e.fallos for e in examenes)
    blancos_totales = sum(e.blancos for e in examenes)

    examen_ids = [e.id for e in examenes]
    detalles = db.query(models.DetalleExamen).filter(models.DetalleExamen.examen_id.in_(examen_ids)).all()

    temas_stats = {}
    for d in detalles:
        tema = d.tema
        if tema not in temas_stats:
            temas_stats[tema] = {"total": 0, "aciertos": 0}
        temas_stats[tema]["total"] += 1
        if d.resultado == "acierto":
            temas_stats[tema]["aciertos"] += 1

    resultado_temas = {}
    for tema, stats in temas_stats.items():
        total = stats["total"]
        aciertos = stats["aciertos"]
        porcentaje = round((aciertos / total) * 100, 1) if total > 0 else 0
        resultado_temas[tema] = {
            "total_preguntas": total,
            "aciertos": aciertos,
            "porcentaje": porcentaje
        }

    return {
        "total_examenes": total_examenes,
        "aciertos_totales": aciertos_totales,
        "fallos_totales": fallos_totales,
        "blancos_totales": blancos_totales,
        "por_tema": resultado_temas
    }


@app.get("/api/generar-test-fallos/{usuario_id}")
def generar_test_fallos(usuario_id: int, cantidad: int = 10, db: Session = Depends(get_db)):
    # 1. Buscar los IDs de las preguntas que este usuario ha fallado en el pasado
    ids_falladas = (
        db.query(models.DetalleExamen.pregunta_id)
        .join(models.ExamenRealizado)
        .filter(models.ExamenRealizado.usuario_id == usuario_id)
        .filter(models.DetalleExamen.resultado == "fallo")
        .distinct()
        .all()
    )

    # Convertimos el resultado de SQLAlchemy en una lista limpia de IDs (ej: [4, 12, 33])
    lista_ids = [item[0] for item in ids_falladas]

    if not lista_ids:
        return {"error": "¡Increíble! No tienes preguntas falladas registradas o aún no has hecho ningún test."}

    # 2. Buscar las preguntas reales en la tabla de preguntas usando esos IDs
    preguntas = (
        db.query(models.Pregunta)
        .filter(models.Pregunta.id.in_(lista_ids))
        .order_by(func.random())
        .limit(cantidad)
        .all()
    )

    preguntas_barajadas = [barajar_opciones_pregunta(p) for p in preguntas]
    return {"preguntas": preguntas_barajadas}


# 9. ACTUALIZADO: Historial filtrado por oposición activa
@app.get("/api/historial-examenes/{usuario_id}")
def obtener_historial_examenes(usuario_id: int, oposicion_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.ExamenRealizado).filter(models.ExamenRealizado.usuario_id == usuario_id)
    if oposicion_id:
        query = query.filter(models.ExamenRealizado.oposicion_id == oposicion_id)

    examenes = query.order_by(models.ExamenRealizado.fecha.desc()).all()

    historial = []
    for e in examenes:
        historial.append({
            "id": e.id,
            "fecha": e.fecha.strftime("%d/%m/%Y a las %H:%M") if e.fecha else "",
            "aciertos": e.aciertos,
            "fallos": e.fallos,
            "blancos": e.blancos,
            "nota": e.nota
        })
    return historial


@app.get("/api/examen-detalle/{examen_id}")
def obtener_detalle_examen(examen_id: int, db: Session = Depends(get_db)):
    examen = db.query(models.ExamenRealizado).filter(models.ExamenRealizado.id == examen_id).first()
    if not examen:
        raise HTTPException(status_code=404, detail="Examen no encontrado")

    detalles_query = (
        db.query(models.DetalleExamen, models.Pregunta)
        .join(models.Pregunta, models.DetalleExamen.pregunta_id == models.Pregunta.id)
        .filter(models.DetalleExamen.examen_id == examen_id)
        .all()
    )

    preguntas_detalle = []
    for detalle, pregunta in detalles_query:
        preguntas_detalle.append({
            "id": pregunta.id,
            "tema": pregunta.tema,
            "enunciado": pregunta.enunciado,
            "opcion_a": pregunta.opcion_a,
            "opcion_b": pregunta.opcion_b,
            "opcion_c": pregunta.opcion_c,
            "opcion_d": pregunta.opcion_d,
            "respuesta_correcta": pregunta.respuesta_correcta,
            "justificacion": pregunta.justificacion,
            "resultado": detalle.resultado,
            "respuesta_usuario": detalle.respuesta_usuario,  # NUEVO
            "origen": detalle.pregunta.origen
        })

    return {
        "id": examen.id,
        "fecha": examen.fecha.strftime("%d/%m/%Y a las %H:%M") if examen.fecha else "",
        "aciertos": examen.aciertos,
        "fallos": examen.fallos,
        "blancos": examen.blancos,
        "nota": examen.nota,
        "preguntas": preguntas_detalle
    }


# 2. NUEVO: Listar todas las oposiciones disponibles en el catálogo de la academia
@app.get("/api/oposiciones-disponibles")
def listar_oposiciones_disponibles(db: Session = Depends(get_db)):
    oposiciones = db.query(models.Oposicion).all()
    return [{"id": op.id, "nombre": op.nombre, "codigo": op.codigo} for op in oposiciones]


# 3. NUEVO: Comprar / Asignar una oposición a un usuario
class ComprarOposicionSchema(BaseModel):
    oposicion_id: int


@app.post("/api/usuario/{usuario_id}/comprar-oposicion")
def comprar_oposicion(usuario_id: int, datos: ComprarOposicionSchema, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    oposicion = db.query(models.Oposicion).filter(models.Oposicion.id == datos.oposicion_id).first()

    if not usuario or not oposicion:
        raise HTTPException(status_code=404, detail="Usuario u Oposición no encontrados")

    if oposicion in usuario.oposiciones:
        raise HTTPException(status_code=400, detail="Ya tienes contratada esta oposición")

    usuario.oposiciones.append(oposicion)
    db.commit()
    return {"mensaje": "¡Oposición contratada con éxito!"}


# 4. Listar las oposiciones contratadas del usuario
@app.get("/api/usuario/{usuario_id}/oposiciones")
def obtener_oposiciones_usuario(usuario_id: int, db: Session = Depends(get_db)):
    suscripciones = db.query(models.Suscripcion).filter(models.Suscripcion.usuario_id == usuario_id).all()

    resultado = []
    for sub in suscripciones:
        resultado.append({
            "id": sub.oposicion.id,
            "nombre": sub.oposicion.nombre,
            "cancel_at_period_end": sub.cancel_at_period_end  # <--- Enviamos el estado individual
        })
    return resultado


# 1. Endpoint para generar la pasarela de pago de Stripe
@app.post("/api/crear-checkout-session")
def crear_checkout_session(datos: dict, db: Session = Depends(get_db)):
    usuario_id = datos.get("usuario_id")
    oposicion_id = datos.get("oposicion_id")

    # Comprobamos que la oposición exista
    oposicion = db.query(models.Oposicion).filter(models.Oposicion.id == oposicion_id).first()
    if not oposicion:
        raise HTTPException(status_code=404, detail="Oposición no encontrada")

    try:
        # Creamos la sesión de pago usando el precio único global
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,  # <--- Precio único para cualquier oposición
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{FRONTEND_URL}/?pago=exito",
            cancel_url=f"{FRONTEND_URL}/?pago=cancelado",
            client_reference_id=str(usuario_id),
            metadata={
                'usuario_id': str(usuario_id),
                'oposicion_id': str(oposicion_id)
            }
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 2. Webhook: Stripe llama a este endpoint automáticamente cuando ocurren eventos
@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        print(f"❌ Payload inválido: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Error de firma de webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    print(f"🔔 Evento de Stripe recibido y verificado: {event['type']}")
    data_object = event['data']['object']
    session_dict = data_object.to_dict() if hasattr(data_object, 'to_dict') else dict(data_object)

    # EVENTO 1: Cuando se completa el pago de la suscripción
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        session_dict = session.to_dict() if hasattr(session, 'to_dict') else dict(session)
        metadata = session_dict.get('metadata', {})

        usuario_id = int(metadata.get('usuario_id'))
        oposicion_id = int(metadata.get('oposicion_id'))
        subscription_id = session_dict.get('subscription')

        if usuario_id and oposicion_id and subscription_id:
            # Creamos un registro de suscripción independiente
            nueva_suscripcion = models.Suscripcion(
                usuario_id=usuario_id,
                oposicion_id=oposicion_id,
                stripe_subscription_id=subscription_id,
                cancel_at_period_end=False
            )
            db.add(nueva_suscripcion)
            db.commit()
            print(f"✅ Suscripción {subscription_id} creada para usuario {usuario_id} y oposición {oposicion_id}")

    elif event['type'] == 'customer.subscription.deleted':
        sub_id = session_dict.get('id')

        # Buscamos la suscripción exacta que ha expirado y la eliminamos
        suscripcion = db.query(models.Suscripcion).filter(models.Suscripcion.stripe_subscription_id == sub_id).first()
        if suscripcion:
            db.delete(suscripcion)
            db.commit()
            print(f"❌ Suscripción {sub_id} eliminada definitivamente.")

    return {"status": "success"}


@app.post("/api/cancelar-suscripcion")
def cancelar_suscripcion(datos: dict, db: Session = Depends(get_db)):
    usuario_id = datos.get("usuario_id")
    oposicion_id = datos.get("oposicion_id")  # <--- Recibimos qué oposición quiere cancelar

    suscripcion = db.query(models.Suscripcion).filter(
        models.Suscripcion.usuario_id == usuario_id,
        models.Suscripcion.oposicion_id == oposicion_id
    ).first()

    if not suscripcion:
        raise HTTPException(status_code=404, detail="No se encontró una suscripción activa para esta oposición")

    try:
        # Modificamos la suscripción específica en Stripe
        stripe.Subscription.modify(
            suscripcion.stripe_subscription_id,
            cancel_at_period_end=True
        )

        # Actualizamos el estado solo para esta oposición
        suscripcion.cancel_at_period_end = True
        db.commit()

        return {
            "status": "success",
            "message": "La suscripción de esta oposición no se renovará. Mantendrás el acceso hasta el final del periodo actual."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/origenes")
def obtener_origenes(oposicion_id: int, db: Session = Depends(get_db)):
    # Obtenemos todos los orígenes únicos que no sean nulos para esta oposición
    origenes = db.query(models.Pregunta.origen).filter(
        models.Pregunta.oposicion_id == oposicion_id,
        models.Pregunta.origen != None,
        models.Pregunta.origen != ""
    ).distinct().all()

    return [o[0] for o in origenes]