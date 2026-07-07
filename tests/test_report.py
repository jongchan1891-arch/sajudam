# -*- coding: utf-8 -*-
"""US-022: 유료 풀이 Gemini 장문 리포트 테스트 (Gemini 모킹)."""
import json

import pytest

from app import create_app
from config import TestConfig
from models import db, SajuReading, SajuReport
import payment as payment_module
import report_service

SECTION_KEYS = ["grit", "inflow", "leak", "timing", "rx"]


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


def _calc(client, slug=None):
    data = {
        "name": "홍길동", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }
    if slug:
        data["product"] = slug
    return client.post("/calculate", data=data, follow_redirects=True)


def _pay_done(client, app, monkeypatch, slug):
    client.get(f"/payment/checkout?product={slug}")
    with app.app_context():
        from models import Payment
        pay = Payment.query.filter_by(status="READY").order_by(Payment.id.desc()).first()
        order_id, amount = pay.order_id, pay.amount
    monkeypatch.setattr(payment_module, "confirm_payment",
                        lambda *a, **k: (True, {"method": "카드"}))
    client.get(f"/payment/success?paymentKey=pk_t&orderId={order_id}&amount={amount}",
               follow_redirects=True)


def _mock_gemini(monkeypatch, body_len=450, fail=False):
    """_call_gemini_json 모킹. 호출 횟수 카운터 반환."""
    calls = {"n": 0}
    filler = "곳간의 흐름을 살펴보니 강한 기운이 길을 내고 있습니다. " * 60

    def fake(api_key, model, system_prompt, user_prompt, timeout=90):
        calls["n"] += 1
        if fail:
            return False, "mock api error"
        return True, {k: filler[:body_len] for k in SECTION_KEYS}

    monkeypatch.setattr(report_service, "_call_gemini_json", fake)
    return calls


def _last_reading_id(app):
    with app.app_context():
        return SajuReading.query.order_by(SajuReading.id.desc()).first().id


# ---- 생성/저장 -----------------------------------------------------------

def test_paid_calc_creates_done_report(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    _mock_gemini(monkeypatch)
    body = _calc(client, "jaerok-money").data.decode("utf-8")

    assert "타고난 재물 그릇" in body
    assert "재록 선생의 처방" in body
    assert "인쇄 / 저장" in body
    # 인쇄 미지원 브라우저(삼성 인터넷·인앱) 대응: 버튼 스크립트 + 대체 안내
    assert 'id="print-btn"' in body
    assert 'id="print-help"' in body
    assert "SamsungBrowser" in body
    with app.app_context():
        report = SajuReport.query.one()
        assert report.status == "DONE"
        sections = json.loads(report.content_json)["sections"]
        assert [s["key"] for s in sections] == SECTION_KEYS
        assert sum(len(s["body"]) for s in sections) >= 1500


def test_report_page_has_palja_and_ohaeng(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    _mock_gemini(monkeypatch)
    body = _calc(client, "jaerok-money").data.decode("utf-8")
    assert "사주 원국" in body and "오행 분석" in body   # 기존 표/그래프 재활용


def test_other_paid_product_uses_own_persona(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "yeonhwa-love")
    _mock_gemini(monkeypatch)
    body = _calc(client, "yeonhwa-love").data.decode("utf-8")
    assert "타고난 인연의 결" in body
    assert "연화의 처방" in body


# ---- 재조회: 저장본 재사용 (재호출 금지) ---------------------------------

def test_stored_report_not_regenerated(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    calls = _mock_gemini(monkeypatch)
    _calc(client, "jaerok-money")
    assert calls["n"] == 1
    rid = _last_reading_id(app)

    for _ in range(2):
        body = client.get(f"/reading/{rid}").data.decode("utf-8")
        assert "타고난 재물 그릇" in body
    assert calls["n"] == 1                     # 저장본 표시 — Gemini 재호출 없음


# ---- 실패 처리: 생성 중 + 재시도 -----------------------------------------

def test_failure_keeps_pending_with_retry(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    _mock_gemini(monkeypatch, fail=True)
    body = _calc(client, "jaerok-money").data.decode("utf-8")

    assert "리포트 다시 생성하기" in body       # 돈 받고 빈 화면 금지
    with app.app_context():
        assert SajuReport.query.one().status == "PENDING"


def test_retry_completes_report(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    _mock_gemini(monkeypatch, fail=True)
    _calc(client, "jaerok-money")
    rid = _last_reading_id(app)

    _mock_gemini(monkeypatch)                   # 이번엔 성공
    body = client.post(f"/reading/{rid}/report", follow_redirects=True).data.decode("utf-8")
    assert "타고난 재물 그릇" in body
    with app.app_context():
        assert SajuReport.query.one().status == "DONE"


def test_too_short_response_treated_as_failure(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    _mock_gemini(monkeypatch, body_len=120)     # 총 600자 < 1500자
    _calc(client, "jaerok-money")
    with app.app_context():
        assert SajuReport.query.one().status == "PENDING"


def test_retry_owner_only(client, app, monkeypatch):
    _signup(client, "owner@b.com")
    _pay_done(client, app, monkeypatch, "jaerok-money")
    calls = _mock_gemini(monkeypatch, fail=True)
    _calc(client, "jaerok-money")
    rid = _last_reading_id(app)
    n_before = calls["n"]

    client.get("/logout")
    _signup(client, "intruder@b.com")
    resp = client.post(f"/reading/{rid}/report")
    assert resp.status_code == 302 and "/mypage" in resp.headers["Location"]
    assert calls["n"] == n_before               # 타인 요청으로 생성 시도 안 함


# ---- 무료 풀이 불변 -------------------------------------------------------

def test_free_product_unchanged(client, app, monkeypatch):
    calls = _mock_gemini(monkeypatch)
    body = _calc(client, "jaerok-free").data.decode("utf-8")
    assert "심층풀이에서" in body               # 기존 무료 아웃트로 유지
    assert "타고난 재물 그릇" not in body
    assert calls["n"] == 0
    with app.app_context():
        assert SajuReport.query.count() == 0


# ---- 설정 무결성 ----------------------------------------------------------

def test_all_paid_products_have_config():
    assert set(report_service.REPORT_CONFIGS) == {
        "jaerok-money", "yeonhwa-love", "wolha-rejoin", "premium-total",
    }
    for slug, cfg in report_service.REPORT_CONFIGS.items():
        assert [k for k, _t, _g in cfg["sections"]] == SECTION_KEYS, slug
        assert cfg["min_chars"] >= 1500
    assert report_service.REPORT_CONFIGS["premium-total"]["min_chars"] >= 2000
