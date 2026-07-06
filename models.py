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


class Product(db.Model):
    """풀이 상품 (US-014): 캐릭터가 진행하는 사주 풀이 상품."""
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    character_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    tagline = db.Column(db.String(200))                     # 한줄카피
    description = db.Column(db.Text)
    thumbnail = db.Column(db.String(200), nullable=True)    # static/img/products/ 파일명
    hero_image = db.Column(db.String(200), nullable=True)   # 상세페이지 배너
    category = db.Column(db.String(20), nullable=False, index=True)  # 연애/재물/종합/재회
    price = db.Column(db.Integer, nullable=False, default=0)         # 0 = 무료
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    readings = db.relationship("SajuReading", backref="product", lazy=True)
    reviews = db.relationship("Review", backref="product", lazy=True)


class Review(db.Model):
    """상품 리뷰 (US-018): 풀이를 받은 회원만 작성, 회원당 상품별 1개."""
    __tablename__ = "reviews"
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)          # 1~5
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref="reviews", lazy=True)


class SajuReading(db.Model):
    __tablename__ = "saju_readings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
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
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    order_id = db.Column(db.String(64), unique=True, nullable=False)
    product_name = db.Column(db.String(120))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(20), default="READY")   # READY/DONE/FAILED/CANCELED
    payment_key = db.Column(db.String(200))
    method = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
