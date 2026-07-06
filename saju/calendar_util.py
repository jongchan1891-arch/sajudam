# -*- coding: utf-8 -*-
"""만세력 기반 달력/천문 유틸.

- 양력 <-> 음력 변환 (korean_lunar_calendar)
- 태양 황경(ephem) 기반 절기 계산: 월주는 황경 구간, 년주는 입춘 순간 기준
- 율리우스일(JDN) 기반 일주(60갑자) 계산  (day_index = (JDN + 49) % 60)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import ephem
from korean_lunar_calendar import KoreanLunarCalendar

KST_OFFSET = timedelta(hours=9)

# 12 節(월 시작 절기)의 태양황경 -> 월지(지지) index
#   자=0 축=1 인=2 ... 해=11
# 인월 315~345, 묘월 345~15, ... (경계 절기: 입춘/경칩/청명/입하/망종/소서/입추/백로/한로/입동/대설/소한)
def month_branch_from_longitude(lon: float) -> int:
    """태양 황경(도, 0~360)으로 사주 월지 index 반환."""
    lon = lon % 360.0
    # (하한 황경, 월지 index)  — 인(2)월부터 순서대로
    bounds = [
        (315.0, 2),   # 입춘  -> 인
        (345.0, 3),   # 경칩  -> 묘
        (15.0, 4),    # 청명  -> 진
        (45.0, 5),    # 입하  -> 사
        (75.0, 6),    # 망종  -> 오
        (105.0, 7),   # 소서  -> 미
        (135.0, 8),   # 입추  -> 신
        (165.0, 9),   # 백로  -> 유
        (195.0, 10),  # 한로  -> 술
        (225.0, 11),  # 입동  -> 해
        (255.0, 0),   # 대설  -> 자
        (285.0, 1),   # 소한  -> 축
    ]
    # 각 구간 [start, start+30) 안에 lon이 있는지 검사 (청명 15도 구간은 wrap)
    for start, branch in bounds:
        end = (start + 30.0) % 360.0
        if start < end:
            if start <= lon < end:
                return branch
        else:  # wrap (예: 345~15)
            if lon >= start or lon < end:
                return branch
    return 2  # 이론상 도달하지 않음


def sun_ecliptic_longitude(dt_utc: datetime) -> float:
    """UTC datetime에서 태양의 겉보기 황경(도) 반환."""
    sun = ephem.Sun(dt_utc)
    ecl = ephem.Ecliptic(sun)
    return math.degrees(ecl.lon) % 360.0


def _solar_term_utc(year: int, target_lon: float, approx_month: int, approx_day: int) -> datetime:
    """해당 연도에서 태양황경이 target_lon이 되는 UTC 순간을 이분탐색으로 계산."""
    lo = datetime(year, approx_month, approx_day) - timedelta(days=10)
    hi = lo + timedelta(days=20)
    for _ in range(60):
        mid = lo + (hi - lo) / 2
        diff = ((sun_ecliptic_longitude(mid) - target_lon + 180.0) % 360.0) - 180.0
        if diff < 0:
            lo = mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def ipchun_utc(year: int) -> datetime:
    """해당 연도 입춘(태양황경 315도) 순간 (UTC)."""
    return _solar_term_utc(year, 315.0, 2, 4)


def kst_to_utc(dt_kst: datetime) -> datetime:
    return dt_kst - KST_OFFSET


def julian_day_number(year: int, month: int, day: int) -> int:
    """그레고리력 날짜의 율리우스일(JDN, 정오 기준 정수)."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def day_ganzi_index(year: int, month: int, day: int) -> int:
    """일주 60갑자 index (0=갑자). 자정(KST) 경계."""
    return (julian_day_number(year, month, day) + 49) % 60


def solar_to_lunar(year: int, month: int, day: int):
    """양력 -> 음력. (lunar_year, lunar_month, lunar_day, is_intercalation)."""
    c = KoreanLunarCalendar()
    ok = c.setSolarDate(year, month, day)
    if not ok:
        return None
    return (c.lunarYear, c.lunarMonth, c.lunarDay, c.isIntercalation)


def lunar_to_solar(year: int, month: int, day: int, is_intercalation: bool = False):
    """음력 -> 양력. (solar_year, solar_month, solar_day)."""
    c = KoreanLunarCalendar()
    ok = c.setLunarDate(year, month, day, is_intercalation)
    if not ok:
        return None
    return (c.solarYear, c.solarMonth, c.solarDay)
