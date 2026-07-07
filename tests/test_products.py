# -*- coding: utf-8 -*-
"""v2 상품 시스템 테스트 (US-014 ~ US-018)."""
import pytest

from app import create_app
from config import TestConfig
from models import db, Product, Review, SajuReading
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


def _calc(client, slug=None):
    data = {
        "name": "홍길동", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }
    if slug:
        data["product"] = slug
    return client.post("/calculate", data=data, follow_redirects=True)


def _pay_done(client, app, monkeypatch, slug):
    """유료 상품 테스트 결제 완료 처리."""
    client.get(f"/payment/checkout?product={slug}")
    with app.app_context():
        from models import Payment
        pay = Payment.query.filter_by(status="READY").order_by(Payment.id.desc()).first()
        order_id = pay.order_id
        amount = pay.amount
    monkeypatch.setattr(payment_module, "confirm_payment",
                        lambda *a, **k: (True, {"method": "카드"}))
    client.get(f"/payment/success?paymentKey=pk_t&orderId={order_id}&amount={amount}",
               follow_redirects=True)


# ---- US-014: 상품 모델 & 상품별 해설 ---------------------------------
def test_seed_has_all_categories(app):
    with app.app_context():
        for cat in ["연애", "재물", "종합", "재회"]:
            assert Product.query.filter_by(category=cat).count() >= 1, cat
        p = Product.query.filter_by(slug="jaerok-money").first()
        assert p.character_name == "재록"
        assert p.tagline and p.thumbnail and p.price == 9900


def test_composition_differs_by_product(client, app, monkeypatch):
    free_body = _calc(client, "jaerok-free").data.decode("utf-8")
    _signup(client, "buyer@b.com")
    _pay_done(client, app, monkeypatch, "jaerok-money")
    # 유료는 US-022부터 Gemini 장문 리포트 — 호출 모킹
    import report_service
    filler = "곳간의 물꼬가 트여 흐름이 굵어지는 사주입니다. " * 60
    monkeypatch.setattr(
        report_service, "_call_gemini_json",
        lambda *a, **k: (True, {k2: filler[:400] for k2 in
                                ["grit", "inflow", "leak", "timing", "rx"]}),
    )
    money_body = _calc(client, "jaerok-money").data.decode("utf-8")

    # 같은 입력, 다른 상품 → 다른 구성 (US-014 / US-022)
    assert "재록이의 무료 사주 맛보기" in free_body
    assert "심층풀이에서" in free_body            # 무료 상품 아웃트로 (기존 유지)
    assert "타고난 재물 그릇" not in free_body     # 리포트 섹션은 유료 전용
    assert "타고난 재물 그릇" in money_body        # 유료 = 장문 리포트 (US-022)
    assert "재록이의 재물운 심층풀이" in money_body


def test_default_calc_keeps_v1_sections(client):
    body = _calc(client).data.decode("utf-8")
    for cat in ["성격", "직업", "재물", "연애"]:
        assert cat in body


# ---- US-015: 홈 개편 --------------------------------------------------
def test_home_has_tabs_grid_ranking(client):
    body = client.get("/").data.decode("utf-8")
    for cat in ["전체", "연애", "재물", "종합", "재회"]:
        assert cat in body
    assert "cat-tab" in body
    assert "product-card" in body
    assert "지금 인기" in body
    assert "재록이의 무료 사주 맛보기" in body


def test_home_category_filter(client):
    body = client.get("/?cat=연애").data.decode("utf-8")
    assert "연화의 연애운 풀이" in body
    assert "재록이의 재물운 심층풀이" not in body


def test_home_placeholder_for_missing_thumbnail(client):
    body = client.get("/?cat=재회").data.decode("utf-8")
    assert "pc-placeholder" in body          # 썸네일 없는 상품 → 플레이스홀더
    assert "wolha" not in body.lower().replace("wolha-rejoin", "")  # 이미지 파일 참조 없음


