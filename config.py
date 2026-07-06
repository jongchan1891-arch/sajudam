# -*- coding: utf-8 -*-
"""애플리케이션 설정."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-saju-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "saju.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 토스페이먼츠 테스트(샌드박스) 키 — 공개된 테스트 키.
    # 실제 서비스 시 환경변수로 본인 키를 주입하세요.
    TOSS_CLIENT_KEY = os.environ.get(
        "TOSS_CLIENT_KEY", "test_ck_D5GePWvyJnrK0W0k6q8gLzN97Eoq"
    )
    TOSS_SECRET_KEY = os.environ.get(
        "TOSS_SECRET_KEY", "test_sk_zXLkKEypNArWmo50nX3lmeaxYG5R"
    )
    TOSS_CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
