# -*- coding: utf-8 -*-
"""사주 홈페이지 — Flask 애플리케이션."""
import json
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash, g,
)

from sqlalchemy import func

import report_service
from config import Config
from models import db, SajuReading, SajuReport, Payment, Product, Review
from saju.daily import compute_daily_fortune
from saju.engine import calculate_saju
from saju.interpret import interpret
from saju.product_config import compose_reading
from seed import seed_products
from web_utils import current_user, login_required, has_paid, has_reading

CATEGORIES = ["전체", "연애", "재물", "종합", "재회"]


def kst_today():
    """서버 시간대와 무관하게 KST 기준 오늘 날짜."""
    return (datetime.utcnow() + timedelta(hours=9)).date()


def _user_birth(user):
    """회원의 저장된 생년월일(가장 최근 풀이 이력 기준). 없으면 None."""
    if user is None:
        return None
    rec = (
        SajuReading.query.filter(
            SajuReading.user_id == user.id, SajuReading.birth_solar.isnot(None)
        ).order_by(SajuReading.created_at.desc()).first()
    )
    if rec is None:
        return None
    try:
        y, m, d = map(int, rec.birth_solar.split("-"))
        return (y, m, d)
    except (ValueError, AttributeError):
        return None


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    from auth import bp as auth_bp
    from counsel import bp as counsel_bp
    from payment import bp as payment_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(counsel_bp)
    app.register_blueprint(payment_bp)

    with app.app_context():
        db.create_all()
        seed_products()

    @app.before_request
    def _reset_user_cache():
        g._cached_user = None

    @app.context_processor
    def _inject_user():
        return {"current_user": current_user()}

    # ---- 메인 ----------------------------------------------------
    @app.route("/")
    def index():
        """상품 중심 홈 (US-015): 카테고리 탭 + 상품 그리드 + 인기 랭킹."""
        cat = request.args.get("cat", "전체")
        if cat not in CATEGORIES:
            cat = "전체"
        q = Product.query.filter_by(is_active=True)
        if cat != "전체":
            q = q.filter_by(category=cat)
        products = q.order_by(Product.price.asc(), Product.id.asc()).all()

        # 지금 인기: 실데이터(풀이 횟수) 기준 상위 3
        popular = (
            db.session.query(Product, func.count(SajuReading.id).label("cnt"))
            .outerjoin(SajuReading, SajuReading.product_id == Product.id)
            .filter(Product.is_active.is_(True))
            .group_by(Product.id)
            .order_by(func.count(SajuReading.id).desc(), Product.id.asc())
            .limit(3)
            .all()
        )
        # 오늘의 운세 미리보기 (US-019): 회원 + 저장된 생년월일 있을 때
        fortune = None
        birth = _user_birth(current_user())
        if birth:
            fortune = compute_daily_fortune(*birth, kst_today())
        return render_template(
            "index.html",
            products=products, popular=popular,
            categories=CATEGORIES, active_cat=cat, fortune=fortune,
        )

    @app.route("/today")
    def today_fortune():
        """오늘의 운세 (US-019). 비회원은 생년월일 입력, 회원은 자동 표시."""
        today = kst_today()
        birth = None
        try:
            if request.args.get("y"):
                y = int(request.args["y"])
                m = int(request.args["m"])
                d = int(request.args["d"])
                if not (1900 <= y <= 2100):
                    raise ValueError
                datetime(y, m, d)  # 날짜 유효성
                birth = (y, m, d)
        except (KeyError, ValueError):
            flash("생년월일을 확인해 주세요.", "danger")
            return redirect(url_for("today_fortune"))

        if birth is None:
            birth = _user_birth(current_user())

        fortune = compute_daily_fortune(*birth, today) if birth else None
        return render_template("today.html", fortune=fortune, today=today)

    @app.route("/saju")
    def saju_form():
        """사주 입력 폼. product 파라미터가 있으면 해당 상품 풀이로 진행."""
        product = None
        slug = request.args.get("product")
        if slug:
            product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
            if product.price > 0 and not has_paid(current_user(), product):
                flash("결제 후 이용할 수 있는 풀이입니다.", "warning")
                return redirect(url_for("payment.checkout", product=slug))
        return render_template("saju_form.html", product=product)

    @app.route("/product/<slug>")
    def product_detail(slug):
        """상품 상세 (US-017): 배너 + 설명 + 리뷰 + 풀이 시작."""
        product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
        reviews = (
            Review.query.filter_by(product_id=product.id)
            .order_by(Review.created_at.desc()).all()
        )
        avg_rating = (
            round(sum(rv.rating for rv in reviews) / len(reviews), 1) if reviews else None
        )
        user = current_user()
        my_review = (
            Review.query.filter_by(user_id=user.id, product_id=product.id).first()
            if user else None
        )
        return render_template(
            "product_detail.html",
            product=product, reviews=reviews, avg_rating=avg_rating,
            can_review=has_reading(user, product), my_review=my_review,
            reading_count=SajuReading.query.filter_by(product_id=product.id).count(),
            paid=has_paid(user, product),
        )

    @app.route("/product/<slug>/review", methods=["POST"])
    @login_required
    def product_review(slug):
        """리뷰 작성/수정 (US-018): 풀이 받은 회원만, 회원당 1개."""
        product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
        user = current_user()
        if not has_reading(user, product):
            flash("이 상품의 풀이를 받은 회원만 리뷰를 작성할 수 있습니다.", "warning")
            return redirect(url_for("product_detail", slug=slug))

        content = (request.form.get("content") or "").strip()
        try:
            rating = int(request.form.get("rating", ""))
        except ValueError:
            rating = 0
        if not (1 <= rating <= 5) or not content:
            flash("별점(1~5)과 리뷰 내용을 입력해 주세요.", "danger")
            return redirect(url_for("product_detail", slug=slug))

        review = Review.query.filter_by(user_id=user.id, product_id=product.id).first()
        if review:
            review.rating = rating
            review.content = content
            flash("리뷰를 수정했습니다.", "success")
        else:
            db.session.add(Review(
                user_id=user.id, product_id=product.id,
                rating=rating, content=content,
            ))
            flash("리뷰를 등록했습니다.", "success")
        db.session.commit()
        return redirect(url_for("product_detail", slug=slug))

    @app.route("/calculate", methods=["POST"])
    def calculate():
        product = None
        slug = (request.form.get("product") or "").strip()
        if slug:
            product = Product.query.filter_by(slug=slug, is_active=True).first()
            if product and product.price > 0 and not has_paid(current_user(), product):
                flash("결제 후 이용할 수 있는 풀이입니다.", "warning")
                return redirect(url_for("payment.checkout", product=slug))
        try:
            name = (request.form.get("name") or "").strip()
            year = int(request.form["year"])
            month = int(request.form["month"])
            day = int(request.form["day"])
            gender = request.form.get("gender", "")
            cal_type = request.form.get("cal_type", "solar")  # solar/lunar
            is_lunar = cal_type == "lunar"
            is_intercalation = request.form.get("intercalation") == "on"

            hour_known = request.form.get("hour_known", "yes") == "yes"
            hour = int(request.form["hour"]) if hour_known and request.form.get("hour", "") != "" else None
        except (KeyError, ValueError):
            flash("입력값을 확인해 주세요.", "danger")
            return redirect(url_for("saju_form", product=slug or None))

        try:
            result = calculate_saju(
                year, month, day, hour,
                is_lunar=is_lunar, is_intercalation=is_intercalation,
                gender=gender,
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("saju_form", product=slug or None))

        reading = interpret(result)
        result_dict = result.to_dict()
        palja = " ".join(
            p["gapja"] for p in [
                result_dict["year"], result_dict["month"],
                result_dict["day"],
            ] + ([result_dict["hour"]] if result_dict["hour"] else [])
        )

        # 저장 (로그인 시 사용자 귀속, 상품 풀이면 상품 귀속)
        user = current_user()
        rec = SajuReading(
            user_id=user.id if user else None,
            product_id=product.id if product else None,
            name=name,
            birth_solar=result.solar_date,
            birth_hour=hour,
            gender=gender,
            palja=palja,
            result_json=json.dumps(
                {"result": result_dict, "reading": reading}, ensure_ascii=False
            ),
        )
        db.session.add(rec)
        db.session.commit()

        # 유료 리포트 상품 (US-022): Gemini 장문 리포트 생성 → 저장 → 표시
        if product is not None:
            report = report_service.ensure_report(rec, product)
            if report is not None:
                return _render_report(rec, product, report, result_dict, reading, palja, name)

        composed = compose_reading(product.slug if product else None, reading, name)
        return render_template(
            "result.html",
            name=name, r=result_dict, reading=reading, palja=palja,
            product=product, composed=composed,
        )

    @app.route("/pricing")
    def pricing():
        products = (
            Product.query.filter(Product.is_active.is_(True), Product.price > 0)
            .order_by(Product.price.asc()).all()
        )
        return render_template("pricing.html", products=products)

    @app.route("/mypage")
    @login_required
    def mypage():
        user = current_user()
        readings = (
            SajuReading.query.filter_by(user_id=user.id)
            .order_by(SajuReading.created_at.desc()).all()
        )
        payments = (
            Payment.query.filter_by(user_id=user.id)
            .order_by(Payment.created_at.desc()).all()
        )
        return render_template("mypage.html", readings=readings, payments=payments)

    @app.route("/reading/<int:reading_id>")
    @login_required
    def reading_detail(reading_id):
        user = current_user()
        rec = db.get_or_404(SajuReading, reading_id)
        if rec.user_id != user.id:
            flash("접근 권한이 없습니다.", "danger")
            return redirect(url_for("mypage"))
        payload = json.loads(rec.result_json)
        rec_product = db.session.get(Product, rec.product_id) if rec.product_id else None

        # 리포트가 있는 풀이는 저장본 표시 (US-022) — Gemini 재호출 없음
        if rec_product is not None:
            report = SajuReport.query.filter_by(reading_id=rec.id).first()
            if report is not None:
                return _render_report(
                    rec, rec_product, report,
                    payload["result"], payload["reading"], rec.palja, rec.name,
                )

        composed = compose_reading(
            rec_product.slug if rec_product else None, payload["reading"], rec.name,
        )
        return render_template(
            "result.html",
            name=rec.name, r=payload["result"], reading=payload["reading"],
            palja=rec.palja, product=rec_product, composed=composed,
        )

    @app.route("/reading/<int:reading_id>/report", methods=["POST"])
    @login_required
    def report_retry(reading_id):
        """리포트 재시도 (US-022) — 소유자만, 저장본 있으면 재호출 없이 표시."""
        user = current_user()
        rec = db.get_or_404(SajuReading, reading_id)
        if rec.user_id != user.id:
            flash("접근 권한이 없습니다.", "danger")
            return redirect(url_for("mypage"))
        product = db.session.get(Product, rec.product_id) if rec.product_id else None
        if product is None or product.slug not in report_service.REPORT_CONFIGS:
            return redirect(url_for("reading_detail", reading_id=rec.id))

        report = report_service.ensure_report(rec, product)
        if report.status == "DONE":
            flash("리포트가 완성되었습니다.", "success")
        else:
            flash("리포트 생성이 또 지연되었습니다. 잠시 후 다시 시도해 주세요.", "warning")
        return redirect(url_for("reading_detail", reading_id=rec.id))

    def _render_report(rec, product, report, r, reading, palja, name):
        cfg = report_service.REPORT_CONFIGS[product.slug]
        return render_template(
            "report.html",
            name=name, r=r, reading=reading, palja=palja, product=product,
            sections=report_service.report_sections(report),
            character=cfg["character"], profile=cfg["profile"], reading_id=rec.id,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")))
