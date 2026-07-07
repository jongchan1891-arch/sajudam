# -*- coding: utf-8 -*-
"""유료 풀이 Gemini 장문 리포트 (US-022).

- 상품별 페르소나·섹션은 REPORT_CONFIGS로 정의 — config만 추가하면 상품 확장.
- 생성본은 SajuReport(saju_reports)에 저장하고 재조회 시 재호출하지 않는다.
- 실패 시 status=PENDING 유지 → 결과 화면에서 재시도 (돈 받고 빈 화면 금지).
"""
import json
from datetime import datetime, timedelta

import requests
from flask import current_app

from models import db, SajuReport

COMMON_RULES = """[공통 규칙 — 모든 섹션에 적용]
- 존댓말로 쓴다.
- 단정적 예언 금지: "~할 팔자다", "반드시 ~됩니다" 대신 "~한 흐름이 강합니다", "~하기 쉬운 기운입니다"처럼 흐름과 경향으로 쓴다.
- 모든 서술은 주어진 사주 데이터(일간, 팔자, 강한/약한 오행, 나이)를 근거로 든다. 데이터와 무관한 일반론 금지.
- 각 섹션 본문은 350자 이상, 문단 형태로 충실하게 쓴다. 헤딩·목록 기호 없이 본문만 쓴다(처방 섹션 제외).
- 처방 섹션만 "1. ..." "2. ..." "3. ..." 형식으로 실천 조언 3가지를 각각 줄바꿈으로 구분해 쓴다. 각 조언은 오늘부터 할 수 있는 구체적 행동이어야 한다.
- 의료·법률·투자 종목의 구체적 지시는 금지한다(방향 제시까지만).
- 제공된 사주 데이터에 없는 것을 지어내지 않는다. 특히 대운·세운의 구체 간지(예: "병술대운")는 데이터에 없으므로 절대 언급 금지 — 시기 분석은 나이대별 흐름과 오행 기운의 성쇠로만 서술한다.
- 본문 안에 마크다운 서식(**굵게**, ## 헤딩, - 목록 기호) 금지. 순수 문장만 쓴다.
- 출력은 반드시 지정된 JSON 객체 하나만. JSON 밖의 텍스트·마크다운 금지."""

