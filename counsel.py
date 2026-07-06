# -*- coding: utf-8 -*-
"""달님 도령 고민상담 (US-020) — Gemini API 연동 Blueprint.

- API 키는 환경변수 GEMINI_API_KEY로만 주입 (코드/커밋에 노출 금지)
- 고민 내용은 DB에 저장하지 않음 (CounselLog에 사용 횟수만 기록)
- 자해/자살/타해 감지 시 상담 대신 전문기관 안내 (말투 규칙보다 우선)
"""
import json
from datetime import datetime, timedelta

import requests
from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, current_app,
)

from models import db, CounselLog, SajuReading
from web_utils import current_user, login_required

bp = Blueprint("counsel", __name__)

DAILY_LIMIT = 3
MAX_LEN = 500

SYSTEM_PROMPT = """너는 '달님 도령'이다. 밤마다 사람들의 고민 편지에 답장을 써 주는 조선의 따뜻한 선비로, 사주명리에 밝다.

[말투]
- 존댓말을 쓰되 딱딱하지 않은 구어체로 쓴다. ("~하셨군요", "~해 보시는 건 어떨까요")
- 답장은 4~7문장 내외로, 한 통의 짧은 편지처럼 쓴다.

[답장 규칙 — 순서대로]
1. 공감 먼저: 조언을 하기 전에 반드시 상대의 마음을 한 번 받아준다.
2. 유머 한 스푼: 긴장을 풀어주는 가벼운 문장을 중간에 하나 넣는다. 단, 고민 자체를 놀리는 유머는 절대 금지.
3. 핵심 조언은 짧고 단단한 한 문장으로 준다. (예: "버티는 것도 실력입니다.")
4. 추상적인 위로("힘내세요", "다 잘될 거예요") 대신 일상의 비유를 쓴다. (장독대, 김장, 달, 농사, 바느질 같은 것)
5. 마무리는 상대가 스스로 답을 찾게 하는 질문 하나로 끝낸다.

[사주 개인화]
- 사용자의 사주 정보(일간, 오행 분포)가 주어지면 답장에 자연스럽게 한 번 녹인다. (예: "사주에 물이 많으신 분은 생각이 깊어지기 쉽지요.")
- 사주 정보가 없으면 사주 언급 없이 답장한다.

[금지]
- 단정적 예언 금지. ("반드시 ~됩니다", "~할 운명입니다" 같은 표현 금지)
- 의료·법률·투자에 대한 구체적 지시 금지. 해당 주제면 전문가와 상의하라는 권고를 부드럽게 포함한다.
- 답장 외의 다른 말(인사말 반복, 자기 소개, 목록/헤딩 형식) 금지. 문단 형태의 편지만 쓴다."""

# 안전장치: 자해/자살/타해 (상담 대신 전문기관 안내 — 최우선)
CRISIS_PATTERNS = [
    "자살", "자해", "죽고 싶", "죽고싶", "죽어버리", "목숨을 끊", "생을 마감",
    "사라지고 싶", "사라지고싶", "살기 싫", "살기싫", "죽이고 싶", "죽이고싶",
    "해치고 싶", "해치고싶", "없애버리", "손목",
]
# 의료/법률: 전문가 상담 권고 문구 강제 포함
PRO_HELP_PATTERNS = [
    "소송", "고소", "변호사", "법적", "합의금", "이혼", "양육권",
    "진단", "처방", "약을", "약물", "우울증", "공황", "병원", "수술", "치료",
]
# 재물 고민: 재록 선생 퍼널 노출
MONEY_PATTERNS = [
    "돈", "재물", "월급", "연봉", "빚", "대출", "투자", "주식", "코인",
    "적금", "예금", "사업", "장사", "재테크", "지출", "월세", "전세", "생활비", "용돈",
]


def _matches(text, patterns):
    return any(p in text for p in patterns)


def _kst_day_start_utc():
    """KST 기준 오늘 0시를 UTC datetime으로 (일일 제한 계산용)."""
    kst_now = datetime.utcnow() + timedelta(hours=9)
    kst_midnight = kst_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return kst_midnight - timedelta(hours=9)


