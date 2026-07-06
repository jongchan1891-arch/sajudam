# -*- coding: utf-8 -*-
"""애플리케이션 설정."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _load_dotenv():
    """.env 파일이 있으면 환경변수로 로드 (이미 설정된 값은 우선)."""
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


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

    # 고민상담 (US-020) — 키는 환경변수/.env로만 주입. 코드·커밋에 절대 노출 금지.
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    GEMINI_API_KEY = ""  # 테스트는 항상 키 없는 환경 기준 (필요 시 개별 주입)