REPORT_CONFIGS = {
    "jaerok-money": {
        "character": "재록 선생",
        "profile": "jaerok_profile.jpg",
        "min_chars": 1500,
        "persona": """너는 '재록 선생'이다. 주판을 든 사주담의 재물 도령으로, 곳간·장부·물꼬 같은 살림 비유를 즐겨 쓴다.
말투는 단단하고 실용적이다. "들어오는 돈보다 새는 돈부터 봐야지요." 같은, 현실을 똑바로 보게 하는 조언 톤.
헛된 희망을 팔지 않되, 반드시 실행 가능한 방향을 함께 준다.""",
        "sections": [
            ("grit", "타고난 재물 그릇",
             "사주 원국(일간과 팔자 전체)을 근거로 이 사람의 재물 성향 — 모으는 힘, 쓰는 습관, 돈을 대하는 기질을 풀이"),
            ("inflow", "돈이 들어오는 길",
             "가장 강한 오행을 근거로 어떤 방식의 수입(직장/사업/전문기술/투자 등)과 어떤 분야가 이 사주에 맞는지"),
            ("leak", "돈이 새는 구멍",
             "약하거나 없는 오행을 근거로 소비 습관·투자 판단에서 조심할 지점과 그 보완법"),
            ("timing", "시기 분석",
             "현재 나이를 기준으로 지나온 시기와 앞으로의 나이대별 재물 흐름 — 언제 모으고 언제 지켜야 하는지"),
            ("rx", "재록 선생의 처방",
             "위 내용을 바탕으로 오늘부터 실천할 재물 관리 조언 3가지"),
        ],
    },
    "yeonhwa-love": {
        "character": "연화",
        "profile": None,
        "min_chars": 1500,
        "persona": """너는 '연화'다. 사주담의 연애 도령으로, 꽃·계절·바람 같은 비유를 즐겨 쓴다.
말투는 다정하고 섬세하지만, 핵심은 흐리지 않고 분명하게 짚는다.
상대를 바꾸라는 조언 대신, 본인의 기운과 마음결을 돌보는 방향으로 이끈다.""",
        "sections": [
            ("grit", "타고난 인연의 결",
             "사주 원국(일간과 팔자 전체)을 근거로 이 사람의 연애 성향 — 마음을 여는 방식, 관계에서의 기질"),
            ("inflow", "사랑이 피어나는 자리",
             "가장 강한 오행을 근거로 어떤 만남·어떤 상대·어떤 관계 방식에서 이 사람의 매력이 살아나는지"),
            ("leak", "마음이 어긋나는 순간",
             "약하거나 없는 오행을 근거로 관계에서 반복되기 쉬운 갈등 패턴과 그 다스림"),
            ("timing", "시기 분석",
             "현재 나이를 기준으로 나이대별 인연의 흐름 — 마음을 열기 좋은 때와 신중해야 할 때"),
            ("rx", "연화의 처방",
             "위 내용을 바탕으로 오늘부터 실천할 연애·관계 조언 3가지"),
        ],
    },
    "wolha-rejoin": {
        "character": "월하",
        "profile": None,
        "min_chars": 1500,
        "persona": """너는 '월하'다. 달빛 아래에서 지난 인연의 매듭을 살피는 사주담의 도령으로, 달·밤·강물 비유를 즐겨 쓴다.
말투는 차분하고 담담하다. 미련을 부추기지 않고, 마음을 정리하는 힘을 준다.

[재회 상담 특별 규칙 — 최우선]
- 재회를 보장하는 표현("반드시 돌아옵니다", "다시 만날 운명입니다") 절대 금지. 가능성의 흐름으로만 말한다.
- 떠난 상대를 비난하지 않는다. 집착이나 매달림을 조장하는 조언 금지.
- 재회만이 답이 아님을 존중한다 — 놓아주는 선택도 하나의 길로 함께 제시한다.""",
        "sections": [
            ("grit", "지난 인연의 매듭",
             "사주 원국(일간과 팔자 전체)을 근거로 이 사람이 관계를 맺고 매듭짓는 방식 — 이별에 이르는 반복 패턴"),
            ("inflow", "다시 이어질 실마리",
             "가장 강한 오행을 근거로 관계 회복에 쓸 수 있는 이 사람의 힘과, 재회가 이뤄진다면 어떤 조건에서인지"),
            ("leak", "놓아야 할 미련",
             "약하거나 없는 오행을 근거로 재회를 막거나 같은 이별을 반복하게 하는 습관과 그 다스림"),
            ("timing", "시기 분석",
             "현재 나이를 기준으로 마음을 정리하고 움직이기 좋은 흐름 — 서두를 때와 기다릴 때"),
            ("rx", "월하의 처방",
             "위 내용을 바탕으로 오늘부터 실천할 조언 3가지 — 재회 시도든 정리든 본인이 단단해지는 행동 위주"),
        ],
    },
    "premium-total": {
        "character": "사주담",
        "profile": None,
        "min_chars": 2000,
        "persona": """너는 '사주담'이다. 도령들을 아우르는 사주담 본가의 목소리로, 가장 깊고 정중한 풀이를 맡는다.
말투는 정중하고 무게가 있되 어렵지 않게, 한지에 먹으로 눌러 쓴 편지처럼 쓴다.
성격·직업·재물·관계를 따로 떼지 않고 하나의 원국에서 흘러나오는 이야기로 엮는다.
각 섹션은 400자 이상으로, 프리미엄 풀이답게 가장 깊이 있게 쓴다.""",
        "sections": [
            ("grit", "타고난 그릇",
             "사주 원국 총론 — 일간과 팔자 전체가 그리는 기질·성격·타고난 강점"),
            ("inflow", "기운이 뻗는 길",
             "가장 강한 오행을 근거로 직업·적성·재물이 함께 열리는 방향"),
            ("leak", "채워야 할 자리",
             "약하거나 없는 오행을 근거로 관계·건강·습관에서 비어 있기 쉬운 자리와 그 보완"),
            ("timing", "인생의 큰 흐름",
             "현재 나이를 기준으로 지나온 시기의 의미와 앞으로의 나이대별 종합 흐름"),
            ("rx", "사주담의 처방",
             "위 내용을 바탕으로 오늘부터 실천할 조언 3가지"),
        ],
    },
}


def kst_today():
    return (datetime.utcnow() + timedelta(hours=9)).date()


def _build_system_prompt(cfg) -> str:
    lines = [cfg["persona"], "", COMMON_RULES, "", "[리포트 구성 — 5개 섹션]"]
    keys = []
    for key, title, guide in cfg["sections"]:
        lines.append(f'- "{key}" ({title}): {guide}')
        keys.append(f'"{key}"')
    lines += [
        "",
        f'[출력 형식] 키가 {", ".join(keys)}인 JSON 객체 하나. 각 값은 해당 섹션 본문 문자열.',
        f'본문 합계는 반드시 {cfg["min_chars"]}자 이상이어야 한다.',
    ]
    return "\n".join(lines)


