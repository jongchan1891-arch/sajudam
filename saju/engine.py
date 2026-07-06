# -*- coding: utf-8 -*-
"""사주팔자(四柱八字) 계산 엔진."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from . import calendar_util as cal

# ---- 상수 -------------------------------------------------------------
CHEONGAN = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
CHEONGAN_HANJA = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
JIJI = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]
JIJI_HANJA = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 오행: 목 화 토 금 수
CHEONGAN_OHAENG = ["목", "목", "화", "화", "토", "토", "금", "금", "수", "수"]
JIJI_OHAENG = ["수", "토", "목", "목", "토", "화", "화", "토", "금", "금", "토", "수"]

# 음양 (양=True)
CHEONGAN_YINYANG = [True, False, True, False, True, False, True, False, True, False]
JIJI_YINYANG = [True, False, True, False, True, False, True, False, True, False, True, False]

OHAENG_LIST = ["목", "화", "토", "금", "수"]
JIJI_ZODIAC = ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]

# 1984 = 갑자년(甲子年) 기준
YEAR_ANCHOR = 1984


@dataclass
class Pillar:
    """하나의 기둥(주): 천간 + 지지."""
    gan_index: int
    ji_index: int

    @property
    def gan(self) -> str:
        return CHEONGAN[self.gan_index]

    @property
    def ji(self) -> str:
        return JIJI[self.ji_index]

    @property
    def gan_hanja(self) -> str:
        return CHEONGAN_HANJA[self.gan_index]

    @property
    def ji_hanja(self) -> str:
        return JIJI_HANJA[self.ji_index]

    @property
    def gapja(self) -> str:
        return self.gan + self.ji

    @property
    def gapja_hanja(self) -> str:
        return self.gan_hanja + self.ji_hanja

    def to_dict(self) -> dict:
        return {
            "gan": self.gan, "ji": self.ji,
            "gan_hanja": self.gan_hanja, "ji_hanja": self.ji_hanja,
            "gan_ohaeng": CHEONGAN_OHAENG[self.gan_index],
            "ji_ohaeng": JIJI_OHAENG[self.ji_index],
            "gapja": self.gapja, "gapja_hanja": self.gapja_hanja,
        }


@dataclass
class SajuResult:
    year_pillar: Pillar
    month_pillar: Pillar
    day_pillar: Pillar
    hour_pillar: Optional[Pillar]
    ohaeng_count: dict = field(default_factory=dict)
    lunar: Optional[tuple] = None
    saju_year: int = 0
    gender: str = ""
    solar_date: str = ""
    hour_known: bool = True

    @property
    def day_gan_index(self) -> int:
        return self.day_pillar.gan_index

    @property
    def il_gan(self) -> str:
        """일간(日干) — 사주의 주체."""
        return self.day_pillar.gan

    def pillars(self):
        ps = [self.year_pillar, self.month_pillar, self.day_pillar]
        if self.hour_pillar is not None:
            ps.append(self.hour_pillar)
        return ps

    def to_dict(self) -> dict:
        return {
            "year": self.year_pillar.to_dict(),
            "month": self.month_pillar.to_dict(),
            "day": self.day_pillar.to_dict(),
            "hour": self.hour_pillar.to_dict() if self.hour_pillar else None,
            "ohaeng_count": self.ohaeng_count,
            "il_gan": self.il_gan,
            "il_gan_ohaeng": CHEONGAN_OHAENG[self.day_gan_index],
            "day_zodiac": JIJI_ZODIAC[self.day_pillar.ji_index],
            "year_zodiac": JIJI_ZODIAC[self.year_pillar.ji_index],
            "lunar": self.lunar,
            "saju_year": self.saju_year,
            "gender": self.gender,
            "solar_date": self.solar_date,
            "hour_known": self.hour_known,
        }


def _year_pillar(saju_year: int) -> Pillar:
    gan = (saju_year - YEAR_ANCHOR) % 10
    ji = (saju_year - YEAR_ANCHOR) % 12
    return Pillar(gan, ji)


def _month_pillar(year_gan_index: int, month_ji_index: int) -> Pillar:
    """오호둔(五虎遁): 년간으로 인월 천간 결정, 이후 월 순서대로 증가."""
    # 인월(寅) 천간 = (년간 % 5) * 2 + 2 (mod 10)
    ipwol_gan = ((year_gan_index % 5) * 2 + 2) % 10
    # 월 순서: 인(2)월을 0으로
    month_order = (month_ji_index - 2) % 12
    gan = (ipwol_gan + month_order) % 10
    return Pillar(gan, month_ji_index)


def _day_pillar(year: int, month: int, day: int) -> Pillar:
    idx = cal.day_ganzi_index(year, month, day)
    return Pillar(idx % 10, idx % 12)


def _hour_branch_index(hour: int) -> int:
    """23~00시 = 자시(0). ((hour+1)//2) % 12."""
    return ((hour + 1) // 2) % 12


def _hour_pillar(day_gan_index: int, hour: int) -> Pillar:
    """오서둔(五鼠遁): 일간으로 자시 천간 결정."""
    hour_ji = _hour_branch_index(hour)
    # 자시 천간 = (일간 % 5) * 2 (mod 10)
    jasi_gan = ((day_gan_index % 5) * 2) % 10
    gan = (jasi_gan + hour_ji) % 10
    return Pillar(gan, hour_ji)


def _count_ohaeng(pillars) -> dict:
    counts = {o: 0 for o in OHAENG_LIST}
    for p in pillars:
        counts[CHEONGAN_OHAENG[p.gan_index]] += 1
        counts[JIJI_OHAENG[p.ji_index]] += 1
    return counts


def calculate_saju(
    year: int, month: int, day: int,
    hour: Optional[int] = None, minute: int = 0,
    is_lunar: bool = False, is_intercalation: bool = False,
    gender: str = "",
) -> SajuResult:
    """생년월일시로 사주를 계산한다.

    year/month/day: 양력 또는 음력(is_lunar=True)
    hour: 0~23 (KST). None이면 시주 생략(시간 모름)
    """
    # 1) 입력이 음력이면 양력으로 변환
    if is_lunar:
        conv = cal.lunar_to_solar(year, month, day, is_intercalation)
        if conv is None:
            raise ValueError("유효하지 않은 음력 날짜입니다.")
        year, month, day = conv

    hour_known = hour is not None
    calc_hour = hour if hour_known else 12  # 표기용 기본값(사용 안 함)

    birth_kst = datetime(year, month, day, calc_hour, minute)
    birth_utc = cal.kst_to_utc(birth_kst)

    # 2) 사주년 결정 (입춘 기준)
    saju_year = year
    if birth_utc < cal.ipchun_utc(year):
        saju_year -= 1

    year_pillar = _year_pillar(saju_year)

    # 3) 월지: 태양황경 구간
    lon = cal.sun_ecliptic_longitude(birth_utc)
    month_ji = cal.month_branch_from_longitude(lon)
    month_pillar = _month_pillar(year_pillar.gan_index, month_ji)

    # 4) 일주
    day_pillar = _day_pillar(year, month, day)

    # 5) 시주
    hour_pillar = _hour_pillar(day_pillar.gan_index, hour) if hour_known else None

    pillars = [year_pillar, month_pillar, day_pillar]
    if hour_pillar is not None:
        pillars.append(hour_pillar)
    ohaeng = _count_ohaeng(pillars)

    lunar = cal.solar_to_lunar(year, month, day)

    return SajuResult(
        year_pillar=year_pillar,
        month_pillar=month_pillar,
        day_pillar=day_pillar,
        hour_pillar=hour_pillar,
        ohaeng_count=ohaeng,
        lunar=lunar,
        saju_year=saju_year,
        gender=gender,
        solar_date=f"{year:04d}-{month:02d}-{day:02d}",
        hour_known=hour_known,
    )
