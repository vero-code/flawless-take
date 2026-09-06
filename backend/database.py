"""
Repository layer for continuity history.

Current implementation: SQLite via aiosqlite.
To migrate to Firestore: implement FirestoreRepository with the same
interface (save_check, save_comparison, list_records, get_record)
and swap the dependency in main.py.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path(__file__).parent / "flawless.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,          -- 'check' | 'comparison'
    created_at  REAL    NOT NULL,          -- unix timestamp
    scene       TEXT    NOT NULL,
    character   TEXT    NOT NULL,
    take        TEXT,                      -- single check
    take_ref    TEXT,                      -- comparison
    take_current TEXT,                     -- comparison
    risk_level  TEXT,
    match_score TEXT,                      -- comparison only
    script_grounded INTEGER NOT NULL DEFAULT 0,
    report      TEXT    NOT NULL,          -- full Gemini text
    preview_ref TEXT,                      -- filename in uploads/
    preview_cur TEXT,                      -- comparison second image
    extra       TEXT    DEFAULT '{}'       -- JSON for future fields
);
"""


async def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------
async def save_check(
    *,
    scene: str,
    character: str,
    take: str,
    risk_level: str,
    script_grounded: bool,
    report: str,
    preview_ref: str | None = None,
) -> int:
    """Persist a single-take continuity check. Returns the new row id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO checks
               (kind, created_at, scene, character, take,
                risk_level, script_grounded, report, preview_ref)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                "check", time.time(), scene, character, take,
                risk_level, int(script_grounded), report, preview_ref,
            ),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def save_comparison(
    *,
    scene: str,
    character: str,
    take_ref: str,
    take_current: str,
    risk_level: str,
    match_score: str,
    script_grounded: bool,
    report: str,
    preview_ref: str | None = None,
    preview_cur: str | None = None,
) -> int:
    """Persist a takes-comparison result. Returns the new row id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO checks
               (kind, created_at, scene, character, take_ref, take_current,
                risk_level, match_score, script_grounded, report,
                preview_ref, preview_cur)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "comparison", time.time(), scene, character,
                take_ref, take_current, risk_level, match_score,
                int(script_grounded), report, preview_ref, preview_cur,
            ),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def list_records(
    scene: str | None = None,
    character: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return history records newest-first, with optional filters."""
    where, params = [], []
    if scene:
        where.append("scene LIKE ?")
        params.append(f"%{scene}%")
    if character:
        where.append("character LIKE ?")
        params.append(f"%{character}%")
    sql = "SELECT * FROM checks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_record(record_id: int) -> dict[str, Any] | None:
    """Return a single record by id, or None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM checks WHERE id = ?", (record_id,)
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def delete_record(record_id: int) -> bool:
    """Delete a record by id. Returns True if deleted, False if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM checks WHERE id = ?", (record_id,))
        await db.commit()
        return cur.rowcount > 0


def normalize_key(val: str) -> str:
    """Normalize whitespace and various dashes (-, –, —) for resilient screenplay matching."""
    if not val:
        return ""
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\-]+", "-", val)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


async def get_scene_chronology(
    scene: str,
    character: str,
) -> list[dict[str, Any]]:
    """Return all records for a scene & character in chronological order (oldest first)."""
    norm_scene = normalize_key(scene)
    norm_char = normalize_key(character)
    if not norm_scene or not norm_char:
        return []

    sql = """
        SELECT * FROM checks
        WHERE LOWER(TRIM(character)) = LOWER(TRIM(?))
        ORDER BY created_at ASC
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, (character.strip(),)) as cur:
            rows = await cur.fetchall()

    matched = []
    for r in rows:
        row_dict = dict(r)
        if normalize_key(row_dict.get("scene", "")) == norm_scene:
            matched.append(row_dict)
    return matched