def _build_user_prompt(reading_row) -> str:
    """SajuReading 행에서 만세력 엔진의 가용 데이터를 전부 컨텍스트로 구성."""
    payload = json.loads(reading_row.result_json)
    r, reading = payload["result"], payload["reading"]
    counts = reading["ohaeng_analysis"]["counts"]
    strong = [o for o, c in counts.items() if c == max(counts.values())]
    weak = [o for o, c in counts.items() if c == min(counts.values())]

    age = ""
    try:
        birth_year = int(reading_row.birth_solar.split("-")[0])
        age = f"만 {kst_today().year - birth_year}세 전후"
    except (ValueError, AttributeError):
        pass

    pillars = []
    for key, label in [("year", "년주"), ("month", "월주"), ("day", "일주"), ("hour", "시주")]:
        p = r.get(key)
        pillars.append(f"{label} {p['gapja']}" if p else f"{label} 모름")

    lines = [
        "[사주 데이터]",
        f"- 이름: {reading_row.name or '미입력'} / 성별: {reading_row.gender or '미입력'}",
        f"- 양력 생일: {reading_row.birth_solar}"
        + (f" {reading_row.birth_hour}시" if reading_row.birth_hour is not None else " (시간 모름)"),
        f"- 현재 나이: {age or '미상'}",
        f"- 사주 원국: {' · '.join(pillars)} (팔자: {reading_row.palja})",
        f"- 일간(日干): {reading['ilgan']}({reading['ilgan_ohaeng']})",
        f"- 오행 분포: " + " ".join(f"{o}{c}" for o, c in counts.items()),
        f"- 강한 오행: {'/'.join(strong)} · 약한 오행: {'/'.join(weak)}",
        f"- 오행 분석 요약: {reading['ohaeng_analysis']['text']}",
        "",
        "위 사주 데이터를 근거로 지정된 5개 섹션의 리포트를 JSON으로 작성하라.",
    ]
    return "\n".join(lines)


def _call_gemini_json(api_key, model, system_prompt, user_prompt, timeout=90):
    """Gemini generateContent — JSON 응답 모드. (ok: bool, data: dict|str) 반환."""
    if not api_key:
        return False, "GEMINI_API_KEY 미설정"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
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
        return True, json.loads(text)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        return False, str(e)


def _validate(cfg, data):
    """형식·분량 검증. 통과 시 sections 리스트 반환, 실패 시 None."""
    if not isinstance(data, dict):
        return None
    sections, total = [], 0
    for key, title, _guide in cfg["sections"]:
        body = data.get(key)
        if not isinstance(body, str) or len(body.strip()) < 100:
            return None
        body = body.strip().replace("**", "")  # 마크다운 굵게 잔재 방어적 제거
        total += len(body)
        sections.append({"key": key, "title": title, "body": body})
    if total < cfg["min_chars"]:
        return None
    return sections


def ensure_report(reading_row, product):
    """리포트 보장: 저장본(DONE)이 있으면 그대로, 없으면 생성 시도.

    리포트 대상 상품이 아니면 None. 실패 시 PENDING 상태의 SajuReport 반환.
    """
    cfg = REPORT_CONFIGS.get(product.slug) if product else None
    if cfg is None:
        return None

    report = SajuReport.query.filter_by(reading_id=reading_row.id).first()
    if report is not None and report.status == "DONE":
        return report                      # 저장본 재사용 — Gemini 재호출 금지
    if report is None:
        report = SajuReport(
            reading_id=reading_row.id, user_id=reading_row.user_id,
            product_id=product.id, status="PENDING",
        )
        db.session.add(report)
        db.session.commit()                # 실패해도 '생성 중' 건으로 남김

    model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
    ok, data = _call_gemini_json(
        current_app.config.get("GEMINI_API_KEY", ""), model,
        _build_system_prompt(cfg), _build_user_prompt(reading_row),
    )
    sections = _validate(cfg, data) if ok else None
    if sections is None:
        current_app.logger.warning(
            "report generation failed (reading=%s): %s",
            reading_row.id, data if not ok else "형식/분량 검증 실패",
        )
        db.session.commit()
        return report

    report.status = "DONE"
    report.content_json = json.dumps({"sections": sections}, ensure_ascii=False)
    report.model = model
    db.session.commit()
    return report


def report_sections(report):
    """저장된 리포트의 sections 리스트 (DONE이 아니면 빈 리스트)."""
    if report is None or report.status != "DONE" or not report.content_json:
        return []
    try:
        return json.loads(report.content_json)["sections"]
    except (ValueError, KeyError):
        return []
