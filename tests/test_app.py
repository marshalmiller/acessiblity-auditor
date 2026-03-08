"""Tests for the Flask Accessibility Auditor application."""

import json
import os
import sys
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    Audit,
    _compute_score,
    _normalise_url,
    allowed_file,
    app,
    db,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a test client with an in-memory database."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield client
        db.drop_all()


@pytest.fixture
def sample_audit(client):
    """Insert a sample successful audit row and return it."""
    with app.app_context():
        results = {
            "violations": [
                {
                    "id": "color-contrast",
                    "impact": "serious",
                    "description": "Insufficient color contrast",
                    "help": "Fix color contrast",
                    "helpUrl": "https://dequeuniversity.com/rules/axe/4.x/color-contrast",
                    "tags": ["wcag2aa"],
                    "nodes": [{"html": "<p>text</p>", "target": ["p"], "failureSummary": "Fix contrast"}],
                }
            ],
            "passes": [
                {
                    "id": "html-has-lang",
                    "impact": None,
                    "description": "HTML has lang attribute",
                    "help": "lang attribute",
                    "helpUrl": "https://dequeuniversity.com/rules/axe/4.x/html-has-lang",
                    "tags": ["wcag2a"],
                    "nodes": [],
                }
            ],
            "incomplete": [],
            "inapplicable": [],
        }
        audit = Audit(
            target="https://example.com",
            audit_type="url",
            violations_count=1,
            passes_count=1,
            incomplete_count=0,
            inapplicable_count=0,
            score=50.0,
            results_json=json.dumps(results),
            status="success",
        )
        db.session.add(audit)
        db.session.commit()
        audit_id = audit.id
    return audit_id


# ---------------------------------------------------------------------------
# Helper / Utility Tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_normalise_url_adds_https(self):
        assert _normalise_url("example.com") == "https://example.com"

    def test_normalise_url_keeps_https(self):
        assert _normalise_url("https://example.com") == "https://example.com"

    def test_normalise_url_keeps_http(self):
        assert _normalise_url("http://example.com") == "http://example.com"

    def test_normalise_url_strips_whitespace(self):
        assert _normalise_url("  example.com  ") == "https://example.com"

    def test_allowed_file_pdf(self):
        assert allowed_file("report.pdf") is True

    def test_allowed_file_html(self):
        assert allowed_file("page.html") is True

    def test_allowed_file_htm(self):
        assert allowed_file("page.htm") is True

    def test_allowed_file_txt_rejected(self):
        assert allowed_file("notes.txt") is False

    def test_allowed_file_no_extension(self):
        assert allowed_file("noextension") is False

    def test_compute_score_no_violations(self):
        score = _compute_score([], [{"id": "test"}] * 5, [])
        assert score == 100.0

    def test_compute_score_all_violations(self):
        violations = [{"id": f"v{i}", "impact": "serious"} for i in range(5)]
        score = _compute_score(violations, [], [])
        assert score == 0.0

    def test_compute_score_mixed(self):
        violations = [{"id": "v1", "impact": "serious"}]
        passes = [{"id": "p1"}] * 3
        score = _compute_score(violations, passes, [])
        assert 0 < score < 100

    def test_compute_score_empty(self):
        score = _compute_score([], [], [])
        assert score == 100.0


# ---------------------------------------------------------------------------
# Route Tests
# ---------------------------------------------------------------------------


class TestIndexRoute:
    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_form(self, client):
        data = client.get("/").data.decode()
        assert "Check a Website URL" in data
        assert "Check a File" in data

    def test_index_shows_audit_history(self, client, sample_audit):
        response = client.get("/")
        assert response.status_code == 200
        assert b"example.com" in response.data


