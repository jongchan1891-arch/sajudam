# -*- coding: utf-8 -*-
"""초기 상품 시드 데이터 (US-014). slug 기준으로 없을 때만 추가(멱등)."""
from models import db, Product

PRODUCT_SEED = [
    dict(
        slug="jaerok-free", character_name="재록", name="재록이의 무료 사주 맛보기",
        tagline="곳간 문을 살짝 열어보는 무료 풀이", category="종합", price=0,
        thumbnail="jaerok_free.jpg", hero_image="jaerok_hero.jpg",
        description="사주담의 재물 도령 재록이가 만세력으로 계산한 사주 원국과 오행 "
                    "분포, 성격·재물의 기본 결을 무료로 짚어 드립니다. 부담 없이 "
                    "시작해 보세요.",
    ),
    dict(
        slug="jaerok-money", character_name="재록", name="재록이의 재물운 심층풀이",
        tagline="당신의 곳간은 언제 차오를까?", category="재물", price=9900,
        thumbnail="jaerok_paid.jpg", hero_image="jaerok_hero.jpg",
        description="주판을 든 재물 도령 재록이가 일간의 재물 그릇, 강한 기운의 "
                    "수입원, 비어 있는 기운의 보완법까지 곳간의 흐름을 깊이 "
                    "풀어드립니다.",
    ),
    dict(
        slug="yeonhwa-love", character_name="연화", name="연화의 연애운 풀이",
        tagline="인연의 결, 오행으로 읽어드립니다", category="연애", price=7900,
        thumbnail=None, hero_image=None,
        description="연화가 일간의 연애 성향과 어울리는 인연의 결을 짚고, 사랑 앞에서 "
                    "빛나는 기운과 조심할 기운을 알려드립니다.",
    ),
    dict(
        slug="wolha-rejoin", character_name="월하", name="월하의 재회 가능성 풀이",
        tagline="끝난 인연일까, 쉬어가는 인연일까", category="재회", price=12900,
        thumbnail=None, hero_image=None,
        description="달빛 아래 월하가 지난 인연의 매듭을 살핍니다. 마음결과 기운의 "
                    "빈자리를 짚어 재회의 실마리를 건네드립니다.",
    ),
    dict(
        slug="premium-total", character_name="사주담", name="프리미엄 종합 사주",
        tagline="대운·세운까지 담은 가장 깊은 풀이", category="종합", price=29900,
        thumbnail=None, hero_image=None,
        description="성격·직업·재물·연애 전 영역에 종합 조언까지, 사주담이 원국 "
                    "전체를 가장 깊게 풀어드리는 프리미엄 상품입니다.",
    ),
]


def seed_products() -> None:
    added = False
    for row in PRODUCT_SEED:
        if Product.query.filter_by(slug=row["slug"]).first() is None:
            db.session.add(Product(**row))
            added = True
    if added:
        db.session.commit()
