# -*- coding: utf-8 -*-
"""규칙 기반 사주 해설 생성 (LLM 미사용)."""
from __future__ import annotations

from .engine import (
    SajuResult, CHEONGAN, CHEONGAN_OHAENG, OHAENG_LIST,
)

# 일간(日干)별 성격 해설
ILGAN_PERSONALITY = {
    "갑": "큰 나무(甲木)의 기운입니다. 곧고 진취적이며 리더십이 강합니다. 자존심이 높고 명분을 중시하나, 융통성이 부족할 때가 있습니다.",
    "을": "화초·덩굴(乙木)의 기운입니다. 유연하고 섬세하며 적응력이 뛰어납니다. 협력적이고 현실적이나, 우유부단할 수 있습니다.",
    "병": "태양(丙火)의 기운입니다. 밝고 열정적이며 표현력이 풍부합니다. 솔직하고 화끈하나, 감정 기복과 성급함을 조심해야 합니다.",
    "정": "등불·촛불(丁火)의 기운입니다. 따뜻하고 섬세하며 헌신적입니다. 예술적 감각과 배려심이 크나, 예민한 편입니다.",
    "무": "큰 산·대지(戊土)의 기운입니다. 듬직하고 포용력이 크며 신용이 있습니다. 중심을 잘 잡으나, 고집과 변화에 대한 저항이 있습니다.",
    "기": "논밭·정원(己土)의 기운입니다. 실속 있고 꼼꼼하며 현실적입니다. 포용력과 인내심이 있으나, 걱정이 많은 편입니다.",
    "경": "무쇠·원석(庚金)의 기운입니다. 강직하고 의리가 있으며 결단력이 뛰어납니다. 추진력이 강하나, 다소 거칠고 융통성이 부족할 수 있습니다.",
    "신": "보석·칼(辛金)의 기운입니다. 예리하고 세련되며 완벽주의 성향이 있습니다. 자존심이 높고 미적 감각이 뛰어나나, 예민합니다.",
    "임": "바다·강(壬水)의 기운입니다. 지혜롭고 포용력이 크며 활동적입니다. 스케일이 크고 융통성이 있으나, 변덕과 산만함을 조심해야 합니다.",
    "계": "이슬·빗물(癸水)의 기운입니다. 총명하고 섬세하며 상상력이 풍부합니다. 감수성과 직관이 뛰어나나, 소심하거나 생각이 많습니다.",
}

# 오행별 직업 적성
OHAENG_CAREER = {
    "목": "교육, 기획, 출판, 목재·섬유, 의료·제약, 성장 산업 등 뻗어나가는 분야",
    "화": "방송·미디어, 예술·공연, IT·전자, 요식, 마케팅 등 표현하고 빛나는 분야",
    "토": "부동산, 건설, 농업, 중개·유통, 공직·행정 등 안정적이고 신뢰가 필요한 분야",
    "금": "금융, 법률, 군·경, 기계·제조, 의료(외과), 스포츠 등 결단과 정밀함의 분야",
    "수": "연구·학문, 무역·유통, 물류, 요식·수산, 컨설팅 등 유동적이고 지혜가 필요한 분야",
}

# 오행별 연애 성향 (일간 오행 기준)
OHAENG_LOVE = {
    "목": "다정하고 배려심이 많은 연애를 합니다. 상대의 성장을 돕는 편이지만, 자기 뜻을 굽히지 않을 때가 있습니다.",
    "화": "표현이 풍부하고 정열적인 연애를 합니다. 사랑에 빠지면 화끈하나, 감정 기복을 관리하면 좋습니다.",
    "토": "믿음직하고 안정적인 연애를 합니다. 헌신적이지만 표현이 서툴 수 있어 마음을 자주 전하면 좋습니다.",
    "금": "의리 있고 진중한 연애를 합니다. 한번 마음을 주면 깊으나, 자존심 때문에 먼저 다가서길 어려워합니다.",
    "수": "센스 있고 이해심 깊은 연애를 합니다. 상대를 잘 파악하지만, 속마음을 잘 드러내지 않는 편입니다.",
}


