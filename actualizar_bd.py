from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        # Añadimos la columna directamente a SQLite
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN stripe_subscription_id VARCHAR;"))
        conn.commit()
        print("✅ Columna 'stripe_subscription_id' añadida con éxito a la base de datos.")
    except Exception as e:
        print(f"ℹ️ Aviso o error (puede que ya existiera): {e}")