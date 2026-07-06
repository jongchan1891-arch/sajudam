# -*- coding: utf-8 -*-
"""웹 공용 유틸: 세션 사용자, 로그인 보호 데코레이터, 상품 정의."""
from functools import wraps

from flask import session, redirect, url_for, flash, g

from models import db, User

# 결제 상품 정의: key -> (이름, 금액원)
PRODUCTS = {
    "basic": {"name": "기본 사주 해설", "amount": 9900},
    "premium": {"name": "프리미엄 종합 사주", "amount": 29900},
}


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
