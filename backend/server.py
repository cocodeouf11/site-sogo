"""
FastAPI backend for warehouse Order Picking application.
- SQLite persistence (aiosqlite) - files in /app/backend/storage/
- PDF parsing with PyMuPDF (line detection with bbox)
- Chronopost label auto-cropping
- Operator-code based simple auth
"""
from __future__ import annotations

import os
import uuid
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

from database import init_db, get_db, STORAGE_DIR
from pdf_parser import parse_delivery_note
from chronopost_cropper import crop_chronopost_labels

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB per PDF

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("picking")

app = FastAPI(title="Warehouse Picking API")
api = APIRouter(prefix="/api")


# ---------- Startup ----------
@app.on_event("startup")
async def on_startup():
    await init_db()
    logger.info("Database initialized")


# ---------- Auth (very simple) ----------
class LoginIn(BaseModel):
    code: str


@api.post("/auth/login")
async def login(payload: LoginIn):
    if not payload.code or not payload.code.isdigit():
        raise HTTPException(400, "Code invalide")
    db = await get_db()
    try:
        async with db.execute("SELECT id, code, name FROM operators WHERE code = ?", (payload.code,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(401, "Code opérateur inconnu")
        return {"operator": {"id": row["id"], "code": row["code"], "name": row["name"]}, "token": row["code"]}
    finally:
        await db.close()


async def current_operator(x_operator_code: Optional[str] = Header(None)) -> dict:
    if not x_operator_code:
        raise HTTPException(401, "Authentification requise")
    db = await get_db()
    try:
        async with db.execute("SELECT id, code, name FROM operators WHERE code = ?", (x_operator_code,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(401, "Session invalide")
        return {"id": row["id"], "code": row["code"], "name": row["name"]}
    finally:
        await db.close()


# ---------- Orders ----------
@api.post("/orders")
async def create_order(
    delivery: UploadFile = File(...),
    label: Optional[UploadFile] = File(None),
    order_number: Optional[str] = Form(None),
    operator: dict = Depends(current_operator),
):
    """Upload delivery-note (PDF) + optional Chronopost label (PDF). Parses lines, stores everything."""
    if delivery.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "Le bon de livraison doit être un PDF")
    if not delivery.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Le bon de livraison doit avoir l'extension .pdf")

    # Save delivery PDF
    order_id = str(uuid.uuid4())
    delivery_path = STORAGE_DIR / "pdfs" / f"{order_id}.pdf"
    size = 0
    with delivery_path.open("wb") as f:
        while chunk := await delivery.read(1024 * 64):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                f.close()
                delivery_path.unlink(missing_ok=True)
                raise HTTPException(413, "Fichier trop volumineux (max 25MB)")
            f.write(chunk)

    # Parse delivery PDF
    try:
        parsed = parse_delivery_note(str(delivery_path))
    except Exception as e:
        delivery_path.unlink(missing_ok=True)
        logger.exception("PDF parse failed")
        raise HTTPException(400, f"Erreur d'analyse du PDF: {e}")

    detected_number = order_number or parsed.get("order_number") or f"#{order_id[:6].upper()}"

    # Handle label upload + cropping
    label_path = None
    label_cropped = None
    if label is not None and label.filename:
        if not label.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "L'étiquette doit être un PDF")
        label_path = STORAGE_DIR / "labels" / f"{order_id}.pdf"
        size = 0
        with label_path.open("wb") as f:
            while chunk := await label.read(1024 * 64):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    f.close()
                    label_path.unlink(missing_ok=True)
                    raise HTTPException(413, "Étiquette trop volumineuse (max 25MB)")
                f.write(chunk)
        # Crop
        label_cropped = STORAGE_DIR / "labels" / f"{order_id}_cropped.pdf"
        try:
            crop_chronopost_labels(str(label_path), str(label_cropped))
        except Exception:
            logger.exception("Chronopost crop failed")
            label_cropped = None

    total_qty = sum(item["quantity"] for item in parsed["lines"])
    total_lines = len(parsed["lines"])

    now_iso = datetime.now(timezone.utc).isoformat()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO orders (id, order_number, filename, delivery_pdf_path, label_pdf_path, label_cropped_path,
                                    total_qty, picked_qty, total_lines, done_lines, status, operator_code, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0, 'in_progress', ?, ?, ?)""",
            (
                order_id,
                detected_number,
                delivery.filename,
                str(delivery_path),
                str(label_path) if label_path else None,
                str(label_cropped) if label_cropped else None,
                total_qty,
                total_lines,
                operator["code"],
                now_iso,
                now_iso,
            ),
        )

        for line in parsed["lines"]:
            await db.execute(
                """INSERT INTO order_lines (id, order_id, line_index, product_name, reference,
                                              etagere, colonne, tiroir, bac, quantity, picked, page, x, y, width, height)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    order_id,
                    line["line_index"],
                    line["product_name"],
                    line["reference"],
                    line["etagere"],
                    line["colonne"],
                    line["tiroir"],
                    line["bac"],
                    line["quantity"],
                    line["page"],
                    line["bbox"][0],
                    line["bbox"][1],
                    line["bbox"][2],
                    line["bbox"][3],
                ),
            )
        await db.commit()
    finally:
        await db.close()

    return {
        "id": order_id,
        "order_number": detected_number,
        "total_lines": total_lines,
        "total_qty": total_qty,
        "has_label": label_cropped is not None,
        "pages": parsed["pages"],
    }