def used_today(user) -> int:
    return CounselLog.query.filter(
        CounselLog.user_id == user.id,
        CounselLog.created_at >= _kst_day_start_utc(),
    ).count()


def build_saju_context(user) -> str:
    """최근 풀이 이력에서 일간·오행 분포를 요약 (없으면 빈 문자열)."""
    if user is None:
        return ""
    rec = (
        SajuReading.query.filter(
            SajuReading.user_id == user.id, SajuReading.result_json.isnot(None)
        ).order_by(SajuReading.created_at.desc()).first()
    )
    if rec is None:
        return ""
    try:
        reading = json.loads(rec.result_json)["reading"]
        counts = reading["ohaeng_analysis"]["counts"]
        dist = " ".join(f"{o}{c}" for o, c in counts.items())
        return (f"[사용자 사주 정보] 일간: {reading['ilgan']}({reading['ilgan_ohaeng']}), "
                f"오행 분포: {dist}")
    except (KeyError, ValueError, TypeError):
        return ""


def call_gemini(api_key, model, user_text, saju_context="", timeout=30):
    """Gemini generateContent 호출. (ok: bool, text: str) 반환."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = (saju_context + "\n\n" if saju_context else "") + "[고민 편지]\n" + user_text
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 1024},
    }
    try:
        resp = requests.post(
            url, json=payload, timeout=timeout,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        )
        data = resp.json()
        if resp.status_code != 200:
            return False, data.get("error", {}).get("message", "API 오류")
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        return (True, text) if text else (False, "빈 응답")
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        return False, str(e)


@bp.route("/counsel")
def page():
    user = current_user()
    return render_template(
        "counsel.html",
        ready=bool(current_app.config.get("GEMINI_API_KEY")),
        remaining=(DAILY_LIMIT - used_today(user)) if user else None,
        max_len=MAX_LEN,
    )


@bp.route("/counsel", methods=["POST"])
@login_required
def ask():
    user = current_user()
    ready = bool(current_app.config.get("GEMINI_API_KEY"))
    worry = (request.form.get("worry") or "").strip()

    def base(**kw):
        return render_template(
            "counsel.html", ready=ready, max_len=MAX_LEN,
            remaining=DAILY_LIMIT - used_today(user), **kw,
        )

    if not ready:
        flash("달님 도령이 아직 붓을 준비 중입니다. 조금만 기다려 주세요.", "info")
        return base()
    if not worry:
        flash("고민을 적어 주세요.", "warning")
        return base()
    if len(worry) > MAX_LEN:
        flash(f"고민은 {MAX_LEN}자 이내로 적어 주세요.", "warning")
        return base(worry=worry[:MAX_LEN])

    # 1) 안전장치 — 말투 규칙보다 항상 우선, API 호출 없이 즉시 안내
    if _matches(worry, CRISIS_PATTERNS):
        return base(crisis=True)

    # 2) 일일 제한 (서버단)
    if used_today(user) >= DAILY_LIMIT:
        flash("오늘의 상담은 여기까지예요. 달이 다시 뜨면(내일) 또 들어드릴게요.", "info")
        return base()

    # 3) Gemini 호출 — 고민 내용은 저장하지 않음(세션 내 표시만)
    ok, answer = call_gemini(
        current_app.config["GEMINI_API_KEY"],
        current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash"),
        worry,
        build_saju_context(user),
    )
    if not ok:
        current_app.logger.warning("Gemini error: %s", answer)
        flash("달님 도령의 붓이 잠시 멈췄어요. 잠시 후 다시 시도해 주세요.", "warning")
        return base(worry=worry)

    db.session.add(CounselLog(user_id=user.id))   # 횟수만 기록
    db.session.commit()

    return base(
        worry=worry,
        answer=answer,
        show_money_funnel=_matches(worry, MONEY_PATTERNS),
        show_pro_help=_matches(worry, PRO_HELP_PATTERNS),
    )