def analyze_ohaeng(result: SajuResult) -> dict:
    """오행 분포의 과다/부족 분석."""
    counts = result.ohaeng_count
    total = sum(counts.values())
    excess = [o for o, c in counts.items() if c >= 3]
    lacking = [o for o, c in counts.items() if c == 0]
    strongest = max(counts, key=counts.get)
    weakest = min(counts, key=counts.get)

    parts = []
    dist = ", ".join(f"{o} {counts[o]}개" for o in OHAENG_LIST)
    parts.append(f"오행 분포는 {dist} 입니다 (총 {total}개).")
    if excess:
        parts.append(f"{'·'.join(excess)} 기운이 강하여 해당 성향이 두드러집니다.")
    if lacking:
        parts.append(f"{'·'.join(lacking)} 기운이 없어 이를 보완하는 활동·환경이 도움이 됩니다.")
    if not excess and not lacking:
        parts.append("오행이 비교적 고르게 분포되어 균형이 잡힌 사주입니다.")
    parts.append(f"가장 강한 기운은 {strongest}, 가장 약한 기운은 {weakest} 입니다.")

    return {
        "text": " ".join(parts),
        "counts": counts,
        "excess": excess,
        "lacking": lacking,
        "strongest": strongest,
        "weakest": weakest,
    }


def _wealth_text(result: SajuResult, ohaeng: dict) -> str:
    """재물운: 일간과 오행 균형 기반."""
    il = result.il_gan
    il_ohaeng = CHEONGAN_OHAENG[CHEONGAN.index(il)]
    base = {
        "목": "성실하게 쌓아가는 재물운입니다. 꾸준함이 곧 자산이 됩니다.",
        "화": "기회를 빠르게 포착하는 재물운입니다. 다만 지출 관리가 관건입니다.",
        "토": "안정적으로 모으는 재물운입니다. 부동산·현물 자산과 인연이 있습니다.",
        "금": "결단으로 큰 재물을 만드는 힘이 있습니다. 재물의 흐름을 잘 통제합니다.",
        "수": "융통성 있게 굴리는 재물운입니다. 정보와 인맥이 재물로 이어집니다.",
    }[il_ohaeng]
    if ohaeng["excess"]:
        base += " 특정 기운이 강하니 한 분야에 집중하되 과욕은 경계하세요."
    if ohaeng["lacking"]:
        base += " 부족한 기운을 채워줄 동업·협력이 재물운을 보완합니다."
    return base


def interpret(result: SajuResult) -> dict:
    """사주 결과로 카테고리별 규칙기반 해설을 생성한다."""
    il = result.il_gan
    il_ohaeng = CHEONGAN_OHAENG[CHEONGAN.index(il)]
    ohaeng = analyze_ohaeng(result)

    personality = ILGAN_PERSONALITY[il]
    if ohaeng["excess"]:
        personality += f" 사주에 {'·'.join(ohaeng['excess'])} 기운이 강해 그 특성이 더 뚜렷합니다."

    career = f"일간이 {il}({il_ohaeng})이며, {OHAENG_CAREER[il_ohaeng]}에 적성이 있습니다."
    if ohaeng["strongest"] != il_ohaeng:
        career += f" 사주 전체로는 {ohaeng['strongest']} 기운도 강해 {OHAENG_CAREER[ohaeng['strongest']].split(',')[0]} 분야와도 인연이 있습니다."

    love = OHAENG_LOVE[il_ohaeng]
    wealth = _wealth_text(result, ohaeng)

    return {
        "ilgan": il,
        "ilgan_ohaeng": il_ohaeng,
        "ohaeng_analysis": ohaeng,
        "categories": {
            "성격": personality,
            "직업": career,
            "재물": wealth,
            "연애": love,
        },
    }
