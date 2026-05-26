from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from prompt_ops.config import settings
from prompt_ops.database.models import Base

engine = None
SessionLocal = None

def init_database() -> None:
    global engine, SessionLocal
    if engine is not None:
        return
    
    # Ensure DB directory exists if sqlite
    if settings.db_url.startswith("sqlite"):
        db_path = settings.db_url.replace("sqlite:///", "")
        db_path = db_path.replace("sqlite://", "") # in case it's sqlite://foo.db vs sqlite:///foo.db
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            
    engine = create_engine(settings.db_url, connect_args={"check_same_thread": False} if settings.db_url.startswith("sqlite") else {})
    Base.metadata.create_all(bind=engine)
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_session():
    if SessionLocal is None:
        init_database()
    return SessionLocal()
