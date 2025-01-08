# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    candidate_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    skills = db.Column(db.ARRAY(db.String))
    experience = db.Column(db.JSON)
    education = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
