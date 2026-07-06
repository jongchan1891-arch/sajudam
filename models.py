# -*- coding: utf-8 -*-
"""데이터베이스 모델."""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    readings = db.relationship("SajuReading", backref="user", lazy=True)
    payments = db.relationship("Payment", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class SajuReading(db.Model):
    __tablename__ = "saju_readings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(100))
    birth_solar = db.Column(db.String(20))     # YYYY-MM-DD
    birth_hour = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10))
    palja = db.Column(db.String(40))           # 팔자 요약 (예: 경오 임오 신해 갑오)
    result_json = db.Column(db.Text)           # 전체 결과 JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    order_id = db.Column(db.String(64), unique=True, nullable=False)
    product_name = db.Column(db.String(120))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(20), default="READY")   # READY/DONE/FAILED/CANCELED
    payment_key = db.Column(db.String(200))
    method = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
