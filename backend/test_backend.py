"""
Unit and integration tests for DecisionFlow AI backend.
Verifies health check, input validation, Cortex JSON parsing, and mocked analysis pipeline.
"""

import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from models import DocumentAnalysis
from snowflake_client import parse_json_safely

client = TestClient(app)


def test_parse_json_safely_clean():
    sample = {
        "title": "Semester Registration Notice",
        "category": "Academic",
        "summary": "Students must complete course registration by Oct 1.",
        "deadline": "2026-10-01",
        "priority": "High",
        "actions": ["Log into portal", "Select courses"],
        "required_documents": ["Transcript", "Fee Receipt"],
    }
    result = parse_json_safely(json.dumps(sample))
    assert result["title"] == "Semester Registration Notice"
    assert result["category"] == "Academic"
    assert result["priority"] == "High"
    assert len(result["actions"]) == 2
    assert len(result["required_documents"]) == 2


def test_parse_json_safely_markdown_wrapped():
    raw_markdown = """```json
{
  "title": "IT Maintenance Window",
  "category": "Operations",
  "summary": "Network upgrade this Saturday.",
  "deadline": "2026-09-26",
  "priority": "medium",
  "actions": ["Save open files"],
  "required_documents": []
}
```"""
    result = parse_json_safely(raw_markdown)
    assert result["title"] == "IT Maintenance Window"
    assert result["category"] == "Operations"
    assert result["priority"] == "Medium"  # Capitalized


def test_parse_json_safely_with_preamble_and_null_deadline():
    raw = """Here is the extracted information based on your document:
{
  "title": "General Office Policy Update",
  "category": "HR",
  "summary": "Updated hybrid work expectations.",
  "deadline": null,
  "priority": "Low",
  "actions": ["Review handbook"],
  "required_documents": []
}
Hope this helps!"""
    result = parse_json_safely(raw)
    assert result["title"] == "General Office Policy Update"
    assert result["deadline"] is None


def test_health_check_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "DECISIONFLOW_DB"
    assert data["cortex_model"] == "openai-gpt-5"


def test_analyze_text_empty_input():
    response = client.post("/analyze-text", json={"text": ""})
    assert response.status_code == 422


def test_analyze_text_too_short():
    response = client.post("/analyze-text", json={"text": "Hi"})
    assert response.status_code == 422


def test_analyze_text_missing_field():
    response = client.post("/analyze-text", json={})
    assert response.status_code == 422


def test_analyze_text_without_snowflake_env():
    # If no credentials in .env, should return 503 with helpful config instructions
    with patch("snowflake_client.SnowflakeConfig.is_configured", return_value=False):
        response = client.post(
            "/analyze-text",
            json={"text": "Notice: Submit all patent filings before Friday."},
        )
        assert response.status_code == 503
        assert "credentials are not configured" in response.json()["detail"]


def test_analyze_text_pipeline_mocked():
    mock_analysis = DocumentAnalysis(
        title="Patent Filing Submission Deadline",
        category="Legal",
        summary="Submit all pending IP and patent disclosures to the legal department.",
        deadline="2026-10-15",
        priority="High",
        actions=["Complete disclosure form", "Submit to legal counsel"],
        required_documents=["Invention Disclosure Form", "Prior Art Search"],
    )

    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.analyze_and_store_document", return_value=(mock_analysis, "test-doc-uuid-123")):
        
        response = client.post(
            "/analyze-text",
            json={"text": "Notice: Submit all patent filings before Friday with disclosure form."},
        )
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["inserted_id"] == "test-doc-uuid-123"
        assert res["data"]["title"] == "Patent Filing Submission Deadline"
        assert res["data"]["category"] == "Legal"
        assert res["data"]["priority"] == "High"
        assert len(res["data"]["actions"]) == 2
        assert len(res["data"]["required_documents"]) == 2


def test_parse_json_safely_single_quotes():
    # Exact scenario that triggered the error: line 1 column 2 expecting property name in double quotes
    raw_single_quotes = "{'title': 'Research Grant Call', 'category': 'Academic', 'summary': 'Submit grant proposals.', 'deadline': '2026-11-30', 'priority': 'High', 'actions': ['Write proposal'], 'required_documents': ['CV', 'Budget']}"
    result = parse_json_safely(raw_single_quotes)
    assert result["title"] == "Research Grant Call"
    assert result["category"] == "Academic"
    assert result["priority"] == "High"
    assert result["deadline"] == "2026-11-30"


def test_parse_json_safely_trailing_commas():
    raw_trailing = '{"title": "Library Notice", "category": "General", "summary": "Return books.", "deadline": null, "priority": "Low", "actions": ["Return book",], "required_documents": [],}'
    result = parse_json_safely(raw_trailing)
    assert result["title"] == "Library Notice"
    assert len(result["actions"]) == 1


def test_analyze_text_cortex_invalid_json_returns_422():
    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.analyze_and_store_document", side_effect=ValueError("Snowflake Cortex response was not valid JSON.")):
        
        response = client.post(
            "/analyze-text",
            json={"text": "Notice: Quarterly audit deadline approaching."},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Snowflake Cortex response was not valid JSON."


def _make_dummy_pdf(text: str) -> bytes:
    content_stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET"
    stream_len = len(content_stream)
    pdf = f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length {stream_len} >> stream
{content_stream}
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000117 00000 n 
0000000249 00000 n 
0000000325 00000 n 
trailer << /Root 1 0 R /Size 6 >>
startxref
406
%%EOF"""
    return pdf.encode("latin-1")


def test_analyze_pdf_invalid_extension():
    response = client.post(
        "/analyze-pdf",
        files={"file": ("test.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


def test_analyze_pdf_empty_file():
    response = client.post(
        "/analyze-pdf",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_analyze_pdf_mocked():
    sample_pdf_bytes = _make_dummy_pdf("Notice: Annual Cybersecurity Training must be completed by Dec 15.")
    mock_analysis = DocumentAnalysis(
        title="Annual Cybersecurity Training",
        category="Compliance",
        summary="Complete training by Dec 15.",
        deadline="2026-12-15",
        priority="High",
        actions=["Complete module"],
        required_documents=["Certificate"],
    )

    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.analyze_and_store_document", return_value=(mock_analysis, "pdf-doc-uuid-999")):

        response = client.post(
            "/analyze-pdf",
            files={"file": ("notice.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["inserted_id"] == "pdf-doc-uuid-999"
        assert res["data"]["title"] == "Annual Cybersecurity Training"
        assert res["data"]["category"] == "Compliance"
        assert "PDF successfully analyzed" in res["message"]


if __name__ == "__main__":
    tests = [
        test_parse_json_safely_clean,
        test_parse_json_safely_markdown_wrapped,
        test_parse_json_safely_with_preamble_and_null_deadline,
        test_parse_json_safely_single_quotes,
        test_parse_json_safely_trailing_commas,
        test_health_check_endpoint,
        test_analyze_text_empty_input,
        test_analyze_text_too_short,
        test_analyze_text_missing_field,
        test_analyze_text_without_snowflake_env,
        test_analyze_text_pipeline_mocked,
        test_analyze_text_cortex_invalid_json_returns_422,
        test_analyze_pdf_invalid_extension,
        test_analyze_pdf_empty_file,
        test_analyze_pdf_mocked,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__} - {e}")
            raise
    print(f"\nAll {passed} tests passed successfully!")
