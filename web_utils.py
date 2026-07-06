# -*- coding: utf-8 -*-
"""웹 공용 유틸: 세션 사용자, 로그인 보호 데코레이터, 상품 접근 권한."""
from functools import wraps

from flask import session, redirect, url_for, flash, g

from models import db, User, Payment, SajuReading


def has_paid(user, product) -> bool:
    """유료 상품 이용 권한: 무료 상품은 항상 True, 유료는 DONE 결제 보유 여부."""
    if product.price == 0:
        return True
    if user is None:
        return False
    return (
        Payment.query.filter_by(
            user_id=user.id, product_id=product.id, status="DONE"
        ).count() > 0
    )


def has_reading(user, product) -> bool:
    """리뷰 자격 (US-018): 해당 상품 풀이를 실제로 받은 회원인지."""
    if user is None:
        return False
    return (
        SajuReading.query.filter_by(user_id=user.id, product_id=product.id).count() > 0
    )


def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    if getattr(g, "_cached_user", None) is not None and g._cached_user.id == uid:
        return g._cached_user
    user = db_get_user(uid)
    g._cached_user = user
    return user


def db_get_user(uid):
    return db.session.get(User, uid)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") is None:
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for("auth.login", next=True))
        return view(*args, **kwargs)
    return wrapped
