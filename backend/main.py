# SPDX-License-Identifier: MIT
# Copyright (c) 2026 임제민 (gunobo)
import os
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, func, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://usagi:usagi@localhost:5432/usagi")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://usagi.imjemin.co.kr,http://localhost:8081").split(",")
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/data/media"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_RULES = {  # 종류: (허용 확장자, 최대 크기)
    "image": ({".png", ".jpg", ".jpeg", ".webp", ".gif"}, 10 * 1024 * 1024),
    "audio": ({".mp3", ".wav", ".ogg", ".m4a", ".aac"}, 40 * 1024 * 1024),
}
WRITE_INTERVAL = 10  # 같은 IP 연속 작성 제한(초)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Guestbook(Base):
    __tablename__ = "guestbook"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), default="")
    text: Mapped[str] = mapped_column(String(140))
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # image | audio
    filename: Mapped[str] = mapped_column(String(64), unique=True)
    original_name: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), default="")


Base.metadata.create_all(engine)

# 플레이어 화면 문구 (관리자 수정 가능)
DEFAULT_SETTINGS = {"handle": "@PENGU_CAROL", "name": "SANTA PENGU", "edition": "SCARF EDITION", "title": "Pengu Carol #1", "style": "ascii"}


def get_settings(s: Session) -> dict:
    out = dict(DEFAULT_SETTINGS)
    out.update({r.key: r.value for r in s.scalars(select(Setting)).all() if r.key in DEFAULT_SETTINGS})
    return out


def db():
    with SessionLocal() as s:
        yield s


class EntryIn(BaseModel):
    name: str = Field("", max_length=20)
    text: str = Field(min_length=1, max_length=140)


class EntryOut(BaseModel):
    id: int
    name: str
    text: str
    created_at: datetime


class AdminEntry(EntryOut):
    ip: str


class MediaOut(BaseModel):
    id: int
    kind: str
    url: str
    original_name: str
    active: bool
    sort: int


class MediaPatch(BaseModel):
    active: bool | None = None
    sort: int | None = None


def media_out(m: Media) -> MediaOut:
    return MediaOut(id=m.id, kind=m.kind, url=f"/media/{m.filename}", original_name=m.original_name, active=m.active, sort=m.sort)


class SettingsIn(BaseModel):
    handle: str | None = Field(None, max_length=40)
    name: str | None = Field(None, max_length=40)
    edition: str | None = Field(None, max_length=40)
    title: str | None = Field(None, max_length=40)
    style: str | None = Field(None, pattern="^(ascii|ansi|pixel)$")


class AdminPage(BaseModel):
    total: int
    items: list[AdminEntry]


app = FastAPI(title="usagi.imjemin.co.kr")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
_last_write: dict[str, float] = {}


def client_ip(req: Request) -> str:
    # Cloudflare Tunnel 뒤에서는 실제 IP가 헤더로 온다
    return req.headers.get("cf-connecting-ip") or req.headers.get("x-forwarded-for", "").split(",")[0] or req.client.host


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/guestbook", response_model=list[EntryOut])
def list_entries(limit: int = 50, s: Session = Depends(db)):
    q = select(Guestbook).order_by(Guestbook.created_at.desc()).limit(min(max(limit, 1), 200))
    return s.scalars(q).all()


@app.post("/api/guestbook", response_model=EntryOut, status_code=201)
def create_entry(body: EntryIn, req: Request, s: Session = Depends(db)):
    ip = client_ip(req)
    now = time.time()
    if now - _last_write.get(ip, 0) < WRITE_INTERVAL:
        raise HTTPException(429, "too many requests")
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "empty text")
    e = Guestbook(name=body.name.strip(), text=text, ip=ip)
    s.add(e)
    s.commit()
    _last_write[ip] = now
    return e


def require_admin(x_admin_token: str = Header("")):
    if not ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(403, "forbidden")


@app.get("/api/admin/guestbook", response_model=AdminPage, dependencies=[Depends(require_admin)])
def admin_list(offset: int = 0, limit: int = 100, q: str = "", s: Session = Depends(db)):
    """관리자 전용: 전체 방명록(IP 포함), 검색·페이지네이션"""
    base = select(Guestbook)
    if q:
        base = base.where(Guestbook.text.ilike(f"%{q}%") | Guestbook.name.ilike(f"%{q}%"))
    total = s.scalar(select(func.count()).select_from(base.subquery()))
    rows = s.scalars(base.order_by(Guestbook.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500))).all()
    return {"total": total, "items": rows}


