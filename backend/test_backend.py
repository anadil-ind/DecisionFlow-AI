"""
Unit and integration tests for DecisionFlow AI backend.
Verifies health check, input validation, Cortex JSON parsing, and mocked analysis pipeline.
"""

import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from models import DocumentAnalysis
from snowflake_client import parse_json_safely, _compute_deadline_status

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


def test_compare_documents_validation_min_max():
    # 1 document should fail validation (min_length=2)
    resp1 = client.post("/compare", json={"document_ids": [101]}, headers={"X-Session-ID": "test-session"})
    assert resp1.status_code == 422

    # 4 documents should fail validation (max_length=3)
    resp4 = client.post("/compare", json={"document_ids": [101, 102, 103, 104]}, headers={"X-Session-ID": "test-session"})
    assert resp4.status_code == 422


def test_compare_documents_missing_session():
    resp = client.post("/compare", json={"document_ids": [101, 102]})
    assert resp.status_code == 400
    assert "Session" in resp.json()["detail"]


def test_compare_documents_success_2_docs_mocked():
    mock_doc1 = {
        "id": 101,
        "title": "Scholarship A - Merit Grant",
        "category": "Scholarship",
        "summary": "Full tuition merit grant for science students with 3.8 GPA.",
        "deadline": "2026-09-30",
        "priority": "High",
        "actions": ["Submit transcript", "Submit essay"],
        "required_documents": ["Transcript", "Valid ID", "Essay"],
        "created_at": "2026-09-24T10:00:00",
    }
    mock_doc2 = {
        "id": 102,
        "title": "Scholarship B - Leadership Fellowship",
        "category": "Scholarship",
        "summary": "Leadership grant for community advocates with letters of recommendation.",
        "deadline": "2026-10-15",
        "priority": "Medium",
        "actions": ["Complete portal application", "Request recommendation letters"],
        "required_documents": ["Valid ID", "Recommendation Letters", "Resume", "Statement of Purpose"],
        "created_at": "2026-09-24T10:30:00",
    }

    cortex_mock = {
        "eligibility_per_option": {
            "Option A": "Science majors with min 3.8 GPA.",
            "Option B": "Community service advocates, any major.",
        },
        "important_conditions_per_option": {
            "Option A": ["Must maintain 3.8 GPA through graduation."],
            "Option B": ["Must complete 50 hours community service."],
        },
        "common_information": [
            "Both options provide financial support for university studies.",
            "Both require formal application submission before deadline.",
        ],
        "differences": [
            "Option A is academic merit-based while Option B is leadership/service-based.",
            "Option A has an earlier deadline than Option B.",
        ],
        "conflicts": [
            "No conflicting information detected.",
        ],
        "important_conditions": [
            "Option A requires 3.8 GPA maintenance.",
            "Option B requires 50 hours community service.",
        ],
        "missing_information": [
            "Option B does not specify minimum GPA requirement.",
        ],
        "decision_summary": [
            "Option A has an earlier deadline (30 Sep 2026 vs 15 Oct 2026).",
            "Option B requires one additional document.",
            "Both options require a valid ID.",
            "Check GPA eligibility for Option A before applying.",
        ],
    }

    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.compare_documents_pipeline") as mock_pipeline:
        
        from snowflake_client import build_decision_comparison
        mock_pipeline.return_value = build_decision_comparison([mock_doc1, mock_doc2], cortex_data=cortex_mock)

        resp = client.post(
            "/compare",
            json={"document_ids": [101, 102]},
            headers={"X-Session-ID": "test-session-uuid-1"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["options"]) == 2
        assert data["options"][0]["title"] == "Scholarship A - Merit Grant"
        assert data["options"][1]["title"] == "Scholarship B - Leadership Fellowship"
        assert len(data["different_deadlines"]) >= 2
        assert any("earlier deadline" in d for d in data["different_deadlines"])
        assert "Valid ID" in data["different_requirements"]["common"]
        assert "Essay" in data["different_requirements"]["per_option"]["Option A"]
        assert len(data["conflicts"]) >= 1
        assert "No conflicting information detected." in data["conflicts"][0]
        assert len(data["decision_summary"]) >= 3
        # Strict neutrality check: no winner words
        for s in data["decision_summary"]:
            assert "winner" not in s.lower()
            assert "better" not in s.lower()
            assert "recommend" not in s.lower()


def test_compare_documents_success_3_docs_mocked():
    mock_docs = [
        {
            "id": 101, "title": "Program Alpha", "category": "Academic", "summary": "Alpha",
            "deadline": "2026-10-01", "priority": "High", "actions": ["Act 1"], "required_documents": ["ID"],
            "created_at": "2026-09-24T10:00:00",
        },
        {
            "id": 102, "title": "Program Beta", "category": "Academic", "summary": "Beta",
            "deadline": "2026-10-10", "priority": "Medium", "actions": ["Act 2"], "required_documents": ["ID", "Form"],
            "created_at": "2026-09-24T10:00:00",
        },
        {
            "id": 103, "title": "Program Gamma", "category": "Academic", "summary": "Gamma",
            "deadline": "2026-10-20", "priority": "Low", "actions": ["Act 3"], "required_documents": ["ID", "Photo"],
            "created_at": "2026-09-24T10:00:00",
        },
    ]

    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.compare_documents_pipeline") as mock_pipeline:
        
        from snowflake_client import build_decision_comparison
        mock_pipeline.return_value = build_decision_comparison(mock_docs, cortex_data=None)

        resp = client.post(
            "/compare",
            json={"document_ids": [101, 102, 103]},
            headers={"X-Session-ID": "test-session-uuid-1"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["options"]) == 3
        assert data["options"][2]["title"] == "Program Gamma"
        assert "ID" in data["different_requirements"]["common"]


def test_compare_documents_non_owned_or_invalid_id():
    with patch("main.SnowflakeConfig.is_configured", return_value=True), \
         patch("main.compare_documents_pipeline", side_effect=ValueError("One or more documents ([999]) not found or do not belong to current session.")):
        
        resp = client.post(
            "/compare",
            json={"document_ids": [101, 999]},
            headers={"X-Session-ID": "test-session-uuid-1"},
        )
        assert resp.status_code == 400
        assert "not found or do not belong" in resp.json()["detail"]


def test_build_decision_comparison_deterministic_fallback():
    from snowflake_client import build_decision_comparison
    doc_a = {
        "id": 1, "title": "Grant A", "category": "Finance", "summary": "Grant A details",
        "deadline": "2026-10-01", "priority": "High", "actions": ["Apply"], "required_documents": ["Tax Return", "ID"],
        "created_at": "2026-09-24",
    }
    doc_b = {
        "id": 2, "title": "Grant B", "category": "Finance", "summary": "Grant B details",
        "deadline": "2026-11-01", "priority": "Low", "actions": ["Apply"], "required_documents": ["ID"],
        "created_at": "2026-09-24",
    }

    res = build_decision_comparison([doc_a, doc_b], cortex_data=None)
    assert len(res["options"]) == 2
    assert "ID" in res["different_requirements"]["common"]
    assert "Tax Return" in res["different_requirements"]["per_option"]["Option A"]
    assert any("earlier deadline" in d for d in res["different_deadlines"])
    assert any("Option A is High" in d for d in res["differences"])
    assert len(res["decision_summary"]) >= 2




def test_deadline_status_computation():
    from datetime import date
    today = date(2026, 9, 24)

    # Completed takes precedence
    status, days = _compute_deadline_status('2026-09-20', completed=True, today=today)
    assert status == 'Completed'
    assert days == -4

    # Overdue
    status, days = _compute_deadline_status('2026-09-20', completed=False, today=today)
    assert status == 'Overdue'
    assert days == -4

    # Due today (0 days) is Due Soon
    status, days = _compute_deadline_status('2026-09-24', completed=False, today=today)
    assert status == 'Due Soon'
    assert days == 0

    # Due Soon (within 7 days)
    status, days = _compute_deadline_status('2026-09-28', completed=False, today=today)
    assert status == 'Due Soon'
    assert days == 4

    # Upcoming (> 7 days)
    status, days = _compute_deadline_status('2026-10-10', completed=False, today=today)
    assert status == 'Upcoming'
    assert days == 16

    # None deadline and not completed -> ignored
    status, days = _compute_deadline_status(None, completed=False, today=today)
    assert status is None
    assert days is None


def test_get_deadlines_missing_session():
    resp = client.get('/deadlines')
    assert resp.status_code == 400
    assert 'Session ID header' in resp.json()['detail']


def test_get_deadlines_success_mocked():
    mock_items = [
        {
            'document_id': 1,
            'task': 'Doc 1',
            'source_document': 'Doc 1',
            'category': 'Academic',
            'deadline': '2026-09-20',
            'days_remaining': -4,
            'priority': 'High',
            'required_action': 'Submit now',
            'actions': ['Submit now'],
            'status': 'Overdue',
            'completed': False,
            'created_at': '2026-09-24T10:00:00',
        },
        {
            'document_id': 2,
            'task': 'Doc 2',
            'source_document': 'Doc 2',
            'category': 'Financial',
            'deadline': '2026-09-28',
            'days_remaining': 4,
            'priority': 'Medium',
            'required_action': 'Pay fee',
            'actions': ['Pay fee'],
            'status': 'Due Soon',
            'completed': False,
            'created_at': '2026-09-24T10:00:00',
        },
        {
            'document_id': 3,
            'task': 'Doc 3',
            'source_document': 'Doc 3',
            'category': 'General',
            'deadline': '2026-10-15',
            'days_remaining': 21,
            'priority': 'Low',
            'required_action': 'Review',
            'actions': ['Review'],
            'status': 'Upcoming',
            'completed': False,
            'created_at': '2026-09-24T10:00:00',
        },
        {
            'document_id': 4,
            'task': 'Doc 4',
            'source_document': 'Doc 4',
            'category': 'Legal',
            'deadline': '2026-09-22',
            'days_remaining': -2,
            'priority': 'High',
            'required_action': 'Sign',
            'actions': ['Sign'],
            'status': 'Completed',
            'completed': True,
            'created_at': '2026-09-24T10:00:00',
        },
    ]
    with patch('main.get_deadline_items', return_value=mock_items):
        resp = client.get('/deadlines', headers={'X-Session-ID': 'test-session-123'})
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert len(body['data']) == 4
        assert body['counts']['Overdue'] == 1
        assert body['counts']['Due Soon'] == 1
        assert body['counts']['Upcoming'] == 1
        assert body['counts']['Completed'] == 1


def test_update_deadline_no_session():
    resp = client.patch('/deadlines/1', json={'completed': True})
    assert resp.status_code == 400
    assert 'Session ID header' in resp.json()['detail']


def test_update_deadline_not_owned():
    with patch('main.update_deadline_completion', return_value=False):
        resp = client.patch(
            '/deadlines/999',
            json={'completed': True},
            headers={'X-Session-ID': 'session-xyz'},
        )
        assert resp.status_code == 404
        assert 'not found' in resp.json()['detail']


def test_update_deadline_completion_mocked():
    with patch('main.update_deadline_completion', return_value=True):
        resp = client.patch(
            '/deadlines/1',
            json={'completed': True},
            headers={'X-Session-ID': 'session-xyz'},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert body['document_id'] == 1
        assert body['completed'] is True
        assert 'completed' in body['message']

        resp_uncheck = client.patch(
            '/deadlines/1',
            json={'completed': False},
            headers={'X-Session-ID': 'session-xyz'},
        )
        assert resp_uncheck.status_code == 200
        body_uncheck = resp_uncheck.json()
        assert body_uncheck['completed'] is False
        assert 'incomplete' in body_uncheck['message']


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
        test_compare_documents_validation_min_max,
        test_compare_documents_missing_session,
        test_compare_documents_success_2_docs_mocked,
        test_compare_documents_success_3_docs_mocked,
        test_compare_documents_non_owned_or_invalid_id,
        test_build_decision_comparison_deterministic_fallback,
        test_deadline_status_computation,
        test_get_deadlines_missing_session,
        test_get_deadlines_success_mocked,
        test_update_deadline_no_session,
        test_update_deadline_not_owned,
        test_update_deadline_completion_mocked,
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
