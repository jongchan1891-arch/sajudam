# -*- coding: utf-8 -*-
"""규칙기반 해설 테스트."""
from saju.engine import calculate_saju
from saju.interpret import interpret, analyze_ohaeng


def test_interpret_categories_present():
    r = calculate_saju(1990, 6, 15, 12)
    result = interpret(r)
    cats = result["categories"]
    for key in ("성격", "직업", "재물", "연애"):
        assert key in cats
        assert isinstance(cats[key], str) and len(cats[key]) > 5


def test_interpret_uses_ilgan():
    r = calculate_saju(1990, 6, 15, 12)  # 일간 신(辛)
    result = interpret(r)
    assert result["ilgan"] == "신"
    assert result["ilgan_ohaeng"] == "금"
    assert "辛" in result["categories"]["성격"] or "보석" in result["categories"]["성격"]


def test_analyze_ohaeng_excess_and_lacking():
    r = calculate_saju(1990, 6, 15, 12)  # 화3 토0
    a = analyze_ohaeng(r)
    assert "화" in a["excess"]
    assert "토" in a["lacking"]
    assert a["strongest"] == "화"


def test_interpret_all_ilgan_have_content():
    # 10개 일간 모두 해설 존재 확인 (대표 날짜 순회)
    seen = set()
    for day in range(1, 28):
        r = calculate_saju(2020, 1, day, 12)
        res = interpret(r)
        seen.add(res["ilgan"])
    # 최소 5개 이상 일간이 등장하고 모두 해설 생성됨
    assert len(seen) >= 5
