"""
SQLite database layer using aiosqlite.
Persistent file-based storage at /app/backend/storage/data.db.
"""
import os
import aiosqlite
from pathlib import Path

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
(STORAGE_DIR / "pdfs").mkdir(exist_ok=True)
(STORAGE_DIR / "labels").mkdir(exist_ok=True)

DB_PATH = STORAGE_DIR / "data.db"


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db():
    """Create tables if they don't exist and seed default operator."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_number TEXT NOT NULL,
            filename TEXT,
            delivery_pdf_path TEXT NOT NULL,
            label_pdf_path TEXT,
            label_cropped_path TEXT,
            total_qty INTEGER DEFAULT 0,
            picked_qty INTEGER DEFAULT 0,
            total_lines INTEGER DEFAULT 0,
            done_lines INTEGER DEFAULT 0,
            status TEXT DEFAULT 'in_progress',
            operator_code TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS order_lines (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            line_index INTEGER NOT NULL,
            product_name TEXT,
            reference TEXT,
            etagere TEXT,
            colonne TEXT,
            tiroir TEXT,
            bac TEXT,
            quantity INTEGER NOT NULL,
            picked INTEGER DEFAULT 0,
            page INTEGER DEFAULT 1,
            x REAL NOT NULL,
            y REAL NOT NULL,
            width REAL NOT NULL,
            height REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_lines_order ON order_lines(order_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number)")

        # Seed default operators
        async with db.execute("SELECT COUNT(*) FROM operators") as cur:
            row = await cur.fetchone()
            if row[0] == 0:
                await db.executemany(
                    "INSERT INTO operators (code, name) VALUES (?, ?)",
                    [
                        ("1234", "Préparateur 1"),
                        ("5678", "Préparateur 2"),
                        ("0000", "Admin"),
                    ],
                )

        await db.commit()
