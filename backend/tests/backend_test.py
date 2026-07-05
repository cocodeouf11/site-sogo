"""
Backend regression tests for Warehouse Picking API.
Covers auth, orders CRUD, PDF upload/parse, line increment/reset, PDF/label serving.
"""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://order-prep-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DELIVERY_PDF = Path("/tmp/pdfs/delivery.pdf")
LABEL_PDF = Path("/tmp/pdfs/label.pdf")


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def op_headers():
    return {"X-Operator-Code": "1234"}


@pytest.fixture(scope="session")
def created_order(op_headers):
    """Create a single order used by many tests."""
    assert DELIVERY_PDF.exists() and LABEL_PDF.exists(), "sample PDFs missing"
    with DELIVERY_PDF.open("rb") as df, LABEL_PDF.open("rb") as lf:
        files = {
            "delivery": ("bon-de-livraison-56747.pdf", df, "application/pdf"),
            "label": ("chronopost.pdf", lf, "application/pdf"),
        }
        r = requests.post(f"{API}/orders", files=files, headers=op_headers, timeout=120)
    assert r.status_code == 200, f"Order creation failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    yield data
    # teardown
    try:
        requests.delete(f"{API}/orders/{data['id']}", headers=op_headers, timeout=30)
    except Exception:
        pass


# ---------- Auth ----------
class TestAuth:
    def test_login_valid_1234(self):
        r = requests.post(f"{API}/auth/login", json={"code": "1234"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["operator"]["code"] == "1234"
        assert d["token"] == "1234"
        assert "name" in d["operator"]

    def test_login_valid_5678(self):
        r = requests.post(f"{API}/auth/login", json={"code": "5678"}, timeout=15)
        assert r.status_code == 200

    def test_login_valid_0000(self):
        r = requests.post(f"{API}/auth/login", json={"code": "0000"}, timeout=15)
        assert r.status_code == 200

    def test_login_invalid_9999(self):
        r = requests.post(f"{API}/auth/login", json={"code": "9999"}, timeout=15)
        assert r.status_code == 401

    def test_login_non_digit(self):
        r = requests.post(f"{API}/auth/login", json={"code": "abcd"}, timeout=15)
        assert r.status_code == 400

    def test_orders_requires_operator_header(self):
        r = requests.post(f"{API}/orders", files={"delivery": ("a.pdf", b"x", "application/pdf")}, timeout=15)
        assert r.status_code == 401


# ---------- Orders CRUD ----------
class TestOrders:
    def test_list_orders_public(self):
        # list endpoint is not protected in current server
        r = requests.get(f"{API}/orders", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_order_parses_lines(self, created_order):
        assert created_order["order_number"] == "56747"
        assert created_order["has_label"] is True
        # Expected ~180 lines
        assert created_order["total_lines"] >= 150, f"Only {created_order['total_lines']} lines detected"
        assert created_order["total_lines"] <= 220

    def test_get_order_with_lines(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["order"]["id"] == oid
        assert d["order"]["order_number"] == "56747"
        assert len(d["lines"]) == created_order["total_lines"]

        first = d["lines"][0]
        # bbox normalized 0..1
        for k in ("x", "y", "width", "height"):
            assert 0 <= first[k] <= 1, f"{k}={first[k]} not normalized"
        # required product fields present (may be empty strings but keys exist)
        for k in ("product_name", "reference", "etagere", "colonne", "tiroir", "bac", "quantity"):
            assert k in first

    def test_list_orders_contains_created(self, created_order):
        r = requests.get(f"{API}/orders", timeout=15)
        assert r.status_code == 200
        ids = [o["id"] for o in r.json()]
        assert created_order["id"] in ids

    def test_search_orders(self, created_order):
        r = requests.get(f"{API}/orders", params={"q": "56747"}, timeout=15)
        assert r.status_code == 200
        assert any(o["id"] == created_order["id"] for o in r.json())

    def test_get_pdf_returns_pdf(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}/pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_get_label_cropped(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}/label", params={"cropped": "true"}, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_get_label_raw(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}/label", params={"cropped": "false"}, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# ---------- Line increment/reset ----------
class TestLineOps:
    def test_increment_and_reset(self, created_order, op_headers):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", timeout=30)
        line = r.json()["lines"][0]
        qty = line["quantity"]
        assert qty >= 1

        # increment up to qty
        for _ in range(qty):
            ri = requests.post(
                f"{API}/orders/{oid}/lines/{line['id']}/increment",
                json={"delta": 1},
                timeout=15,
            )
            assert ri.status_code == 200

        final = ri.json()
        assert final["picked"] == qty
        assert final["picked_qty"] >= qty
        assert final["done_lines"] >= 1

        # extra increment should cap at qty
        rex = requests.post(
            f"{API}/orders/{oid}/lines/{line['id']}/increment",
            json={"delta": 1},
            timeout=15,
        )
        assert rex.status_code == 200
        assert rex.json()["picked"] == qty  # capped

        # Verify persistence via GET
        r2 = requests.get(f"{API}/orders/{oid}", timeout=30)
        persisted = [l for l in r2.json()["lines"] if l["id"] == line["id"]][0]
        assert persisted["picked"] == qty

        # decrement below zero should clamp at 0 via reset
        rr = requests.post(f"{API}/orders/{oid}/lines/{line['id']}/reset", timeout=15)
        assert rr.status_code == 200
        r3 = requests.get(f"{API}/orders/{oid}", timeout=30)
        reset_line = [l for l in r3.json()["lines"] if l["id"] == line["id"]][0]
        assert reset_line["picked"] == 0

    def test_increment_invalid_delta(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", timeout=30)
        line = r.json()["lines"][0]
        ri = requests.post(
            f"{API}/orders/{oid}/lines/{line['id']}/increment",
            json={"delta": 5},
            timeout=15,
        )
        assert ri.status_code == 400

    def test_increment_unknown_line(self, created_order):
        oid = created_order["id"]
        ri = requests.post(
            f"{API}/orders/{oid}/lines/does-not-exist/increment",
            json={"delta": 1},
            timeout=15,
        )
        assert ri.status_code == 404


# ---------- Validation ----------
class TestValidation:
    def test_upload_non_pdf_rejected(self, op_headers):
        files = {"delivery": ("bad.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/orders", files=files, headers=op_headers, timeout=30)
        assert r.status_code == 400

    def test_get_unknown_order(self):
        r = requests.get(f"{API}/orders/does-not-exist", timeout=15)
        assert r.status_code == 404

    def test_get_unknown_pdf(self):
        r = requests.get(f"{API}/orders/does-not-exist/pdf", timeout=15)
        assert r.status_code == 404


# ---------- Delete (runs last) ----------
class TestDelete:
    def test_delete_order_removes_files(self, op_headers):
        # Create dedicated order to delete
        with DELIVERY_PDF.open("rb") as df, LABEL_PDF.open("rb") as lf:
            files = {
                "delivery": ("del.pdf", df, "application/pdf"),
                "label": ("del-label.pdf", lf, "application/pdf"),
            }
            r = requests.post(f"{API}/orders", files=files, headers=op_headers, timeout=120)
        assert r.status_code == 200
        oid = r.json()["id"]

        rd = requests.delete(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
        assert rd.status_code == 200
        assert rd.json().get("ok") is True

        rg = requests.get(f"{API}/orders/{oid}", timeout=15)
        assert rg.status_code == 404

        rp = requests.get(f"{API}/orders/{oid}/pdf", timeout=15)
        assert rp.status_code == 404