@app.delete("/api/guestbook/{entry_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_entry(entry_id: int, s: Session = Depends(db)):
    e = s.get(Guestbook, entry_id)
    if e:
        s.delete(e)
        s.commit()


# ───────── 미디어 (관리자가 이미지 여러 개 + 음원 관리) ─────────
@app.get("/api/media")
def public_media(s: Session = Depends(db)):
    """플레이어용: 활성 이미지 목록(순서대로) + 활성 음원 1개"""
    rows = s.scalars(select(Media).where(Media.active).order_by(Media.sort, Media.id)).all()
    audio = next((m for m in rows if m.kind == "audio"), None)
    return {"images": [media_out(m) for m in rows if m.kind == "image"], "audio": media_out(audio) if audio else None,
            "settings": get_settings(s)}


@app.get("/api/admin/settings", dependencies=[Depends(require_admin)])
def admin_settings(s: Session = Depends(db)):
    return get_settings(s)


@app.put("/api/admin/settings", dependencies=[Depends(require_admin)])
def save_settings(body: SettingsIn, s: Session = Depends(db)):
    for k, v in body.model_dump(exclude_none=True).items():
        s.merge(Setting(key=k, value=v.strip()))
    s.commit()
    return get_settings(s)


@app.get("/api/admin/media", response_model=list[MediaOut], dependencies=[Depends(require_admin)])
def admin_media(s: Session = Depends(db)):
    return [media_out(m) for m in s.scalars(select(Media).order_by(Media.kind, Media.sort, Media.id)).all()]


@app.post("/api/admin/media", response_model=list[MediaOut], status_code=201, dependencies=[Depends(require_admin)])
async def upload_media(kind: str = Form(...), files: list[UploadFile] = File(...), s: Session = Depends(db)):
    if kind not in MEDIA_RULES:
        raise HTTPException(422, "kind must be image or audio")
    exts, max_size = MEDIA_RULES[kind]
    next_sort = (s.scalar(select(func.max(Media.sort)).where(Media.kind == kind)) or 0) + 1
    saved = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in exts:
            raise HTTPException(422, f"허용되지 않는 형식: {f.filename}")
        data = await f.read()
        if len(data) > max_size:
            raise HTTPException(413, f"파일이 너무 커요: {f.filename}")
        name = f"{uuid.uuid4().hex}{ext}"
        (MEDIA_DIR / name).write_bytes(data)
        m = Media(kind=kind, filename=name, original_name=(f.filename or "")[:200], sort=next_sort, active=True)
        next_sort += 1
        s.add(m)
        saved.append(m)
    s.flush()
    if kind == "audio" and saved:  # 음원은 하나만 활성: 방금 올린 것으로 교체
        s.execute(update(Media).where(Media.kind == "audio", Media.id != saved[-1].id).values(active=False))
        for m in saved[:-1]:
            m.active = False
    s.commit()
    return [media_out(m) for m in saved]


@app.patch("/api/admin/media/{media_id}", response_model=MediaOut, dependencies=[Depends(require_admin)])
def patch_media(media_id: int, body: MediaPatch, s: Session = Depends(db)):
    m = s.get(Media, media_id)
    if not m:
        raise HTTPException(404, "not found")
    if body.sort is not None:
        m.sort = body.sort
    if body.active is not None:
        m.active = body.active
        if m.kind == "audio" and body.active:
            s.execute(update(Media).where(Media.kind == "audio", Media.id != m.id).values(active=False))
    s.commit()
    return media_out(m)


@app.delete("/api/admin/media/{media_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_media(media_id: int, s: Session = Depends(db)):
    m = s.get(Media, media_id)
    if m:
        (MEDIA_DIR / m.filename).unlink(missing_ok=True)
        s.delete(m)
        s.commit()


app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# ASCII 캐롤 플레이어 (웹/앱 WebView 공용)
app.mount("/admin", StaticFiles(directory=Path(__file__).parent / "admin", html=True), name="admin")
app.mount("/player", StaticFiles(directory=Path(__file__).parent / "player", html=True), name="player")
