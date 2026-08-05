import glob
import pandas as pd
from database import SessionLocal, engine
import models

# Asegura que las tablas estén creadas en la base de datos
models.Base.metadata.create_all(bind=engine)

def procesar_archivo_excel(ruta_archivo: str, db):
    print(f"📂 Abriendo archivo: {ruta_archivo}...")

    try:
        df = pd.read_excel(ruta_archivo)
    except Exception as e:
        print(f"❌ Error al leer el archivo {ruta_archivo}: {e}")
        return 0, 0

    contador_importadas = 0
    contador_saltadas = 0

    for index, fila in df.iterrows():
        # 1. Obtenemos el nombre de la oposición desde el Excel
        nombre_oposicion = fila.get('oposicion', 'Técnico y Cuadro Técnico ADIF')

        # 2. Buscamos si la oposición ya existe en la base de datos
        oposicion_db = db.query(models.Oposicion).filter(
            (models.Oposicion.nombre == nombre_oposicion) | (models.Oposicion.codigo == nombre_oposicion)
        ).first()

        # 3. Si no existe, la creamos automáticamente al vuelo
        if not oposicion_db:
            oposicion_db = models.Oposicion(
                nombre=nombre_oposicion,
                codigo=nombre_oposicion.lower().replace(" ", "_")
            )
            db.add(oposicion_db)
            db.commit()
            db.refresh(oposicion_db)
            print(f"✨ Oposición creada automáticamente en la BD: {nombre_oposicion}")

        enunciado_actual = fila['enunciado']

        # 4. Verificamos si la pregunta ya existe para esta oposición específica
        existe = db.query(models.Pregunta).filter(
            models.Pregunta.enunciado == enunciado_actual,
            models.Pregunta.oposicion_id == oposicion_db.id
        ).first()

        if existe:
            contador_saltadas += 1
            continue

        # 5. Creamos la pregunta vinculada a la oposición
        nueva_pregunta = models.Pregunta(
            oposicion_id=oposicion_db.id,
            rama_destino=fila.get('rama'),
            tema=fila['tema'],
            enunciado=fila['enunciado'],
            opcion_a=fila['opcion_a'],
            opcion_b=fila['opcion_b'],
            opcion_c=fila['opcion_c'],
            opcion_d=fila['opcion_d'],
            respuesta_correcta=fila['respuesta_correcta'],
            justificacion=fila['justificacion'],
            origen=fila.get('origen')
        )
        db.add(nueva_pregunta)
        contador_importadas += 1

    return contador_importadas, contador_saltadas


def importar_todos_los_archivos():
    # Patrón para buscar todos los archivos que empiecen por preguntas_adif_ y terminen en .xlsx
    patron = "preguntas_adif_*.xlsx"
    archivos = glob.glob(patron)

    if not archivos:
        print(f"⚠️ No se encontró ningún archivo que coincida con el patrón '{patron}' en la carpeta.")
        return

    print(f"🔍 Se han encontrado {len(archivos)} archivo(s) para importar:")
    for arch in archivos:
        print(f"   - {arch}")
    print("-" * 40)

    db = SessionLocal()
    total_nuevas = 0
    total_saltadas = 0

    try:
        for archivo in archivos:
            nuevas, saltadas = procesar_archivo_excel(archivo, db)
            total_nuevas += nuevas
            total_saltadas += saltadas
            print(f"   -> Añadidas: {nuevas} | Omitidas (duplicadas): {saltadas}\n")

        # Guardamos todos los cambios en la base de datos de forma global al terminar
        db.commit()
        print("=" * 40)
        print(f"✅ ¡Importación masiva finalizada con éxito!")
        print(f"   - Total de preguntas nuevas añadidas: {total_nuevas}")
        print(f"   - Total de duplicados omitidos: {total_saltadas}")
        print("=" * 40)

    except Exception as e:
        db.rollback()
        print(f"❌ Error crítico durante la importación masiva: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    importar_todos_los_archivos()