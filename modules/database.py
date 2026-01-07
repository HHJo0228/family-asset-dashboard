import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.models import Base
import os

DB_FILE = "assets.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for getting DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def initialize_sqlite_db():
    """
    Creates tables based on models.
    To be called on app startup or via migration script.
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    print(f"Database {DB_FILE} initialized.")
