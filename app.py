# -*- coding: utf-8 -*-
"""사주 홈페이지 — Flask 애플리케이션."""
import json

from flask import (
    Flask, render_template, request, redirect, url_for, flash, g,
)

from config import Config
from models import db, SajuReading, Payment
from saju.engine import calculate_saju
from saju.interpret import interpret
from web_utils import current_user, login_required, PRODUCTS


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    from auth import bp as auth_bp
    from payment import bp as payment_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(payment_bp)

    with app.app_context():
        db.create_all()

    @app.before_request
    def _reset_user_cache():
        g._cached_user = None

    @app.context_processor
    def _inject_user():
        return {"current_user": current_user()}

    # ---- 메인 ----------------------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/calculate", methods=["POST"])
    def calculate():
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
            return redirect(url_for("index"))

        try:
            result = calculate_saju(
                year, month, day, hour,
                is_lunar=is_lunar, is_intercalation=is_intercalation,
                gender=gender,
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("index"))

        reading = interpret(result)
        result_dict = result.to_dict()
        palja = " ".join(
            p["gapja"] for p in [
                result_dict["year"], result_dict["month"],
                result_dict["day"],
            ] + ([result_dict["hour"]] if result_dict["hour"] else [])
        )

        # 저장 (로그인 시 사용자 귀속)
        user = current_user()
        rec = SajuReading(
            user_id=user.id if user else None,
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

        return render_template(
            "result.html",
            name=name, r=result_dict, reading=reading, palja=palja,
        )

    @app.route("/pricing")
    def pricing():
        return render_template("pricing.html", products=PRODUCTS)

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
        return render_template(
            "result.html",
            name=rec.name, r=payload["result"], reading=payload["reading"],
            palja=rec.palja,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os
    app.run(debug=True, host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")))
