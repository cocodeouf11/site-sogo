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
LABEL1_PDF = Path("/tmp/pdfs/label1.pdf")  # landscape sample (842x595)
LABEL2_PDF = Path("/tmp/pdfs/label2.pdf")  # target portrait (~320x416)
DELIVERY_56755_PDF = Path("/tmp/pdfs/delivery-56755.pdf")  # 3 pages / 33 lines
DELIVERY_56662_PDF = Path("/tmp/pdfs/delivery-56662.pdf")  # 33 lines


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
    def test_list_orders_requires_auth(self):
        # After security fix, list endpoint requires operator header
        r = requests.get(f"{API}/orders", timeout=15)
        assert r.status_code == 401

    def test_list_orders_authed(self, op_headers):
        r = requests.get(f"{API}/orders", headers=op_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_order_parses_lines(self, created_order):
        assert created_order["order_number"] == "56747"
        assert created_order["has_label"] is True
        # Expected exactly 180 lines
        assert created_order["total_lines"] == 180, f"expected 180 got {created_order['total_lines']}"

    def test_get_order_with_lines(self, created_order, op_headers):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
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

    def test_list_orders_contains_created(self, created_order, op_headers):
        r = requests.get(f"{API}/orders", headers=op_headers, timeout=15)
        assert r.status_code == 200
        ids = [o["id"] for o in r.json()]
        assert created_order["id"] in ids

    def test_search_orders(self, created_order, op_headers):
        r = requests.get(f"{API}/orders", params={"q": "56747"}, headers=op_headers, timeout=15)
        assert r.status_code == 200
        assert any(o["id"] == created_order["id"] for o in r.json())

    def test_get_pdf_returns_pdf(self, created_order):
        oid = created_order["id"]
        # PDF endpoint accepts ?code= for <object> / PDF.js
        r = requests.get(f"{API}/orders/{oid}/pdf", params={"code": "1234"}, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_get_label_cropped(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}/label", params={"cropped": "true", "code": "1234"}, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_get_label_raw(self, created_order):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}/label", params={"cropped": "false", "code": "1234"}, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# ---------- Line increment/reset ----------
class TestLineOps:
    def test_increment_and_reset(self, created_order, op_headers):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
        line = r.json()["lines"][0]
        qty = line["quantity"]
        assert qty >= 1

        # increment up to qty
        for _ in range(qty):
            ri = requests.post(
                f"{API}/orders/{oid}/lines/{line['id']}/increment",
                json={"delta": 1},
                headers=op_headers,
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
            headers=op_headers,
            timeout=15,
        )
        assert rex.status_code == 200
        assert rex.json()["picked"] == qty  # capped

        # Verify persistence via GET
        r2 = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
        persisted = [l for l in r2.json()["lines"] if l["id"] == line["id"]][0]
        assert persisted["picked"] == qty

        # reset the line
        rr = requests.post(f"{API}/orders/{oid}/lines/{line['id']}/reset", headers=op_headers, timeout=15)
        assert rr.status_code == 200
        r3 = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
        reset_line = [l for l in r3.json()["lines"] if l["id"] == line["id"]][0]
        assert reset_line["picked"] == 0

    def test_increment_invalid_delta(self, created_order, op_headers):
        oid = created_order["id"]
        r = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=30)
        line = r.json()["lines"][0]
        ri = requests.post(
            f"{API}/orders/{oid}/lines/{line['id']}/increment",
            json={"delta": 5},
            headers=op_headers,
            timeout=15,
        )
        assert ri.status_code == 400

    def test_increment_unknown_line(self, created_order, op_headers):
        oid = created_order["id"]
        ri = requests.post(
            f"{API}/orders/{oid}/lines/does-not-exist/increment",
            json={"delta": 1},
            headers=op_headers,
            timeout=15,
        )
        assert ri.status_code == 404


# ---------- Validation ----------
class TestValidation:
    def test_upload_non_pdf_rejected(self, op_headers):
        files = {"delivery": ("bad.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/orders", files=files, headers=op_headers, timeout=30)
        assert r.status_code == 400

    def test_get_unknown_order(self, op_headers):
        r = requests.get(f"{API}/orders/does-not-exist", headers=op_headers, timeout=15)
        assert r.status_code == 404

    def test_get_unknown_pdf(self):
        r = requests.get(f"{API}/orders/does-not-exist/pdf", params={"code": "1234"}, timeout=15)
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

        rg = requests.get(f"{API}/orders/{oid}", headers=op_headers, timeout=15)
        assert rg.status_code == 404

        rp = requests.get(f"{API}/orders/{oid}/pdf", params={"code": "1234"}, timeout=15)
        assert rp.status_code == 404


# ---------- Standalone Label Resizer (Chronopost) ----------
class TestLabelResize:
    """Regression tests for /api/labels/* endpoints — rotation must be 90° (portrait)."""

    def test_resize_label_landscape_to_portrait(self, op_headers):
        assert LABEL1_PDF.exists(), "sample label1.pdf missing"
        with LABEL1_PDF.open("rb") as lf:
            files = {"label": ("1.pdf", lf, "application/pdf")}
            r = requests.post(f"{API}/labels/resize", files=files, headers=op_headers, timeout=60)
        assert r.status_code == 200, f"resize failed: {r.status_code} {r.text[:400]}"
        data = r.json()
        assert "id" in data and "labels" in data and data["pages"] == 1
        lab = data["labels"][0]
        assert lab["rotated"] is True, f"expected rotated=True, got {lab}"
        assert 280 <= lab["width_pt"] <= 320, f"width_pt out of range: {lab['width_pt']}"
        assert 400 <= lab["height_pt"] <= 425, f"height_pt out of range: {lab['height_pt']}"

        # Download and verify orientation + text position via PyMuPDF
        rid = data["id"]
        dr = requests.get(f"{API}/labels/{rid}/download", params={"code": "1234"}, timeout=30)
        assert dr.status_code == 200
        assert dr.content[:4] == b"%PDF"

        out_path = Path("/tmp/pdfs/_resized_out.pdf")
        out_path.write_bytes(dr.content)
        import fitz
        doc = fitz.open(str(out_path))
        page = doc[0]
        rect = page.rect
        assert rect.width < rect.height, f"not portrait: w={rect.width} h={rect.height}"
        # Text 'Fenouillet' must appear in the UPPER HALF
        found_upper = False
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if "Fenouillet" in span.get("text", ""):
                        y = span["bbox"][1]
                        if y < rect.height / 2:
                            found_upper = True
        doc.close()
        assert found_upper, "'Fenouillet' text not found in upper half of resized PDF"

        # Cleanup
        requests.delete(f"{API}/labels/{rid}", headers=op_headers, timeout=15)

    def test_labels_list_and_delete(self, op_headers):
        assert LABEL1_PDF.exists()
        # create one
        with LABEL1_PDF.open("rb") as lf:
            files = {"label": ("1.pdf", lf, "application/pdf")}
            r = requests.post(f"{API}/labels/resize", files=files, headers=op_headers, timeout=60)
        assert r.status_code == 200
        rid = r.json()["id"]

        # list must contain it
        rl = requests.get(f"{API}/labels", headers=op_headers, timeout=15)
        assert rl.status_code == 200
        ids = [x["id"] for x in rl.json()]
        assert rid in ids

        # delete
        rd = requests.delete(f"{API}/labels/{rid}", headers=op_headers, timeout=15)
        assert rd.status_code == 200
        assert rd.json().get("ok") is True

        # gone from list
        rl2 = requests.get(f"{API}/labels", headers=op_headers, timeout=15)
        ids2 = [x["id"] for x in rl2.json()]
        assert rid not in ids2

        # download must 404
        rdown = requests.get(f"{API}/labels/{rid}/download", params={"code": "1234"}, timeout=15)
        assert rdown.status_code == 404

    def test_labels_requires_auth(self):
        with LABEL1_PDF.open("rb") as lf:
            files = {"label": ("1.pdf", lf, "application/pdf")}
            r = requests.post(f"{API}/labels/resize", files=files, timeout=30)
        assert r.status_code == 401


# ---------- Parser regression: different delivery notes ----------
class TestParserRegression:
    """Ensure parser returns expected number of lines for known samples."""

    def _create(self, pdf_path: Path, name: str, op_headers):
        assert pdf_path.exists(), f"{name} missing"
        with pdf_path.open("rb") as df:
            files = {"delivery": (name, df, "application/pdf")}
            r = requests.post(f"{API}/orders", files=files, headers=op_headers, timeout=120)
        return r

    def test_parse_56755_returns_33_lines(self, op_headers):
        r = self._create(DELIVERY_56755_PDF, "bon-de-livraison-56755.pdf", op_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        d = r.json()
        assert d["total_lines"] == 33, f"expected 33 lines got {d['total_lines']}"
        # cleanup
        requests.delete(f"{API}/orders/{d['id']}", headers=op_headers, timeout=30)

    def test_parse_56662_returns_33_lines(self, op_headers):
        r = self._create(DELIVERY_56662_PDF, "bon-de-livraison-56662.pdf", op_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        d = r.json()
        assert d["total_lines"] == 33, f"expected 33 lines got {d['total_lines']}"
        requests.delete(f"{API}/orders/{d['id']}", headers=op_headers, timeout=30)

    def test_parse_56747_returns_180_lines(self, op_headers):
        r = self._create(DELIVERY_PDF, "bon-de-livraison-56747.pdf", op_headers)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        d = r.json()
        assert d["total_lines"] == 180, f"expected 180 lines got {d['total_lines']}"
        requests.delete(f"{API}/orders/{d['id']}", headers=op_headers, timeout=30)