@api.get("/orders")
async def list_orders(q: Optional[str] = None, operator: dict = Depends(current_operator)):
    db = await get_db()
    try:
        if q:
            sql = """SELECT * FROM orders WHERE order_number LIKE ? OR filename LIKE ? ORDER BY created_at DESC"""
            args = (f"%{q}%", f"%{q}%")
        else:
            sql = "SELECT * FROM orders ORDER BY created_at DESC"
            args = ()
        async with db.execute(sql, args) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@api.get("/orders/{order_id}")
async def get_order(order_id: str, operator: dict = Depends(current_operator)):
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cur:
            order = await cur.fetchone()
        if not order:
            raise HTTPException(404, "Commande introuvable")
        async with db.execute(
            "SELECT * FROM order_lines WHERE order_id = ? ORDER BY line_index ASC", (order_id,)
        ) as cur:
            lines = await cur.fetchall()
        return {
            "order": dict(order),
            "lines": [dict(row) for row in lines],
        }
    finally:
        await db.close()


@api.delete("/orders/{order_id}")
async def delete_order(order_id: str, operator: dict = Depends(current_operator)):
    db = await get_db()
    try:
        async with db.execute("SELECT delivery_pdf_path, label_pdf_path, label_cropped_path FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Commande introuvable")
        # Delete files
        for p in (row["delivery_pdf_path"], row["label_pdf_path"], row["label_cropped_path"]):
            if p and Path(p).exists():
                try:
                    Path(p).unlink()
                except Exception:
                    pass
        await db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


class IncrementIn(BaseModel):
    delta: int = 1


