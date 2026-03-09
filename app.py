"""Flask Accessibility Auditor Application.

Checks websites and documents for accessibility issues using axe-core (for web pages)
and PyMuPDF (for PDF documents).
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone

import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///audits.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(tempfile.gettempdir(), "accessibility_uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

ALLOWED_EXTENSIONS = {"pdf", "html", "htm"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

# Path to the bundled axe-core script served locally
AXE_CORE_PATH = os.path.join(os.path.dirname(__file__), "static", "js", "axe.min.js")


# ---------------------------------------------------------------------------
# Database Models
# ---------------------------------------------------------------------------


class Audit(db.Model):
    """Stores one accessibility audit run."""

    __tablename__ = "audits"

    id = db.Column(db.Integer, primary_key=True)
    target = db.Column(db.String(2048), nullable=False)
    audit_type = db.Column(db.String(20), nullable=False)  # "url", "pdf", "html"
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    violations_count = db.Column(db.Integer, default=0)
    passes_count = db.Column(db.Integer, default=0)
    incomplete_count = db.Column(db.Integer, default=0)
    inapplicable_count = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)  # 0-100 accessibility score
    results_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending")  # "success", "error"

    def results(self):
        """Return parsed results dict or empty dict."""
        if self.results_json:
            return json.loads(self.results_json)
        return {}

    def __repr__(self):
        return f"<Audit id={self.id} target={self.target!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Accessibility Checking Logic
# ---------------------------------------------------------------------------


def _load_axe_script() -> str:
    """Return the axe-core JS source code."""
    with open(AXE_CORE_PATH, encoding="utf-8") as fh:
        return fh.read()


def check_url_accessibility(url: str) -> dict:
    """Run axe-core accessibility checks against a live URL using Playwright.

    Returns a dict with keys: violations, passes, incomplete, inapplicable.
    Raises RuntimeError on failure.
    """
    axe_script = _load_axe_script()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(url, wait_until="domcontentloaded")
            # Inject and run axe-core
            page.evaluate(axe_script)
            results = page.evaluate(
                """async () => {
                    const results = await axe.run(document, {
                        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'best-practice'] }
                    });
                    return {
                        violations: results.violations,
                        passes: results.passes,
                        incomplete: results.incomplete,
                        inapplicable: results.inapplicable
                    };
                }"""
            )
            return results
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Page timed out: {exc}") from exc
        finally:
            browser.close()


def check_html_accessibility(html_content: str, filename: str) -> dict:
    """Run axe-core against an uploaded HTML file using Playwright."""
    axe_script = _load_axe_script()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="domcontentloaded")
            page.evaluate(axe_script)
            results = page.evaluate(
                """async () => {
                    const results = await axe.run(document, {
                        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'best-practice'] }
                    });
                    return {
                        violations: results.violations,
                        passes: results.passes,
                        incomplete: results.incomplete,
                        inapplicable: results.inapplicable
                    };
                }"""
            )
            return results
        finally:
            browser.close()


def check_pdf_accessibility(pdf_path: str) -> dict:
    """Check a PDF file for common accessibility issues using PyMuPDF.

    Returns a dict with violations, passes, and metadata similar to axe-core output.
    """
    violations = []
    passes = []
    incomplete = []

    doc = fitz.open(pdf_path)
    metadata = doc.metadata or {}

    # --- Check: Document title in metadata ---
    title = metadata.get("title", "").strip()
    if title:
        passes.append(
            {
                "id": "pdf-title",
                "description": "PDF document has a title in metadata.",
                "help": "Document title",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#page-titled",
                "impact": None,
                "tags": ["wcag2a", "wcag211"],
                "nodes": [],
            }
        )
    else:
        violations.append(
            {
                "id": "pdf-title",
                "impact": "serious",
                "description": "PDF document is missing a title in metadata.",
                "help": "Documents must have a title (WCAG 2.4.2).",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#page-titled",
                "tags": ["wcag2a", "wcag242"],
                "nodes": [{"html": "<metadata>", "target": ["metadata"], "failureSummary": "Document title is missing from PDF metadata."}],
            }
        )

    # --- Check: Text extractability (not a scanned image) ---
    total_pages = len(doc)
    pages_with_text = sum(1 for page in doc if page.get_text("text").strip())
    if total_pages == 0:
        violations.append(
            {
                "id": "pdf-empty",
                "impact": "critical",
                "description": "PDF document appears to be empty.",
                "help": "PDF has no pages.",
                "helpUrl": "https://www.w3.org/TR/WCAG21/",
                "tags": [],
                "nodes": [],
            }
        )
    elif pages_with_text == 0:
        violations.append(
            {
                "id": "pdf-text-content",
                "impact": "critical",
                "description": (
                    "No extractable text found — PDF may consist entirely of scanned images "
                    "without OCR text layer."
                ),
                "help": "PDFs must contain real text, not just images (WCAG 1.1.1).",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#non-text-content",
                "tags": ["wcag2a", "wcag111"],
                "nodes": [
                    {
                        "html": f"<pages count={total_pages}>",
                        "target": ["page"],
                        "failureSummary": "No text layer detected. Add OCR or use an accessible PDF.",
                    }
                ],
            }
        )
    else:
        text_coverage = pages_with_text / total_pages
        if text_coverage < 0.5:
            incomplete.append(
                {
                    "id": "pdf-text-content",
                    "impact": "moderate",
                    "description": (
                        f"Only {pages_with_text} of {total_pages} pages have extractable text. "
                        "Some pages may be scanned images."
                    ),
                    "help": "All pages should have accessible text.",
                    "helpUrl": "https://www.w3.org/TR/WCAG21/#non-text-content",
                    "tags": ["wcag2a", "wcag111"],
                    "nodes": [],
                }
            )
        else:
            passes.append(
                {
                    "id": "pdf-text-content",
                    "description": f"PDF has extractable text on {pages_with_text}/{total_pages} pages.",
                    "help": "Text content",
                    "helpUrl": "https://www.w3.org/TR/WCAG21/#non-text-content",
                    "impact": None,
                    "tags": ["wcag2a", "wcag111"],
                    "nodes": [],
                }
            )

    # --- Check: Tagged PDF (structure tags) ---
    is_tagged = bool(doc.get_toc()) or _pdf_has_structure_tags(doc)
    if is_tagged:
        passes.append(
            {
                "id": "pdf-tagged",
                "description": "PDF appears to have structure/tag information.",
                "help": "Tagged PDF",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#info-and-relationships",
                "impact": None,
                "tags": ["wcag2a", "wcag131"],
                "nodes": [],
            }
        )
    else:
        violations.append(
            {
                "id": "pdf-tagged",
                "impact": "serious",
                "description": "PDF does not appear to be tagged (no structure tags or TOC found).",
                "help": "PDFs should be tagged for accessibility (WCAG 1.3.1).",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#info-and-relationships",
                "tags": ["wcag2a", "wcag131"],
                "nodes": [
                    {
                        "html": "<pdf>",
                        "target": ["document"],
                        "failureSummary": "Add structure tags to the PDF.",
                    }
                ],
            }
        )

    # --- Check: Language metadata ---
    language = metadata.get("language", "").strip() or _detect_pdf_language_marker(doc)
    if language:
        passes.append(
            {
                "id": "pdf-language",
                "description": f"PDF document language is set to: {language}",
                "help": "Document language",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#language-of-page",
                "impact": None,
                "tags": ["wcag2a", "wcag311"],
                "nodes": [],
            }
        )
    else:
        violations.append(
            {
                "id": "pdf-language",
                "impact": "serious",
                "description": "PDF document language is not specified in metadata.",
                "help": "The language of the document must be specified (WCAG 3.1.1).",
                "helpUrl": "https://www.w3.org/TR/WCAG21/#language-of-page",
                "tags": ["wcag2a", "wcag311"],
                "nodes": [
                    {
                        "html": "<metadata>",
                        "target": ["metadata"],
                        "failureSummary": "Set the document language in PDF properties.",
                    }
                ],
            }
        )

    # --- Check: Hyperlinks have descriptive text ---
    links_checked, bad_links = _check_pdf_links(doc)
    if links_checked > 0:
        if bad_links:
            violations.append(
                {
                    "id": "pdf-link-text",
                    "impact": "moderate",
                    "description": f"{len(bad_links)} link(s) have missing or non-descriptive text.",
                    "help": "Link text must be descriptive (WCAG 2.4.4).",
                    "helpUrl": "https://www.w3.org/TR/WCAG21/#link-purpose-in-context",
                    "tags": ["wcag2a", "wcag244"],
                    "nodes": [
                        {
                            "html": f"<a href={url!r}>",
                            "target": ["a"],
                            "failureSummary": "Link is missing descriptive text.",
                        }
                        for url in bad_links[:10]  # cap at 10 for display
                    ],
                }
            )
        else:
            passes.append(
                {
                    "id": "pdf-link-text",
                    "description": f"All {links_checked} link(s) appear to have associated text.",
                    "help": "Link text",
                    "helpUrl": "https://www.w3.org/TR/WCAG21/#link-purpose-in-context",
                    "impact": None,
                    "tags": ["wcag2a", "wcag244"],
                    "nodes": [],
                }
            )

    doc.close()
    return {
        "violations": violations,
        "passes": passes,
        "incomplete": incomplete,
        "inapplicable": [],
    }


def _pdf_has_structure_tags(doc: fitz.Document) -> bool:
    """Return True if the PDF has structure/accessibility tags."""
    try:
        xml = doc.get_xml_metadata()
        if xml and ("pdfaSchema" in xml or "Marked" in xml):
            return True
    except Exception:
        pass
    return False


def _detect_pdf_language_marker(doc: fitz.Document) -> str:
    """Try to detect language from XML metadata."""
    try:
        xml = doc.get_xml_metadata()
        if xml:
            match = re.search(r'xml:lang=["\']([^"\']+)["\']', xml)
            if match:
                return match.group(1)
            match = re.search(r'<dc:language[^>]*>([^<]+)</dc:language>', xml)
            if match:
                return match.group(1)
    except Exception:
        pass
    return ""


def _check_pdf_links(doc: fitz.Document):
    """Return (total_links, list_of_bare_urls_without_text)."""
    bare_urls = []
    total = 0
    for page in doc:
        for link in page.get_links():
            if link.get("kind") == fitz.LINK_URI:
                total += 1
                uri = link.get("uri", "")
                # Check if the link rectangle has visible text on the page
                rect = fitz.Rect(link.get("from"))
                words = page.get_text("words", clip=rect)
                if not words:
                    bare_urls.append(uri)
    return total, bare_urls


# ---------------------------------------------------------------------------
# Score Calculation
# ---------------------------------------------------------------------------


def _compute_score(violations: list, passes: list, incomplete: list) -> float:
    """Compute a 0-100 accessibility score.

    Higher is better. Weighted by impact level.
    """
    impact_weights = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}

    penalty = sum(
        impact_weights.get(v.get("impact", "minor"), 1) for v in violations
    )
    bonus = len(passes)
    total_signals = penalty + bonus + len(incomplete)
    if total_signals == 0:
        return 100.0
    raw = bonus / (bonus + penalty + 0.5 * len(incomplete))
    return round(raw * 100, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _normalise_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _save_audit(target: str, audit_type: str, results: dict | None, error: str | None) -> Audit:
    """Persist an audit to the database and return the model instance."""
    audit = Audit(
        target=target,
        audit_type=audit_type,
    )
    if error:
        audit.status = "error"
        audit.error_message = error
    else:
        violations = results.get("violations", [])
        passes = results.get("passes", [])
        incomplete = results.get("incomplete", [])
        inapplicable = results.get("inapplicable", [])
        audit.status = "success"
        audit.violations_count = len(violations)
        audit.passes_count = len(passes)
        audit.incomplete_count = len(incomplete)
        audit.inapplicable_count = len(inapplicable)
        audit.score = _compute_score(violations, passes, incomplete)
        audit.results_json = json.dumps(results)

    db.session.add(audit)
    db.session.commit()
    return audit


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def index():
    audits = Audit.query.order_by(Audit.created_at.desc()).limit(50).all()
    return render_template("index.html", audits=audits)


@app.route("/audit/url", methods=["POST"])
def audit_url():
    url = request.form.get("url", "").strip()
    if not url:
        flash("Please enter a URL.", "warning")
        return redirect(url_for("index"))

    url = _normalise_url(url)

    try:
        results = check_url_accessibility(url)
        audit = _save_audit(url, "url", results, None)
    except (RuntimeError, PlaywrightTimeoutError, OSError, ValueError) as exc:
        audit = _save_audit(url, "url", None, str(exc))
        flash(f"Error checking {url}: {exc}", "danger")
        return redirect(url_for("index"))

    return redirect(url_for("audit_detail", audit_id=audit.id))


@app.route("/audit/file", methods=["POST"])
def audit_file():
    if "file" not in request.files:
        flash("No file part in the request.", "warning")
        return redirect(url_for("index"))

    uploaded_file = request.files["file"]
    if not uploaded_file or uploaded_file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("index"))

    if not allowed_file(uploaded_file.filename):
        flash("Unsupported file type. Please upload a PDF or HTML file.", "warning")
        return redirect(url_for("index"))

    filename = secure_filename(uploaded_file.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    audit_type = "pdf" if ext == "pdf" else "html"
    tmp_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    uploaded_file.save(tmp_path)

    try:
        if ext == "pdf":
            results = check_pdf_accessibility(tmp_path)
        else:  # html / htm
            with open(tmp_path, encoding="utf-8", errors="replace") as fh:
                html_content = fh.read()
            results = check_html_accessibility(html_content, filename)

        audit = _save_audit(filename, audit_type, results, None)
    except (RuntimeError, PlaywrightTimeoutError, OSError, ValueError, fitz.FileDataError) as exc:
        audit = _save_audit(filename, audit_type, None, str(exc))
        flash(f"Error processing {filename}: {exc}", "danger")
        return redirect(url_for("index"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return redirect(url_for("audit_detail", audit_id=audit.id))


@app.route("/audit/<int:audit_id>")
def audit_detail(audit_id: int):
    audit = db.get_or_404(Audit, audit_id)
    results = audit.results()
    return render_template("audit_detail.html", audit=audit, results=results)


@app.route("/audit/<int:audit_id>/delete", methods=["POST"])
def delete_audit(audit_id: int):
    audit = db.get_or_404(Audit, audit_id)
    db.session.delete(audit)
    db.session.commit()
    flash("Audit deleted.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# App Entry Point
# ---------------------------------------------------------------------------


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
