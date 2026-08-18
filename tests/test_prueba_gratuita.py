from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
import models


def test_barajar_opciones_conserva_la_respuesta_correcta():
    pregunta = SimpleNamespace(
        id=1,
        enunciado="¿Cuál es la correcta?",
        tema="Tema de prueba",
        origen="Pruebas",
        justificacion="Porque sí",
        opcion_a="Correcta",
        opcion_b="Distractor B",
        opcion_c="Distractor C",
        opcion_d="Distractor D",
        respuesta_correcta="A",
    )

    resultado = main.barajar_opciones_pregunta(pregunta)

    assert {resultado["opcion_a"], resultado["opcion_b"], resultado["opcion_c"], resultado["opcion_d"]} == {
        "Correcta", "Distractor B", "Distractor C", "Distractor D",
    }
    assert resultado[f"opcion_{resultado['respuesta_correcta'].lower()}"] == "Correcta"


def crear_usuario_y_oposicion(client: TestClient, db):
    registro = client.post(
        "/api/registro",
        json={"nombre": "Ada", "email": "ada@example.com", "password": "secreto"},
    )
    assert registro.status_code == 200

    login = client.post("/api/login", json={"email": "ada@example.com", "password": "secreto"})
    assert login.status_code == 200
    usuario_id = login.json()["usuario"]["id"]

    oposicion = models.Oposicion(nombre="Factor de circulación", codigo="factor-circulacion")
    db.add(oposicion)
    db.flush()
    for numero in range(12):
        db.add(models.Pregunta(
            oposicion_id=oposicion.id,
            rama_destino="Común",
            tema="Normativa",
            enunciado=f"Pregunta {numero}",
            opcion_a="Respuesta A",
            opcion_b="Respuesta B",
            opcion_c="Respuesta C",
            opcion_d="Respuesta D",
            respuesta_correcta="A",
            justificacion="Justificación de prueba",
            origen="Banco de pruebas",
        ))
    db.commit()
    return usuario_id, oposicion


def test_prueba_gratuita_se_puede_reanudar_pero_solo_completar_una_vez(client, db):
    usuario_id, oposicion = crear_usuario_y_oposicion(client, db)

    estado_inicial = client.get(f"/api/prueba-gratuita/{usuario_id}/estado")
    assert estado_inicial.status_code == 200
    assert estado_inicial.json()["estado"] == "disponible"

    inicio = client.post(
        "/api/prueba-gratuita/iniciar",
        json={"usuario_id": usuario_id, "oposicion_id": oposicion.id},
    )
    assert inicio.status_code == 200
    prueba = inicio.json()
    assert prueba["reanudada"] is False
    assert len(prueba["preguntas"]) == 10

    reanudacion = client.post(
        "/api/prueba-gratuita/iniciar",
        json={"usuario_id": usuario_id, "oposicion_id": oposicion.id},
    )
    assert reanudacion.status_code == 200
    assert reanudacion.json()["reanudada"] is True
    assert reanudacion.json()["preguntas"] == prueba["preguntas"]

    respuestas = [
        {"pregunta_id": pregunta["id"], "respuesta_usuario": pregunta["respuesta_correcta"]}
        for pregunta in prueba["preguntas"]
    ]
    finalizacion = client.post(
        "/api/prueba-gratuita/finalizar",
        json={"usuario_id": usuario_id, "intento_id": prueba["intento_id"], "respuestas": respuestas},
    )
    assert finalizacion.status_code == 200
    assert finalizacion.json()["aciertos"] == 10
    assert finalizacion.json()["fallos"] == 0

    estado_final = client.get(f"/api/prueba-gratuita/{usuario_id}/estado")
    assert estado_final.json()["estado"] == "completada"

    segundo_intento = client.post(
        "/api/prueba-gratuita/iniciar",
        json={"usuario_id": usuario_id, "oposicion_id": oposicion.id},
    )
    assert segundo_intento.status_code == 409


def test_prueba_gratuita_no_se_ofrece_si_el_usuario_ya_tiene_acceso(client, db):
    usuario_id, oposicion = crear_usuario_y_oposicion(client, db)
    db.add(models.Suscripcion(
        usuario_id=usuario_id,
        oposicion_id=oposicion.id,
        stripe_subscription_id="sub_test_activa",
    ))
    db.commit()

    respuesta = client.post(
        "/api/prueba-gratuita/iniciar",
        json={"usuario_id": usuario_id, "oposicion_id": oposicion.id},
    )
    assert respuesta.status_code == 400
    assert "acceso completo" in respuesta.json()["detail"]