@api.post("/orders/{order_id}/lines/{line_id}/increment")
async def increment_line(order_id: str, line_id: str, payload: IncrementIn, operator: dict = Depends(current_operator)):
    if payload.delta not in (1, -1):
        raise HTTPException(400, "delta doit être 1 ou -1")
    db = await get_db()
    try:
        async with db.execute(
            "SELECT quantity, picked FROM order_lines WHERE id = ? AND order_id = ?", (line_id, order_id)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Ligne introuvable")
        new_val = row["picked"] + payload.delta
        if new_val < 0:
            new_val = 0
        if new_val > row["quantity"]:
            new_val = row["quantity"]

        await db.execute(
            "UPDATE order_lines SET picked = ? WHERE id = ? AND order_id = ?",
            (new_val, line_id, order_id),
        )
        # Recompute totals
        async with db.execute(
            """SELECT COALESCE(SUM(picked), 0) AS picked_qty,
                      COALESCE(SUM(quantity), 0) AS total_qty,
                      COALESCE(SUM(CASE WHEN picked >= quantity THEN 1 ELSE 0 END), 0) AS done_lines,
                      COUNT(*) AS total_lines
               FROM order_lines WHERE order_id = ?""",
            (order_id,),
        ) as cur:
            agg = await cur.fetchone()

        status = "done" if agg["total_lines"] > 0 and agg["done_lines"] == agg["total_lines"] else "in_progress"
        now_iso = datetime.now(timezone.utc).isoformat()

        await db.execute(
            """UPDATE orders SET picked_qty = ?, done_lines = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (agg["picked_qty"], agg["done_lines"], status, now_iso, order_id),
        )
        await db.commit()

        return {
            "line_id": line_id,
            "picked": new_val,
            "picked_qty": agg["picked_qty"],
            "total_qty": agg["total_qty"],
            "done_lines": agg["done_lines"],
            "total_lines": agg["total_lines"],
            "status": status,
        }
    finally:
        await db.close()


@api.post("/orders/{order_id}/lines/{line_id}/reset")
async def reset_line(order_id: str, line_id: str, operator: dict = Depends(current_operator)):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE order_lines SET picked = 0 WHERE id = ? AND order_id = ?",
            (line_id, order_id),
        )
        # Recompute totals
        async with db.execute(
            """SELECT COALESCE(SUM(picked), 0) AS picked_qty,
                      COALESCE(SUM(CASE WHEN picked >= quantity THEN 1 ELSE 0 END), 0) AS done_lines,
                      COUNT(*) AS total_lines
               FROM order_lines WHERE order_id = ?""",
            (order_id,),
        ) as cur:
            agg = await cur.fetchone()
        status = "done" if agg["total_lines"] > 0 and agg["done_lines"] == agg["total_lines"] else "in_progress"
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE orders SET picked_qty = ?, done_lines = ?, status = ?, updated_at = ? WHERE id = ?",
            (agg["picked_qty"], agg["done_lines"], status, now_iso, order_id),
        )
        await db.commit()
        return {"ok": True, "picked": 0}
    finally:
        await db.close()


@api.get("/orders/{order_id}/pdf")
async def get_order_pdf(order_id: str, code: Optional[str] = None, x_operator_code: Optional[str] = Header(None)):
    """PDF fetch: accepts token via query `?code=` OR header `X-Operator-Code`
    (allows PDF.js and <object> tags which can't easily set custom headers)."""
    token = code or x_operator_code
    if not token:
        raise HTTPException(401, "Authentification requise")
    db = await get_db()
    try:
        async with db.execute("SELECT id FROM operators WHERE code = ?", (token,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(401, "Session invalide")
        async with db.execute("SELECT delivery_pdf_path FROM orders WHERE id = ?", (order_id,)) as cur:
            row = await cur.fetchone()
        if not row or not row["delivery_pdf_path"] or not Path(row["delivery_pdf_path"]).exists():
            raise HTTPException(404, "PDF introuvable")
        return FileResponse(row["delivery_pdf_path"], media_type="application/pdf")
    finally:
        await db.close()


@api.get("/orders/{order_id}/label")
async def get_order_label(order_id: str, cropped: bool = True, code: Optional[str] = None, x_operator_code: Optional[str] = Header(None)):
    token = code or x_operator_code
    if not token:
        raise HTTPException(401, "Authentification requise")
    db_c = await get_db()
    try:
        async with db_c.execute("SELECT id FROM operators WHERE code = ?", (token,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(401, "Session invalide")
    finally:
        await db_c.close()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT label_pdf_path, label_cropped_path FROM orders WHERE id = ?", (order_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Commande introuvable")
        path = row["label_cropped_path"] if cropped else row["label_pdf_path"]
        if not path or not Path(path).exists():
            raise HTTPException(404, "Étiquette non disponible")
        return FileResponse(path, media_type="application/pdf")
    finally:
        await db.close()


@api.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