class TestAuditUrlRoute:
    def test_empty_url_redirects_with_flash(self, client):
        response = client.post("/audit/url", data={"url": ""})
        assert response.status_code == 302
        follow = client.post("/audit/url", data={"url": ""}, follow_redirects=True)
        assert b"Please enter a URL" in follow.data

    @patch("app.check_url_accessibility")
    def test_valid_url_creates_audit(self, mock_check, client):
        mock_check.return_value = {
            "violations": [],
            "passes": [{"id": "html-has-lang", "impact": None, "tags": ["wcag2a"], "description": "ok", "helpUrl": "", "nodes": []}],
            "incomplete": [],
            "inapplicable": [],
        }
        response = client.post("/audit/url", data={"url": "https://example.com"})
        assert response.status_code == 302

        with app.app_context():
            audit = Audit.query.first()
            assert audit is not None
            assert audit.target == "https://example.com"
            assert audit.status == "success"

    @patch("app.check_url_accessibility")
    def test_url_check_error_creates_error_audit(self, mock_check, client):
        mock_check.side_effect = RuntimeError("Page timed out")
        response = client.post(
            "/audit/url",
            data={"url": "https://broken.example"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Error checking" in response.data

        with app.app_context():
            audit = Audit.query.first()
            assert audit.status == "error"

    @patch("app.check_url_accessibility")
    def test_url_without_scheme_is_normalised(self, mock_check, client):
        mock_check.return_value = {"violations": [], "passes": [], "incomplete": [], "inapplicable": []}
        client.post("/audit/url", data={"url": "example.com"})
        with app.app_context():
            audit = Audit.query.first()
            assert audit.target.startswith("https://")


class TestAuditFileRoute:
    def test_no_file_redirects_with_flash(self, client):
        response = client.post("/audit/file", follow_redirects=True)
        assert b"No file part" in response.data

    def test_unsupported_extension_rejected(self, client):
        data = {"file": (BytesIO(b"hello"), "notes.txt")}
        response = client.post(
            "/audit/file",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Unsupported file type" in response.data

    @patch("app.check_html_accessibility")
    def test_html_file_creates_audit(self, mock_check, client):
        mock_check.return_value = {
            "violations": [],
            "passes": [],
            "incomplete": [],
            "inapplicable": [],
        }
        html_content = b"<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>"
        data = {"file": (BytesIO(html_content), "test.html")}
        response = client.post(
            "/audit/file",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 302
        with app.app_context():
            audit = Audit.query.first()
            assert audit is not None
            assert audit.audit_type == "html"

    @patch("app.check_pdf_accessibility")
    def test_pdf_file_creates_audit(self, mock_check, client):
        mock_check.return_value = {
            "violations": [
                {"id": "pdf-title", "impact": "serious", "description": "No title",
                 "help": "...", "helpUrl": "...", "tags": [], "nodes": []}
            ],
            "passes": [],
            "incomplete": [],
            "inapplicable": [],
        }
        # Minimal valid-looking file (actual PDF parsing mocked)
        data = {"file": (BytesIO(b"%PDF-1.4 fake content"), "report.pdf")}
        response = client.post(
            "/audit/file",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 302
        with app.app_context():
            audit = Audit.query.first()
            assert audit is not None
            assert audit.audit_type == "pdf"


class TestAuditDetailRoute:
    def test_detail_returns_200(self, client, sample_audit):
        response = client.get(f"/audit/{sample_audit}")
        assert response.status_code == 200

    def test_detail_shows_violations(self, client, sample_audit):
        response = client.get(f"/audit/{sample_audit}")
        assert b"color-contrast" in response.data
        assert b"Violations" in response.data

    def test_detail_shows_passes(self, client, sample_audit):
        response = client.get(f"/audit/{sample_audit}")
        assert b"html-has-lang" in response.data

    def test_detail_404_for_missing(self, client):
        response = client.get("/audit/99999")
        assert response.status_code == 404


class TestDeleteAuditRoute:
    def test_delete_removes_audit(self, client, sample_audit):
        with app.app_context():
            assert db.session.get(Audit, sample_audit) is not None

        response = client.post(f"/audit/{sample_audit}/delete")
        assert response.status_code == 302

        with app.app_context():
            assert db.session.get(Audit, sample_audit) is None

    def test_delete_404_for_missing(self, client):
        response = client.post("/audit/99999/delete")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Database Model Tests
# ---------------------------------------------------------------------------


class TestAuditModel:
    def test_results_returns_dict(self, client):
        with app.app_context():
            results_data = {"violations": [], "passes": [], "incomplete": [], "inapplicable": []}
            audit = Audit(
                target="https://test.com",
                audit_type="url",
                status="success",
                results_json=json.dumps(results_data),
            )
            db.session.add(audit)
            db.session.commit()
            fetched = db.session.get(Audit, audit.id)
            assert fetched.results() == results_data

    def test_results_returns_empty_dict_when_none(self, client):
        with app.app_context():
            audit = Audit(target="x", audit_type="url", status="error", error_message="oops")
            db.session.add(audit)
            db.session.commit()
            fetched = db.session.get(Audit, audit.id)
            assert fetched.results() == {}

    def test_repr(self, client):
        with app.app_context():
            audit = Audit(target="https://example.com", audit_type="url")
            db.session.add(audit)
            db.session.commit()
            assert "Audit" in repr(audit)
            assert "example.com" in repr(audit)


# ---------------------------------------------------------------------------
# PDF Accessibility Check Tests (mocked fitz)
# ---------------------------------------------------------------------------


class TestPDFAccessibilityLogic:
    @patch("app.fitz.open")
    def test_pdf_with_title_passes(self, mock_fitz_open):
        mock_doc = MagicMock()
        mock_doc.metadata = {"title": "My Report", "language": "en"}
        mock_doc.__len__ = lambda self: 1
        page_mock = MagicMock()
        page_mock.get_text.return_value = "Some text content here."
        page_mock.get_links.return_value = []
        mock_doc.__iter__ = lambda self: iter([page_mock])
        mock_doc.get_toc.return_value = [("Chapter 1", 1)]
        mock_doc.get_xml_metadata.return_value = ""
        mock_fitz_open.return_value.__enter__ = lambda s: s
        mock_fitz_open.return_value = mock_doc

        from app import check_pdf_accessibility
        results = check_pdf_accessibility("/tmp/fake.pdf")

        pass_ids = [p["id"] for p in results["passes"]]
        assert "pdf-title" in pass_ids

    @patch("app.fitz.open")
    def test_pdf_without_title_violation(self, mock_fitz_open):
        mock_doc = MagicMock()
        mock_doc.metadata = {"title": "", "language": ""}
        mock_doc.__len__ = lambda self: 1
        page_mock = MagicMock()
        page_mock.get_text.return_value = "Some text."
        page_mock.get_links.return_value = []
        mock_doc.__iter__ = lambda self: iter([page_mock])
        mock_doc.get_toc.return_value = []
        mock_doc.get_xml_metadata.return_value = ""
        mock_fitz_open.return_value = mock_doc

        from app import check_pdf_accessibility
        results = check_pdf_accessibility("/tmp/fake.pdf")

        violation_ids = [v["id"] for v in results["violations"]]
        assert "pdf-title" in violation_ids
