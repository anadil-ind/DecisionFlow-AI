# DecisionFlow AI - Backend Service

DecisionFlow AI is a decision intelligence platform based on **PS02: "From Signal to Decision"**.
It analyzes unstructured information (notices, circulars, reports, policy updates, instructions, emails) using **Snowflake Cortex AI (`AI_COMPLETE` with `openai-gpt-5`)**, extracts actionable structured insights, and persists records directly into Snowflake (`DECISIONFLOW_DB.PUBLIC.DOCUMENTS`).

---

## Architecture Overview

```
[React Frontend] (Next Step)
        │
        ▼ HTTP REST (JSON / Plaintext)
[FastAPI Backend] (Port 8000)
        │
        ├── 1. POST /analyze-text (receives unstructured text)
        ├── 2. Snowflake Cortex AI_COMPLETE(model: openai-gpt-5)
        ├── 3. Safe JSON extraction & validation
        └── 4. INSERT into DECISIONFLOW_DB.PUBLIC.DOCUMENTS
        │
        ▼
[Snowflake Cortex & Database]
```

---

## Project Structure

```
backend/
├── .env.example          # Template for Snowflake credentials & server settings
├── .env                  # Local secret config (git-ignored)
├── .gitignore            # Git exclusions for venv, .env, pycache
├── requirements.txt      # Python dependencies
├── models.py             # Pydantic schemas (AnalyzeRequest, DocumentAnalysis, etc.)
├── snowflake_client.py   # Snowflake connection, Cortex AI prompt, dynamic table insertion
├── main.py               # FastAPI application with GET / and POST /analyze-text
└── README.md             # Documentation & usage guide
```

---

## Setup & Installation

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Access to a Snowflake account with:
  - Database: `DECISIONFLOW_DB`
  - Schema: `PUBLIC`
  - Table: `DOCUMENTS`
  - Cortex AI access enabled for role (e.g. `SNOWFLAKE.CORTEX_USER`)

### 2. Create and Activate Virtual Environment

Navigate to the `backend` directory:
```powershell
cd D:\DecisionFlow\backend
```

Create a virtual environment:
```powershell
python -m venv venv
```

Activate the virtual environment:
- On Windows (PowerShell):
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- On Windows (Command Prompt):
  ```cmd
  venv\Scripts\activate.bat
  ```
- On Linux/macOS:
  ```bash
  source venv/bin/activate
  ```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## Configuration (`.env`)

1. Copy `.env.example` to create your `.env` file:
   ```powershell
   cp .env.example .env
   ```
2. Open `.env` and fill in your Snowflake account details:
   ```env
   SNOWFLAKE_ACCOUNT=xy12345.us-east-1
   SNOWFLAKE_USER=your_username
   SNOWFLAKE_PASSWORD=your_password
   SNOWFLAKE_ROLE=ACCOUNTADMIN
   SNOWFLAKE_WAREHOUSE=COMPUTE_WH
   SNOWFLAKE_DATABASE=DECISIONFLOW_DB
   SNOWFLAKE_SCHEMA=PUBLIC
   CORTEX_MODEL=openai-gpt-5
   DOCUMENTS_TABLE=DOCUMENTS
   HOST=0.0.0.0
   PORT=8000
   ```

> **Security Note:** Never commit `.env` to Git. The `.gitignore` file automatically excludes `.env`.

---

## Running the Backend

Start the FastAPI development server:
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at:
- **API URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`

---

## API Endpoints & Testing

### 1. Health Check (`GET /`)

Check server and Snowflake configuration status:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/" -Method GET
```

**Response:**
```json
{
  "status": "healthy",
  "snowflake_configured": true,
  "database": "DECISIONFLOW_DB",
  "schema_name": "PUBLIC",
  "table": "DOCUMENTS",
  "cortex_model": "openai-gpt-5"
}
```

### 2. Analyze Document / Notice (`POST /analyze-text`)

Analyzes any document or notice, extracts actionable intelligence via Cortex AI (`openai-gpt-5`), and saves it to Snowflake `DOCUMENTS`.

#### Option A: JSON Body (Recommended)

```powershell
$body = @{
    text = "URGENT NOTICE: All employees must complete the Annual Security and Compliance training by Friday, November 14, 2026. Failure to submit certificate of completion will result in badge deactivation. Submit your certificate via the HR portal."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze-text" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

#### Option B: Plain Text Body

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze-text" `
  -Method POST `
  -ContentType "text/plain" `
  -Body "URGENT NOTICE: All employees must complete the Annual Security and Compliance training by Friday, November 14, 2026..."
```

#### Option C: Using cURL

```bash
curl -X POST "http://127.0.0.1:8000/analyze-text" \
  -H "Content-Type: application/json" \
  -d '{"text": "Campus Parking Permit renewals for Fall 2026 open September 25. Upload vehicle registration and proof of residence to the student portal before October 10 to avoid late penalty fees."}'
```

#### Sample Response:

```json
{
  "success": true,
  "data": {
    "title": "Annual Security & Compliance Training Deadline",
    "category": "Compliance",
    "summary": "Mandatory security and compliance training must be completed with certificate submitted to the HR portal by Nov 14, 2026 to avoid badge deactivation.",
    "deadline": "2026-11-14",
    "priority": "High",
    "actions": [
      "Complete the Annual Security and Compliance training course",
      "Obtain certificate of completion",
      "Submit certificate through HR portal before deadline"
    ],
    "required_documents": [
      "Certificate of completion"
    ]
  },
  "inserted_id": "a4d33458-9a4f-4d98-b80c-7b988f0e5eb1",
  "message": "Document successfully analyzed by Cortex AI and saved to Snowflake DOCUMENTS table."
}
```

### 3. Analyze PDF Document (`POST /analyze-pdf`)

Uploads a PDF document (`multipart/form-data`), extracts text, and processes it through the identical Snowflake Cortex AI (`openai-gpt-5`) and `DOCUMENTS` table storage pipeline.

#### PowerShell Example:

```powershell
$form = @{
    file = Get-Item -Path ".\notice.pdf"
}
Invoke-RestMethod -Uri "http://127.0.0.1:8000/analyze-pdf" `
  -Method POST `
  -Form $form
```

#### cURL Example:

```bash
curl -X POST "http://127.0.0.1:8000/analyze-pdf" \
  -F "file=@notice.pdf"
```

---

## Snowflake Schema Compatibility

The backend automatically inspects the existing `DOCUMENTS` table schema (`DESCRIBE TABLE DECISIONFLOW_DB.PUBLIC.DOCUMENTS`) and dynamically maps fields without modifying or dropping your table. It supports:
- `TITLE`, `CATEGORY`, `SUMMARY`, `DEADLINE`, `PRIORITY`
- `ACTIONS` (ARRAY, VARIANT, or VARCHAR)
- `REQUIRED_DOCUMENTS` (ARRAY, VARIANT, or VARCHAR)
- Optional `ID`, `RAW_TEXT`, `CREATED_AT`, and `METADATA` columns if present.
