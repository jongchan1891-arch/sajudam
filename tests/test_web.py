# -*- coding: utf-8 -*-
"""웹 라우트 / 회원 / 결제 통합 테스트."""
import base64

import pytest

from app import create_app
from config import TestConfig
from models import db, User, Payment, SajuReading
import payment as payment_module


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


# ---- US-005: 입력/결과 ----------------------------------------------
def test_index_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "무료 사주풀이".encode() in r.data


def test_calculate_returns_palja(client):
    r = client.post("/calculate", data={
        "name": "홍길동", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=True)
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    # 팔자 8글자 포함 (경오 임오 신해 갑오)
    for ch in ["경", "오", "임", "신", "해", "갑"]:
        assert ch in body
    assert "오행 분석" in body
    assert "성격" in body and "직업" in body


def test_calculate_hour_unknown(client):
    r = client.post("/calculate", data={
        "year": "1990", "month": "6", "day": "15",
        "hour_known": "no", "gender": "여", "cal_type": "solar",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "시주는 제외" in r.data.decode("utf-8")


def test_calculate_lunar_input(client):
    r = client.post("/calculate", data={
        "year": "1990", "month": "5", "day": "23",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "lunar",
    }, follow_redirects=True)
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "신" in body and "해" in body  # 신해 일주


# ---- US-006: 회원 ----------------------------------------------------
def test_signup_and_login(client, app):
    r = _signup(client)
    assert r.status_code == 200
    with app.app_context():
        u = User.query.filter_by(email="a@b.com").first()
        assert u is not None
        assert u.password_hash != "secret1"       # 해시 저장
        assert u.check_password("secret1")

    client.get("/logout", follow_redirects=True)
    r = client.post("/login", data={"email": "a@b.com", "password": "secret1"},
                    follow_redirects=True)
    assert r.status_code == 200
    # 로그인 후 마이페이지 접근 가능
    assert client.get("/mypage").status_code == 200


def test_duplicate_email_rejected(client):
    _signup(client)
    client.get("/logout")
    r = client.post("/signup", data={"email": "a@b.com", "password": "secret1", "password2": "secret1"},
                    follow_redirects=True)
    assert "이미 가입된 이메일" in r.data.decode("utf-8")


def test_wrong_login_rejected(client):
    _signup(client)
    client.get("/logout")
    r = client.post("/login", data={"email": "a@b.com", "password": "wrongpw"},
                    follow_redirects=True)
    assert "올바르지 않습니다" in r.data.decode("utf-8")


# ---- US-008: 마이페이지 ---------------------------------------------
def test_mypage_requires_login(client):
    r = client.get("/mypage", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_mypage_shows_reading(client, app):
    _signup(client)
    client.post("/calculate", data={
        "name": "나", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=True)
    r = client.get("/mypage")
    body = r.data.decode("utf-8")
    assert "사주 계산 이력" in body
    assert "신해" in body  # 저장된 팔자 노출


# ---- US-007: 결제 ----------------------------------------------------
def test_toss_auth_header():
    h = payment_module.build_auth_header("test_sk_abc")
    expected = "Basic " + base64.b64encode(b"test_sk_abc:").decode()
    assert h == expected


def test_checkout_renders_with_client_key(client, app):
    r = client.get("/payment/checkout?product=jaerok-money")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert app.config["TOSS_CLIENT_KEY"] in body
    assert "9,900" in body
    # Payment READY 레코드 생성
    with app.app_context():
        assert Payment.query.filter_by(status="READY").count() == 1


def test_checkout_invalid_product_404(client):
    assert client.get("/payment/checkout?product=nope").status_code == 404


def test_confirm_payment_builds_request(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        def json(self):
            return {"method": "카드", "orderId": captured["json"]["orderId"]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(payment_module.requests, "post", fake_post)
    ok, data = payment_module.confirm_payment(
        "test_sk_x", "https://api.tosspayments.com/v1/payments/confirm",
        "pk_123", "order_abc", 9900,
    )
    assert ok is True
    assert captured["json"] == {"paymentKey": "pk_123", "orderId": "order_abc", "amount": 9900}
    assert captured["headers"]["Authorization"].startswith("Basic ")
    assert captured["url"].endswith("/payments/confirm")


def test_payment_success_flow(client, app, monkeypatch):
    # 체크아웃으로 주문 생성
    client.get("/payment/checkout?product=jaerok-money")
    with app.app_context():
        pay = Payment.query.filter_by(status="READY").first()
        order_id = pay.order_id

    # confirm API 모킹 -> 성공
    monkeypatch.setattr(
        payment_module, "confirm_payment",
        lambda *a, **k: (True, {"method": "카드"})
    )
    r = client.get(f"/payment/success?paymentKey=pk_1&orderId={order_id}&amount=9900",
                   follow_redirects=True)
    assert r.status_code == 200
    assert "결제가 완료" in r.data.decode("utf-8")
    with app.app_context():
        pay = Payment.query.filter_by(order_id=order_id).first()
        assert pay.status == "DONE"
        assert pay.payment_key == "pk_1"


def test_payment_amount_mismatch(client, app, monkeypatch):
    client.get("/payment/checkout?product=jaerok-money")
    with app.app_context():
        order_id = Payment.query.filter_by(status="READY").first().order_id
    # 금액 위변조 (9900 != 100)
    r = client.get(f"/payment/success?paymentKey=pk_1&orderId={order_id}&amount=100",
                   follow_redirects=True)
    body = r.data.decode("utf-8")
    assert "일치하지 않습니다" in body


# ---- US-012: 모바일 반응형 -------------------------------------------
def test_viewport_meta_present(client):
    body = client.get("/").data.decode("utf-8")
    assert 'name="viewport"' in body
    assert "width=device-width" in body


def test_responsive_breakpoints_in_css():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "static" / "css" / "style.css").read_text("utf-8")
    assert "@media (max-width: 768px)" in css
    assert "@media (max-width: 480px)" in css
    assert "overflow-x: hidden" in css  # 가로 스크롤 금지


# ---- US-013: 쿠팡 파트너스 배너 ---------------------------------------
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


def _calc(client):
    return client.post("/calculate", data={
        "name": "홍길동", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=True)


def test_result_has_two_coupang_banners(client):
    body = _calc(client).data.decode("utf-8")
    assert body.count("ads-partners.coupang.com/g.js") == 2
    assert body.count('"trackingCode":"AF9200718"') == 2
    assert body.count(DISCLOSURE) == 2
    # 해설 카드(운세 해설) 이전에 첫 배너, result-actions 이후에 둘째 배너
    assert body.index("ads-partners.coupang.com/g.js") < body.index("운세 해설")
    assert body.rindex("ads-partners.coupang.com/g.js") > body.index("result-actions")


def test_home_has_one_coupang_banner_below_grid(client):
    body = client.get("/").data.decode("utf-8")
    assert body.count("ads-partners.coupang.com/g.js") == 1
    assert body.count(DISCLOSURE) == 1
    # 첫인상 보호: 상품 그리드 아래(하단)에만 위치
    assert body.index("풀이 상품") < body.index("ads-partners.coupang.com/g.js")


# ---- US-009: 스모크 --------------------------------------------------
def test_smoke_routes(client):
    for path in ["/", "/saju", "/pricing", "/login", "/signup",
                 "/payment/checkout?product=premium-total"]:
        assert client.get(path).status_code == 200
