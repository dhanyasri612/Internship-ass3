# models.py
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(120), unique=True, nullable=False)
    email = Column(String(256), nullable=False)
    password_hash = Column(String(256), nullable=False)
    slack_destination = Column(String(256), nullable=True)  # channel or user id
    google_sheet_name = Column(String(256), nullable=True)   # spreadsheet name
    created_at = Column(DateTime, server_default=func.now())
    # created_at tracks when the user was added
class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, nullable=False)
    value = Column(String(1024), nullable=True)
