# DecisionFlow AI - Backend Status

**Status:** Verified & Operational  
**Last Verified:** 2026-09-23  

---

## Architecture & Stack

- **Framework:** Python FastAPI
- **AI Engine:** Snowflake Cortex (`AI_COMPLETE`)
- **LLM Model:** `openai-gpt-5`
- **Snowflake Database:** `DECISIONFLOW_DB`
- **Snowflake Schema:** `PUBLIC`
- **Snowflake Table:** `DOCUMENTS`
- **PDF Engine:** `pypdf` + `python-multipart`

---

## API Endpoints

### 1. `POST /analyze-text`
Ingests unstructured text via JSON payload, processes it through Snowflake Cortex AI (`openai-gpt-5`), extracts structured decision intelligence, inserts the record into Snowflake `DOCUMENTS`, and returns the result.

#### Request Format (`application/json`):
```json
{
  "text": "Scholarship renewal applications must be submitted by 30 September 2026. Students must upload their latest marksheet and income certificate. Late applications may not be accepted."
}
```

### 2. `POST /analyze-pdf`
Accepts a PDF file upload (`multipart/form-data`), extracts readable text, and reuses the exact same Cortex AI analysis and Snowflake `DOCUMENTS` storage pipeline.

#### Request Format (`multipart/form-data`):
- `file`: Binary PDF file (e.g. `notice.pdf`)

---

## Extracted Intelligence Fields

1. `title` (string)
2. `category` (string)
3. `summary` (string)
4. `deadline` (string / null, `YYYY-MM-DD` or descriptive date)
5. `priority` (string: `High`, `Medium`, `Low`)
6. `actions` (array of strings)
7. `required_documents` (array of strings)

---

## End-to-End Verification Status

- **Automated Tests:** 15 of 15 tests passed (`python test_backend.py`)
- **Live Text Endpoint Verification (`POST /analyze-text`):** **SUCCESS (HTTP 200 OK)**, record inserted with `inserted_id: "101"`
- **Live PDF Endpoint Verification (`POST /analyze-pdf`):** **SUCCESS (HTTP 200 OK)**, record inserted with `inserted_id: "102"`
- **Snowflake Storage:** Confirmed stored in `DECISIONFLOW_DB.PUBLIC.DOCUMENTS` table.

#### Verified Live Response Payload (`POST /analyze-pdf`):
```json
{
  "success": true,
  "data": {
    "title": "Annual Vendor Compliance Audit Submission Requirement",
    "category": "Compliance",
    "summary": "Official notice mandating submission of Annual Vendor Compliance Audit reports by 15 November 2026 with SOC2 certificates and proof of insurance.",
    "deadline": "2026-11-15",
    "priority": "High",
    "actions": [
      "Prepare and submit the Annual Vendor Compliance Audit report by the deadline",
      "Upload current SOC2 certificate",
      "Upload valid proof of insurance",
      "Verify successful upload and confirmation of submission before the deadline"
    ],
    "required_documents": [
      "Annual Vendor Compliance Audit report",
      "SOC2 certificate",
      "Proof of insurance"
    ]
  },
  "inserted_id": "102",
  "message": "PDF successfully analyzed by Cortex AI and saved to Snowflake DOCUMENTS table."
}
```
