# -*- coding: utf-8 -*-
"""토스페이먼츠 샌드박스(테스트) 결제 블루프린트."""
import base64
import uuid

import requests
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort, session,
)

from models import db, Payment
from web_utils import PRODUCTS, current_user

bp = Blueprint("payment", __name__, url_prefix="/payment")


def build_auth_header(secret_key: str) -> str:
    """토스 API용 Basic 인증 헤더 값 생성 (secretKey + ':')."""
    token = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def confirm_payment(secret_key, confirm_url, payment_key, order_id, amount, timeout=10):
    """토스 결제 승인 API 호출. (ok: bool, data: dict) 반환."""
    headers = {
        "Authorization": build_auth_header(secret_key),
        "Content-Type": "application/json",
    }
    payload = {"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)}
    resp = requests.post(confirm_url, json=payload, headers=headers, timeout=timeout)
    data = resp.json()
    return (resp.status_code == 200, data)


@bp.route("/checkout")
def checkout():
    product_key = request.args.get("product", "basic")
    if product_key not in PRODUCTS:
        abort(404)
    product = PRODUCTS[product_key]
    order_id = "order_" + uuid.uuid4().hex[:20]

    user = current_user()
    pay = Payment(
        user_id=user.id if user else None,
        order_id=order_id,
        product_name=product["name"],
        amount=product["amount"],
        status="READY",
    )
    db.session.add(pay)
    db.session.commit()

    return render_template(
        "checkout.html",
        client_key=current_app.config["TOSS_CLIENT_KEY"],
        order_id=order_id,
        product=product,
        product_key=product_key,
        customer_email=user.email if user else "",
    )


@bp.route("/success")
def success():
    payment_key = request.args.get("paymentKey")
    order_id = request.args.get("orderId")
    amount = request.args.get("amount")

    pay = Payment.query.filter_by(order_id=order_id).first()
    if pay is None:
        flash("결제 정보를 찾을 수 없습니다.", "danger")
        return redirect(url_for("pricing"))

    # 금액 위변조 검증
    if int(amount) != pay.amount:
        pay.status = "FAILED"
        db.session.commit()
        flash("결제 금액이 일치하지 않습니다.", "danger")
        return render_template("payment_result.html", ok=False, pay=pay)

    ok, data = confirm_payment(
        current_app.config["TOSS_SECRET_KEY"],
        current_app.config["TOSS_CONFIRM_URL"],
        payment_key, order_id, amount,
    )

    if ok:
        pay.status = "DONE"
        pay.payment_key = payment_key
        pay.method = data.get("method", "")
        db.session.commit()
        return render_template("payment_result.html", ok=True, pay=pay, data=data)
    else:
        pay.status = "FAILED"
        db.session.commit()
        msg = data.get("message", "결제 승인에 실패했습니다.")
        return render_template("payment_result.html", ok=False, pay=pay, error=msg)


@bp.route("/fail")
def fail():
    code = request.args.get("code", "")
    message = request.args.get("message", "결제가 취소되었거나 실패했습니다.")
    order_id = request.args.get("orderId")
    if order_id:
        pay = Payment.query.filter_by(order_id=order_id).first()
        if pay and pay.status == "READY":
            pay.status = "CANCELED"
            db.session.commit()
    return render_template("payment_result.html", ok=False, error=f"[{code}] {message}", pay=None)