def test_popularity_ranking_uses_reading_counts(client, app):
    _calc(client, "yeonhwa-love") if False else None
    # 연애 상품 풀이 2회 → 랭킹 1위
    with app.app_context():
        p = Product.query.filter_by(slug="yeonhwa-love").first()
        db.session.add(SajuReading(product_id=p.id, palja="x"))
        db.session.add(SajuReading(product_id=p.id, palja="y"))
        db.session.commit()
    body = client.get("/").data.decode("utf-8")
    first_rank_pos = body.index("rank-item")
    assert body.index("연화의 연애운 풀이", first_rank_pos) < body.index("재록이의 무료 사주 맛보기", first_rank_pos)


# ---- US-016: 하단 네비 ------------------------------------------------
def test_bottom_nav_in_layout(client):
    body = client.get("/").data.decode("utf-8")
    assert "bottom-nav" in body
    for label in ["홈", "사주풀이", "마이"]:
        assert label in body


def test_bottom_nav_css_mobile_only():
    import pathlib
    css = (pathlib.Path(__file__).parent.parent / "static" / "css" / "style.css").read_text("utf-8")
    assert ".bottom-nav { display: none; }" in css          # 데스크톱 기본 숨김
    assert "safe-area-inset-bottom" in css                   # iOS safe-area


# ---- US-017: 상품 상세 -------------------------------------------------
def test_product_detail_renders(client):
    body = client.get("/product/jaerok-money").data.decode("utf-8")
    assert "재록이의 재물운 심층풀이" in body
    assert "9,900" in body
    assert "리뷰" in body
    assert "결제하고 풀이 시작" in body


def test_free_product_detail_starts_without_payment(client):
    body = client.get("/product/jaerok-free").data.decode("utf-8")
    assert "풀이 시작하기" in body
    assert "결제하고" not in body


def test_product_detail_404(client):
    assert client.get("/product/nope").status_code == 404


def test_paid_product_requires_payment(client):
    r = client.get("/saju?product=jaerok-money", follow_redirects=False)
    assert r.status_code == 302
    assert "/payment/checkout" in r.headers["Location"]
    r = client.post("/calculate", data={
        "product": "jaerok-money", "year": "1990", "month": "6", "day": "15",
        "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "/payment/checkout" in r.headers["Location"]


def test_paid_product_after_payment(client, app, monkeypatch):
    _signup(client)
    _pay_done(client, app, monkeypatch, "jaerok-money")
    assert client.get("/saju?product=jaerok-money").status_code == 200


def test_free_product_checkout_redirects_to_form(client):
    r = client.get("/payment/checkout?product=jaerok-free", follow_redirects=False)
    assert r.status_code == 302
    assert "/saju" in r.headers["Location"]


# ---- US-018: 리뷰 ------------------------------------------------------
def test_review_requires_login(client):
    r = client.post("/product/jaerok-free/review",
                    data={"rating": "5", "content": "좋아요"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_review_requires_reading(client, app):
    _signup(client)
    r = client.post("/product/jaerok-free/review",
                    data={"rating": "5", "content": "좋아요"}, follow_redirects=True)
    assert "풀이를 받은 회원만" in r.data.decode("utf-8")
    with app.app_context():
        assert Review.query.count() == 0


def test_review_create_update_and_average(client, app):
    _signup(client)
    _calc(client, "jaerok-free")                       # 풀이 받음 → 자격 획득
    r = client.post("/product/jaerok-free/review",
                    data={"rating": "5", "content": "재록이 최고!"}, follow_redirects=True)
    body = r.data.decode("utf-8")
    assert "리뷰를 등록했습니다" in body
    assert "재록이 최고!" in body

    # 같은 회원 재작성 → 수정(1개 유지)
    client.post("/product/jaerok-free/review",
                data={"rating": "3", "content": "다시 보니 보통"}, follow_redirects=True)
    with app.app_context():
        reviews = Review.query.all()
        assert len(reviews) == 1
        assert reviews[0].rating == 3

    body = client.get("/product/jaerok-free").data.decode("utf-8")
    assert "★ 3.0" in body                             # 평균 평점 표시


def test_review_rejects_bad_rating(client, app):
    _signup(client)
    _calc(client, "jaerok-free")
    client.post("/product/jaerok-free/review",
                data={"rating": "9", "content": "x"}, follow_redirects=True)
    with app.app_context():
        assert Review.query.count() == 0
