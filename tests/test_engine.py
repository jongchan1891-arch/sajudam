# -*- coding: utf-8 -*-
"""사주 엔진 / 만세력 검증 테스트."""
from saju.calendar_util import (
    day_ganzi_index, month_branch_from_longitude, solar_to_lunar, lunar_to_solar,
    julian_day_number,
)
from saju.engine import calculate_saju, CHEONGAN, JIJI


# ---- 일주(60갑자) 검증: 알려진 만세력 일진 -------------------------
def test_day_pillar_known_dates():
    # (양력, 기대 일간, 기대 일지)
    cases = [
        (2024, 1, 1, "갑", "자"),   # 갑자일
        (1990, 6, 15, "신", "해"),  # 신해일
        (2000, 1, 1, "무", "오"),   # 무오일
        (1984, 2, 2, "병", "인"),   # 병인일
        (1936, 2, 13, "을", "축"),  # 을축일
    ]
    for y, m, d, gan, ji in cases:
        idx = day_ganzi_index(y, m, d)
        assert CHEONGAN[idx % 10] == gan, f"{y}-{m}-{d} 일간"
        assert JIJI[idx % 12] == ji, f"{y}-{m}-{d} 일지"


def test_julian_day_number():
    # J2000.0 = 2000-01-01 (정오) JDN 2451545
    assert julian_day_number(2000, 1, 1) == 2451545


# ---- 월지: 태양황경 구간 --------------------------------------------
def test_month_branch_from_longitude():
    assert month_branch_from_longitude(320) == 2   # 인월
    assert month_branch_from_longitude(0) == 3      # 묘월 (청명 전)
    assert month_branch_from_longitude(90) == 6     # 오월
    assert month_branch_from_longitude(280) == 0    # 자월
    assert month_branch_from_longitude(300) == 1    # 축월


# ---- 전체 사주 검증: 알려진 사주 ------------------------------------
def _pillars(r):
    return (
        r.year_pillar.gapja, r.month_pillar.gapja,
        r.day_pillar.gapja, r.hour_pillar.gapja if r.hour_pillar else None,
    )


def test_full_saju_1990():
    r = calculate_saju(1990, 6, 15, 12, gender="남")
    assert _pillars(r) == ("경오", "임오", "신해", "갑오")
    assert r.saju_year == 1990


def test_full_saju_2000_newyear():
    # 입춘 이전이므로 사주년 1999(기묘)
    r = calculate_saju(2000, 1, 1, 0)
    assert _pillars(r) == ("기묘", "병자", "무오", "임자")
    assert r.saju_year == 1999


def test_ipchun_year_boundary():
    before = calculate_saju(2024, 1, 20, 10)   # 입춘 전 -> 2023 계묘
    after = calculate_saju(2024, 2, 10, 10)    # 입춘 후 -> 2024 갑진
    assert before.year_pillar.gapja == "계묘"
    assert before.saju_year == 2023
    assert after.year_pillar.gapja == "갑진"
    assert after.saju_year == 2024


def test_hour_pillar_by_ilgan():
    # 갑일 04시(인시) -> 병인시 (오서둔: 갑일 갑자시)
    r = calculate_saju(2024, 1, 1, 4)
    assert r.day_pillar.gan == "갑"
    assert r.hour_pillar.gapja == "병인"


def test_hour_unknown_omits_hour_pillar():
    r = calculate_saju(1990, 6, 15, None)
    assert r.hour_pillar is None
    assert r.hour_known is False
    # 3주만 계산되어 오행 총합 6
    assert sum(r.ohaeng_count.values()) == 6


def test_full_saju_has_8_chars_with_hour():
    r = calculate_saju(1990, 6, 15, 12)
    assert sum(r.ohaeng_count.values()) == 8  # 4주 x 2


# ---- 음/양력 변환 ----------------------------------------------------
def test_solar_lunar_roundtrip():
    lun = solar_to_lunar(2000, 1, 1)
    assert lun[:3] == (1999, 11, 25)
    sol = lunar_to_solar(1999, 11, 25, False)
    assert sol == (2000, 1, 1)


def test_lunar_input_calculation():
    # 음력 입력이 동일 양력으로 변환되어 계산되는지
    r_lunar = calculate_saju(1990, 5, 23, 12, is_lunar=True)
    r_solar = calculate_saju(1990, 6, 15, 12, is_lunar=False)
    assert _pillars(r_lunar) == _pillars(r_solar)


# ---- 오행 집계 -------------------------------------------------------
def test_ohaeng_count_sum():
    r = calculate_saju(1990, 6, 15, 12)
    assert r.ohaeng_count == {"목": 1, "화": 3, "토": 0, "금": 2, "수": 2}
