from database import SessionLocal
import models

db = SessionLocal()

# Comprobamos si ya existe alguna oposición
existe = db.query(models.Oposicion).first()
if not existe:
    # Creamos la oposición oficial de ADIF
    op_adif = models.Oposicion(
        nombre="Técnico y Cuadro Técnico ADIF",
        codigo="tecnico_adif",
        categoria="ADIF",
        subcategoria="Técnico"
    )
    db.add(op_adif)
    db.commit()
    print("✅ Oposición 'Técnico y Cuadro Técnico ADIF' creada con éxito.")
else:
    print("ℹ️ La oposición ya existía en la base de datos.")

db.close()
