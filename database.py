from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Le decimos que cree un archivo llamado 'aptotest.db' en esta misma carpeta
URL_BASE_DATOS = "sqlite:///./aptotest.db"

# Configuramos el motor (el check_same_thread es específico para que SQLite no de problemas en FastAPI)
engine = create_engine(
    URL_BASE_DATOS, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()