# -*- coding: utf-8 -*-
"""회원가입 / 로그인 / 로그아웃 블루프린트."""
import re

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
)

from models import db, User

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""

        error = None
        if not EMAIL_RE.match(email):
            error = "올바른 이메일 형식이 아닙니다."
        elif len(pw) < 6:
            error = "비밀번호는 6자 이상이어야 합니다."
        elif pw != pw2:
            error = "비밀번호가 일치하지 않습니다."
        elif User.query.filter_by(email=email).first() is not None:
            error = "이미 가입된 이메일입니다."

        if error:
            flash(error, "danger")
            return render_template("signup.html", email=email)

        user = User(email=email)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        flash("회원가입이 완료되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(pw):
            flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
            return render_template("login.html", email=email)
        session.clear()
        session["user_id"] = user.id
        flash("로그인되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("index"))
