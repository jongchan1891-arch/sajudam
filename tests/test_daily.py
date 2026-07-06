# -*- coding: utf-8 -*-
"""오늘의 운세 테스트 (US-019)."""
from datetime import date

import pytest

from app import create_app
from config import TestConfig
from models import db
from saju import daily
from saju.daily import compute_daily_fortune


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


# ---- 결정성 (AC-핵심: 랜덤 금지) --------------------------------------
def test_same_birth_same_date_same_result():
    a = compute_daily_fortune(1990, 6, 15, date(2026, 7, 7))
    b = compute_daily_fortune(1990, 6, 15, date(2026, 7, 7))
    assert a == b


def test_route_repeat_query_identical(client):
    r1 = client.get("/today?y=1990&m=6&d=15").data
    r2 = client.get("/today?y=1990&m=6&d=15").data
    assert r1 == r2


def test_different_dates_vary():
    results = {
        compute_daily_fortune(1990, 6, 15, date(2026, 7, d))["summary"]
        for d in range(1, 11)
    }
    assert len(results) >= 3  # 열흘 동안 최소 3가지 이상 다른 한줄평


def test_different_births_vary():
    a = compute_daily_fortune(1990, 6, 15, date(2026, 7, 7))
    b = compute_daily_fortune(1993, 1, 2, date(2026, 7, 7))
    assert a["user_ilgan"] != b["user_ilgan"] or a["summary"] != b["summary"]


# ---- 구성 (총운/별점/카테고리/조언) ------------------------------------
def test_fortune_structure():
    f = compute_daily_fortune(1990, 6, 15, date(2026, 7, 7))
    assert 1 <= f["score"] <= 5
    assert f["stars"].count("★") == f["score"]
    assert len(f["stars"]) == 5
    assert f["summary"] and f["advice"]
    for cat in ["재물", "애정", "건강"]:
        c = f["categories"][cat]
        assert 1 <= c["score"] <= 5 and c["text"]
    assert f["today_gapja"]
    assert f["user_ilgan"] == "신"  # 1990-06-15 = 신해일


def test_text_pools_are_rich():
    assert len(daily.SUMMARY_HIGH) + len(daily.SUMMARY_MID) + len(daily.SUMMARY_LOW) >= 30
    assert len(daily.MONEY_HIGH) + len(daily.MONEY_MID) + len(daily.MONEY_LOW) >= 20
    assert len(daily.LOVE_HIGH) + len(daily.LOVE_MID) + len(daily.LOVE_LOW) >= 20
    assert len(daily.HEALTH_HIGH) + len(daily.HEALTH_MID) + len(daily.HEALTH_LOW) >= 20
    assert len(daily.ADVICE_POOL) >= 20


# ---- 접근 (비회원 1회 조회 / 회원 자동) --------------------------------
def test_guest_sees_form_then_result(client):
    body = client.get("/today").data.decode("utf-8")
    assert "생년월일 입력" in body
    body = client.get("/today?y=1990&m=6&d=15").data.decode("utf-8")
    assert "오늘의 조언" in body
    assert "★" in body


def test_invalid_birth_redirects(client):
    r = client.get("/today?y=1990&m=13&d=99", follow_redirects=True)
    assert "생년월일을 확인해 주세요" in r.data.decode("utf-8")


def test_member_home_shows_fortune_preview(client):
    _signup(client)
    client.post("/calculate", data={
        "name": "나", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=True)
    body = client.get("/").data.decode("utf-8")
    assert "오늘의" in body and "운세" in body
    assert "★" in body                       # 별점 미리보기
    body = client.get("/today").data.decode("utf-8")
    assert "오늘의 조언" in body              # 입력 없이 바로 결과


def test_guest_home_shows_fortune_cta(client):
    body = client.get("/").data.decode("utf-8")
    assert "fortune-strip" in body
    assert "생년월일만 입력하면" in body


# ---- 쿠팡 배너 (결과 화면에만 1개) --------------------------------------
def test_fortune_result_has_one_coupang_banner(client):
    body = client.get("/today?y=1990&m=6&d=15").data.decode("utf-8")
    assert body.count("ads-partners.coupang.com/g.js") == 1
    # 다른 생년월일로 보기 버튼 아래 배치
    assert body.index("다른 생년월일로 보기") < body.index("ads-partners.coupang.com/g.js")


def test_fortune_form_has_no_coupang_banner(client):
    body = client.get("/today").data.decode("utf-8")
    assert "coupang" not in body.lower()


# ---- 퍼널 (재록 → 재물운 상품) -----------------------------------------
def test_fortune_funnel_links_money_product(client):
    body = client.get("/today?y=1990&m=6&d=15").data.decode("utf-8")
    assert "재록 선생" in body
    assert "재물운 더 깊게 보기" in body
    assert "/product/jaerok-money" in body
    assert "jaerok_profile.jpg" in body
