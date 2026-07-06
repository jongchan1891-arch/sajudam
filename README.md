# 사주담 (SajuDam) — 만세력 사주팔자 웹사이트

Python + Flask 기반의 사주(四柱) 웹사이트입니다. 생년월일시를 입력하면 **실제 만세력 수준**으로
사주팔자를 계산하고, 오행 분석과 규칙 기반 운세 해설을 제공합니다. 회원가입/로그인과
토스페이먼츠 **테스트(샌드박스)** 결제까지 실제로 동작합니다.

> 포트폴리오·데모 목적입니다. 결제는 테스트 PG 환경이며 실제 청구는 없습니다.

**GitHub**: https://github.com/jongchan1891-arch/sajudam

## 주요 기능
- **정확한 사주 계산**: 양/음력 변환, 태양황경(절기) 기준 월주, 입춘 기준 년주, 시진 시주 보정
  - 년주: 입춘(태양황경 315°) 순간 기준
  - 월주: 태양황경 구간(12절기)으로 결정
  - 일주: 율리우스일(JDN) 기반 60갑자 (`(JDN + 49) % 60`) — 실제 만세력 일진과 일치 검증
  - 시주: 일간 기반 오서둔(五鼠遁), 23시 시작 2시간 블록
- **오행 분석**: 목·화·토·금·수 분포와 과다/부족 리포트
- **규칙 기반 해설**: 일간별 성격 + 직업·재물·연애 카테고리 (LLM 미사용)
- **회원**: 이메일/비밀번호 가입·로그인 (비밀번호 해시 저장)
- **결제**: 토스페이먼츠 샌드박스 연동, 마이페이지 이력 조회
- **디자인**: `design.png`(사주담) 시안 기반 — 웜 베이지·브라운·골드·네이비 팔레트

## 스크린샷

| 홈 (데스크톱) | 결과 (데스크톱) |
|:---:|:---:|
| ![홈 데스크톱](docs/screenshots/home-desktop.png) | ![결과 데스크톱](docs/screenshots/result-desktop.png) |

| 홈 (모바일 375px) | 결과 (모바일 375px) |
|:---:|:---:|
| <img src="docs/screenshots/home-mobile.png" alt="홈 모바일" width="300"> | <img src="docs/screenshots/result-mobile.png" alt="결과 모바일" width="300"> |

## 설치
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 실행
```bash
python app.py
# 기본 http://127.0.0.1:5000  (포트 변경: PORT=5001 python app.py)
```
최초 실행 시 `saju.db`(SQLite)가 자동 생성됩니다.

## 테스트
```bash
pytest -q
```
`tests/test_engine.py`는 알려진 만세력 일진/사주와 일치하는지 검증합니다
(예: 1990-06-15 12시 → 경오·임오·신해·갑오, 2024-01-01 → 갑자일).

## 테스트 결제 (토스페이먼츠 샌드박스)
1. `해석 상품` → 상품의 `결제하기` → 결제 버튼 클릭
2. 토스 결제창에서 **테스트 카드**로 결제
   - 카드번호: 아무 테스트 카드(예: `4330-1234-1234-1234`)
   - 유효기간: 미래 임의값 / 비밀번호·생년월일: 임의값
3. 승인되면 결제 내역이 저장되고 마이페이지에서 확인됩니다.

> 실제 서비스 시 `config.py`의 `TOSS_CLIENT_KEY`/`TOSS_SECRET_KEY`를 본인 키로 교체하세요
> (환경변수 `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY`, `SECRET_KEY`, `DATABASE_URL` 지원).

## 구조
```
사주/
├── app.py              # Flask 팩토리 + 라우트(스토어 홈/사주풀이/상품 상세/리뷰/마이)
├── config.py           # 설정 (DB, 토스 키)
├── models.py           # User / Product / Review / SajuReading / Payment
├── seed.py             # 초기 풀이 상품 시드 (캐릭터: 재록·연화·월하)
├── auth.py             # 회원가입 / 로그인 / 로그아웃 (Blueprint)
├── payment.py          # 토스페이먼츠 샌드박스 결제 — Product 기반 (Blueprint)
├── web_utils.py        # 세션 사용자 / login_required / 상품 접근 권한
├── saju/
│   ├── calendar_util.py # 만세력: 음양력 변환, 절기(ephem), 일주(JDN)
│   ├── engine.py        # 사주팔자 계산 (년/월/일/시주, 오행)
│   ├── interpret.py     # 규칙 기반 해설
│   └── product_config.py# 상품별 해설 구성(섹션·캐릭터 멘트·집중 조언)
├── templates/          # Jinja2 (base 상속, design.png 시안)
├── static/css/style.css# 디자인 시스템 (사주담 팔레트)
└── tests/              # pytest (engine / interpret / web)
```

## 참고 · 한계
- 시간대는 KST(UTC+9) 기준. 진태양시(경도·균시차) 보정은 적용하지 않았습니다(대부분의 만세력 앱 기본 동작과 동일).
- 일주 경계는 자정(00:00) 기준입니다(야자시 미적용).
- 사주 해석은 규칙 기반 일반 해설이며 전문 상담을 대체하지 않습니다.
