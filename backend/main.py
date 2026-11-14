# SPDX-License-Identifier: MIT
# Copyright (c) 2026 임제민 (gunobo)
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://usagi:usagi@localhost:5432/usagi")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "https://usagi.imjemin.co.kr,http://localhost:8081").split(",")
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


Base.metadata.create_all(engine)


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


@app.delete("/api/guestbook/{entry_id}", status_code=204)
def delete_entry(entry_id: int, x_admin_token: str = Header(""), s: Session = Depends(db)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "forbidden")
    e = s.get(Guestbook, entry_id)
    if e:
        s.delete(e)
        s.commit()


# ASCII 캐롤 플레이어 (웹/앱 WebView 공용)
app.mount("/player", StaticFiles(directory=Path(__file__).parent / "player", html=True), name="player")
