# -*- coding: utf-8 -*-
"""서버 없이 브라우저로 직접 열어볼 수 있는 정적 HTML을 preview/ 폴더로 내보낸다.

사용법: venv\Scripts\python export_preview.py  →  preview\index.html 더블클릭
(폼 제출·로그인·결제 등 서버 기능은 정적 파일에서는 동작하지 않는다.)
"""
import shutil
from pathlib import Path

from app import create_app
from config import TestConfig
from models import db

ROOT = Path(__file__).parent
OUT = ROOT / "preview"

# 라우트 → 저장 파일명 (링크 재작성에도 사용)
PAGES = {
    "/": "index.html",
    "/pricing": "pricing.html",
    "/login": "login.html",
    "/signup": "signup.html",
}

app = create_app(TestConfig)
with app.app_context():
    db.create_all()
client = app.test_client()


def to_static_html(html: str) -> str:
    # file:// 에서도 동작하도록 절대경로를 상대경로로 재작성
    html = html.replace('"/static/', '"static/')
    for route, fname in PAGES.items():
        html = html.replace(f'href="{route}"', f'href="{fname}"')
    return html


OUT.mkdir(exist_ok=True)
shutil.copytree(ROOT / "static", OUT / "static", dirs_exist_ok=True)

for route, fname in PAGES.items():
    body = client.get(route).data.decode("utf-8")
    (OUT / fname).write_text(to_static_html(body), encoding="utf-8")
    print("saved", fname)

# 샘플 결과 페이지 (홍길동 1990-06-15 12시)
r = client.post("/calculate", data={
    "name": "홍길동", "year": "1990", "month": "6", "day": "15",
    "hour_known": "yes", "hour": "12", "gender": "남", "cal_type": "solar",
}, follow_redirects=True)
(OUT / "result.html").write_text(to_static_html(r.data.decode("utf-8")), encoding="utf-8")
print("saved result.html (샘플: 홍길동 1990-06-15)")
