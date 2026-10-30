from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("COPILOT_DB_PATH", "data/copilot.db"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'Uncategorized',
            seller TEXT NOT NULL DEFAULT '',
            price REAL NOT NULL DEFAULT 0,
            image_path TEXT NOT NULL DEFAULT '',
            image_color TEXT NOT NULL DEFAULT 'unknown',
            risk_score INTEGER NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'Low',
            flags TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending review',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS moderation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            reviewer TEXT NOT NULL DEFAULT 'reviewer',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
        CREATE INDEX IF NOT EXISTS idx_products_risk ON products(risk_level);
        """)


def add_product(product: dict[str, Any]) -> int:
    fields = ("title", "description", "category", "seller", "price", "image_path",
              "image_color", "risk_score", "risk_level", "flags", "status")
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO products ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            tuple(product.get(field, "") for field in fields),
        )
        return int(cur.lastrowid)


def list_products() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(row) for row in rows]


def get_product(product_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return dict(row) if row else None


def update_moderation(product_id: int, status: str, note: str, reviewer: str = "reviewer") -> None:
    allowed = {"Approved", "Rejected", "Needs investigation", "Pending review"}
    if status not in allowed:
        raise ValueError("Unsupported moderation status")
    with connect() as conn:
        conn.execute("UPDATE products SET status = ? WHERE id = ?", (status, product_id))
        conn.execute(
            "INSERT INTO moderation_events(product_id, action, note, reviewer) VALUES (?, ?, ?, ?)",
            (product_id, status, note[:2000], reviewer[:120]),
        )


def list_events(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("""
            SELECT e.*, p.title FROM moderation_events e
            LEFT JOIN products p ON p.id = e.product_id
            ORDER BY e.created_at DESC, e.id DESC LIMIT ?
        """, (max(1, min(limit, 1000)),)).fetchall()
    return [dict(row) for row in rows]
