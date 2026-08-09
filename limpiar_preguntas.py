from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

# ⚠️ IMPORTANTE: Copia aquí la MISMA URL exacta que tienes en tu importador.py (la del puerto 6543)
DATABASE_URL = "postgresql://postgres.ihtacxwbucbsagphtryo:7lJyPHWQ90jmaoG9@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def vaciar_preguntas():
    print("⚠️ ATENCIÓN: Estás conectado a la base de datos de PRODUCCIÓN (Supabase).")
    print("Esta acción borrará TODAS las preguntas almacenadas de forma irreversible.")

    confirmacion = input("\n¿Estás completamente seguro? Escribe 'borrar' para confirmar: ")

    if confirmacion.lower() != 'borrar':
        print("❌ Operación cancelada. No se ha borrado nada.")
        return

    db = SessionLocal()
    try:
        # Contamos cuántas hay antes de borrar para el informe final
        total_preguntas_antes = db.query(models.Pregunta).count()

        # Ejecutamos el borrado masivo
        filas_borradas = db.query(models.Pregunta).delete()

        # Si también quieres borrar las oposiciones (descomenta las siguientes 2 líneas):
        # oposiciones_borradas = db.query(models.Oposicion).delete()
        # print(f"También se eliminaron {oposiciones_borradas} oposiciones.")

        db.commit()
        print("=" * 40)
        print(f"✅ ¡Limpieza completada con éxito!")
        print(f"   - Se han eliminado {filas_borradas} preguntas.")
        print("=" * 40)

    except Exception as e:
        db.rollback()
        print(f"❌ Error crítico durante el borrado: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    vaciar_preguntas()