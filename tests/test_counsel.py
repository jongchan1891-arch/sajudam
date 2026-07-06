# -*- coding: utf-8 -*-
"""달님 도령 고민상담 테스트 (US-020)."""
import pytest

from app import create_app
from config import TestConfig
from models import db, CounselLog
import counsel as counsel_module


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def _signup(client, email="a@b.com", pw="secret1"):
    return client.post("/signup", data={"email": email, "password": pw, "password2": pw},
                       follow_redirects=True)


def _ready(app):
    app.config["GEMINI_API_KEY"] = "test-key"


def _mock_gemini(monkeypatch, answer="달빛 아래 답장을 드립니다."):
    calls = []
    def fake(api_key, model, user_text, saju_context="", timeout=30):
        calls.append({"text": user_text, "ctx": saju_context})
        return True, answer
    monkeypatch.setattr(counsel_module, "call_gemini", fake)
    return calls


# ---- AC-9: 키 없는 환경에서도 서버 생존 + 준비 중 표시 ------------------
def test_no_key_page_alive_and_shows_notready(client):
    r = client.get("/counsel")
    assert r.status_code == 200
    assert "붓을 준비 중" in r.data.decode("utf-8")


def test_no_key_post_friendly(client):
    _signup(client)
    r = client.post("/counsel", data={"worry": "회사가 힘들어요"}, follow_redirects=True)
    assert r.status_code == 200
    assert "준비 중" in r.data.decode("utf-8")


# ---- AC-5: 남용 방지 ---------------------------------------------------
def test_requires_login(client, app):
    _ready(app)
    r = client.post("/counsel", data={"worry": "고민"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_max_length_rejected(client, app, monkeypatch):
    _ready(app)
    calls = _mock_gemini(monkeypatch)
    _signup(client)
    r = client.post("/counsel", data={"worry": "가" * 501}, follow_redirects=True)
    assert "500자 이내" in r.data.decode("utf-8")
    assert calls == []


def test_daily_limit_three(client, app, monkeypatch):
    _ready(app)
    calls = _mock_gemini(monkeypatch)
    _signup(client)
    for i in range(3):
        r = client.post("/counsel", data={"worry": f"고민 {i}"})
        assert "답장" in r.data.decode("utf-8")
    r = client.post("/counsel", data={"worry": "네 번째 고민"}, follow_redirects=True)
    assert "오늘의 상담은 여기까지" in r.data.decode("utf-8")
    assert len(calls) == 3
    with app.app_context():
        assert CounselLog.query.count() == 3


def test_api_error_friendly(client, app, monkeypatch):
    _ready(app)
    monkeypatch.setattr(counsel_module, "call_gemini", lambda *a, **k: (False, "boom"))
    _signup(client)
    r = client.post("/counsel", data={"worry": "고민이에요"}, follow_redirects=True)
    assert "붓이 잠시 멈췄" in r.data.decode("utf-8")
    with app.app_context():
        assert CounselLog.query.count() == 0     # 실패는 횟수 차감 없음


# ---- AC-4: 안전장치 (말투 규칙보다 우선) --------------------------------
def test_crisis_shows_hotlines_without_api_call(client, app, monkeypatch):
    _ready(app)
    calls = _mock_gemini(monkeypatch)
    _signup(client)
    r = client.post("/counsel", data={"worry": "요즘 너무 힘들어서 죽고 싶다는 생각이 들어요"})
    body = r.data.decode("utf-8")
    assert "109" in body
    assert "1577-0199" in body
    assert calls == []                            # API 호출 자체를 안 함
    with app.app_context():
        assert CounselLog.query.count() == 0      # 횟수 차감도 없음


def test_pro_help_notice_for_legal(client, app, monkeypatch):
    _ready(app)
    _mock_gemini(monkeypatch)
    _signup(client)
    r = client.post("/counsel", data={"worry": "전세금 문제로 집주인과 소송을 해야 할지 고민입니다"})
    assert "전문가와의 상담" in r.data.decode("utf-8")


# ---- AC-6: 고민 내용 미저장 ---------------------------------------------
def test_content_not_stored(client, app, monkeypatch):
    _ready(app)
    _mock_gemini(monkeypatch)
    _signup(client)
    secret = "아무에게도 말 못한 비밀 고민"
    client.post("/counsel", data={"worry": secret})
    with app.app_context():
        assert not hasattr(CounselLog, "content")            # 내용 컬럼 자체가 없음
        row = CounselLog.query.first()
        assert row is not None and set(c.name for c in row.__table__.columns) == {
            "id", "user_id", "created_at"}


# ---- AC-7/8/8-1: UI 요소 -------------------------------------------------
def test_answer_ui_disclaimer_and_banner(client, app, monkeypatch):
    _ready(app)
    _mock_gemini(monkeypatch)
    _signup(client)
    r = client.post("/counsel", data={"worry": "친구와 사이가 멀어졌어요"})
    body = r.data.decode("utf-8")
    assert "달님 도령의 답장" in body
    assert "dalnim_profile.jpg" in body
    assert "전문 상담을 대체하지 않습니다" in body
    assert body.count("ads-partners.coupang.com/g.js") == 1          # 답변 후에만 배너
    assert "쿠팡 파트너스 활동의 일환" in body                        # 고지 문구
    assert "/product/jaerok-money" not in body                       # 재물 고민 아님


def test_form_view_has_no_banner(client, app):
    _ready(app)
    _signup(client)
    body = client.get("/counsel").data.decode("utf-8")
    assert "coupang" not in body.lower()


def test_money_worry_shows_funnel(client, app, monkeypatch):
    _ready(app)
    _mock_gemini(monkeypatch)
    _signup(client)
    r = client.post("/counsel", data={"worry": "월급은 그대로인데 대출 이자가 늘어서 걱정이에요"})
    body = r.data.decode("utf-8")
    assert "/product/jaerok-money" in body
    assert "재물 고민이라면" in body


def test_saju_context_personalization(client, app, monkeypatch):
    _ready(app)
    calls = _mock_gemini(monkeypatch)
    _signup(client)
    client.post("/calculate", data={
        "name": "나", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=True)
    client.post("/counsel", data={"worry": "요즘 잠이 안 와요"})
    assert len(calls) == 1
    assert "일간" in calls[0]["ctx"] and "신" in calls[0]["ctx"]     # 사주 컨텍스트 전달


def test_home_has_counsel_entrance(client):
    body = client.get("/").data.decode("utf-8")
    assert "달님 도령의 고민상담" in body
    assert "달이 지기 전에 들어드립니다" in body
    assert "dalnim_banner.jpg" in body
    # 오늘의 운세 섹션 아래 배치
    assert body.index("fortune-strip") < body.index("counsel-strip")
