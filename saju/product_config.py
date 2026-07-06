# -*- coding: utf-8 -*-
"""상품별 해설 구성 (US-014).

사주 엔진(engine.calculate_saju)과 기본 해설(interpret.interpret)은 수정 없이
재사용하고, 그 위에서 상품마다 섹션 구성·인트로/아웃트로·집중 조언을 다르게
조립한다. 규칙 기반(LLM 미사용).
"""

SECTION_ICONS = {"성격": "◍", "직업": "◎", "재물": "◈", "연애": "❀"}

# 상품 슬러그 -> 해설 구성
#  sections: interpret() categories 중 포함할 섹션과 순서
#  intro/outro: 캐릭터 멘트 템플릿 ({name}, {ilgan}, {ilgan_ohaeng} 치환)
#  focus: 집중 조언 섹션을 만들 주제 (오행 분석 기반 규칙 생성)
PRODUCT_CONFIGS = {
    "jaerok-free": {
        "sections": ["성격", "재물"],
        "intro": "안녕하세요, 재록이입니다! {name}님의 일간은 {ilgan}({ilgan_ohaeng}) — "
                 "곳간 문을 살짝 열어 기운의 결부터 보여드릴게요.",
        "outro": "여기까지는 맛보기예요. 곳간이 언제, 어떻게 차오르는지는 "
                 "재록이의 재물운 심층풀이에서 주판을 제대로 놓아 드립니다.",
    },
    "jaerok-money": {
        "sections": ["재물", "직업", "성격"],
        "intro": "재록이가 주판을 놓으며 {name}님의 곳간을 깊이 들여다봅니다. "
                 "{ilgan}({ilgan_ohaeng}) 일간의 재물 그릇부터 살펴볼게요.",
        "focus": "재물",
        "focus_title": "재록이의 곳간 조언",
    },
    "yeonhwa-love": {
        "sections": ["연애", "성격"],
        "intro": "연화가 {name}님 인연의 결을 읽어드립니다. "
                 "{ilgan}({ilgan_ohaeng}) 일간은 사랑 앞에서 이런 얼굴을 하고 있어요.",
        "focus": "연애",
        "focus_title": "연화의 인연 조언",
    },
    "wolha-rejoin": {
        "sections": ["연애", "성격"],
        "intro": "월하가 달빛 아래에서 {name}님의 지난 인연을 비추어 봅니다. "
                 "{ilgan}({ilgan_ohaeng}) 일간의 마음결부터 짚어볼게요.",
        "focus": "연애",
        "focus_title": "월하의 재회 실마리",
        "outro": "재회는 시기보다 준비가 먼저입니다. 부족한 기운을 채우는 동안 "
                 "마음의 문장도 함께 다듬어 보세요.",
    },
    "premium-total": {
        "sections": ["성격", "직업", "재물", "연애"],
        "intro": "사주담이 {name}님의 원국 전체를 정성껏 풀어드립니다.",
        "focus": "종합",
        "focus_title": "사주담의 종합 조언",
    },
}

# 상품 없이 계산했을 때(기본 무료 풀이)의 구성 — 기존 v1 결과와 동일
DEFAULT_CONFIG = {"sections": ["성격", "직업", "재물", "연애"]}

# 집중 조언 규칙: 주제 × 오행 상태 조합으로 문장 생성
_FOCUS_STRONG = {
    "재물": "가장 강한 {strongest} 기운이 수입의 물꼬입니다. {strongest} 기운과 어울리는 "
            "분야에 집중하면 재물의 흐름이 굵어집니다.",
    "연애": "가장 강한 {strongest} 기운이 매력의 원천입니다. 그 기운이 잘 드러나는 "
            "자리에서 인연이 자연스럽게 다가옵니다.",
    "종합": "가장 강한 {strongest} 기운을 삶의 축으로 삼으세요. 큰 결정일수록 "
            "이 기운이 살아나는 방향이 순리입니다.",
}
_FOCUS_LACKING = {
    "재물": "{lacking} 기운이 비어 있어 혼자 움직이면 새는 곳이 생깁니다. 이 기운을 "
            "가진 사람·환경과의 협력이 곳간의 빈틈을 메워 줍니다.",
    "연애": "{lacking} 기운이 비어 있어 관계에서 같은 자리를 맴돌 수 있습니다. 이 기운을 "
            "지닌 상대가 의외로 편안한 짝이 됩니다.",
    "종합": "{lacking} 기운이 비어 있으니 이를 보완하는 활동과 사람을 곁에 두면 "
            "전체 운의 균형이 살아납니다.",
}
_FOCUS_BALANCED = {
    "재물": "오행이 고르게 갖춰져 꾸준함이 곧 재물이 되는 사주입니다. 급한 승부보다 "
            "쌓아 올리는 전략이 유리합니다.",
    "연애": "오행이 고르게 갖춰져 어느 인연과도 결이 크게 어긋나지 않습니다. 다만 "
            "그만큼 스스로 마음을 정하는 일이 관건입니다.",
    "종합": "오행이 고르게 갖춰진 균형 사주입니다. 흐름을 크게 거스르지 않으면 "
            "안정적으로 운이 이어집니다.",
}


def _focus_text(topic: str, reading: dict) -> str:
    oh = reading["ohaeng_analysis"]
    parts = [_FOCUS_STRONG[topic].format(strongest=oh["strongest"])]
    if oh["lacking"]:
        parts.append(_FOCUS_LACKING[topic].format(lacking="·".join(oh["lacking"])))
    elif not oh["excess"]:
        parts.append(_FOCUS_BALANCED[topic])
    return " ".join(parts)


def compose_reading(product_slug, reading: dict, name: str = "") -> dict:
    """interpret() 결과를 상품 구성에 맞춰 조립한다.

    반환: {"intro": str|None, "outro": str|None,
           "sections": [(제목, 아이콘, 본문), ...]}
    """
    cfg = PRODUCT_CONFIGS.get(product_slug, DEFAULT_CONFIG)
    ctx = {
        "name": name or "회원",
        "ilgan": reading["ilgan"],
        "ilgan_ohaeng": reading["ilgan_ohaeng"],
    }
    sections = [
        (cat, SECTION_ICONS.get(cat, "✦"), reading["categories"][cat])
        for cat in cfg["sections"]
    ]
    if cfg.get("focus"):
        sections.append(
            (cfg.get("focus_title", "집중 조언"), "✦", _focus_text(cfg["focus"], reading))
        )
    return {
        "intro": cfg["intro"].format(**ctx) if cfg.get("intro") else None,
        "outro": cfg["outro"].format(**ctx) if cfg.get("outro") else None,
        "sections": sections,
    }
