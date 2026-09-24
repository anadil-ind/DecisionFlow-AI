"""
DecisionFlow AI - Backend API
FastAPI backend service connecting React frontend to Snowflake Cortex AI (openai-gpt-5)
and persisting structured intelligence into Snowflake DECISIONFLOW_DB.PUBLIC.DOCUMENTS.
"""

import io
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf import PdfReader

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    HistoryListResponse,
    HistoryDetailResponse,
    HistoryItem,
    DeleteResponse,
    CompareRequest,
    CompareResponse,
    ComparisonResult,
    DeadlineItem,
    DeadlineListResponse,
    UpdateCompletionRequest,
    UpdateCompletionResponse,
)
from snowflake_client import (
    SnowflakeConfig,
    analyze_and_store_document,
    get_active_history,
    get_document_by_id,
    delete_document_by_id,
    compare_documents_pipeline,
    get_deadline_items,
    update_deadline_completion,
)
from ocr_service import extract_text_from_image

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGES_LIMIT = 5
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("decisionflow.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook for startup checks and shutdown cleanup."""
    logger.info("Initializing DecisionFlow AI backend...")
    if SnowflakeConfig.is_configured():
        logger.info(
            "Snowflake credentials detected for database: %s, schema: %s, model: %s",
            SnowflakeConfig.get_config()["database"],
            SnowflakeConfig.get_config()["schema"],
            SnowflakeConfig.cortex_model(),
        )
    else:
        logger.warning(
            "Snowflake credentials are NOT configured. Copy .env.example to .env to enable Cortex analysis."
        )
    yield
    logger.info("DecisionFlow AI backend shutting down.")


app = FastAPI(
    title="DecisionFlow AI - Backend API",
    description="Generic intelligence engine turning unstructured documents and notices into structured actionable decisions.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for future React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["System"],
)
async def health_check():
    """
    Health check endpoint returning system status and Snowflake Cortex configuration readiness.
    """
    config = SnowflakeConfig.get_config()
    is_configured = SnowflakeConfig.is_configured()

    return HealthResponse(
        status="healthy",
        snowflake_configured=is_configured,
        database=config["database"],
        schema_name=config["schema"],
        table=SnowflakeConfig.documents_table(),
        cortex_model=SnowflakeConfig.cortex_model(),
    )


@app.post(
    "/analyze-text",
    response_model=AnalyzeResponse,
    summary="Analyze Unstructured Text via Snowflake Cortex AI",
    tags=["Analysis"],
)
async def analyze_text(
    payload: AnalyzeRequest,
    x_session_id: Optional[str] = Header(None),
):
    """
    Analyzes unstructured text (notices, circulars, instructions, reports, messages).
    1. Accepts JSON payload `{"text": "..."}` and optional X-Session-ID header.
    2. Sends the text to Snowflake Cortex AI using `AI_COMPLETE` with `openai-gpt-5`.
    3. Safely parses structured JSON (title, category, summary, deadline, priority, actions, required_documents).
    4. Inserts the structured record with session_id into Snowflake DECISIONFLOW_DB.PUBLIC.DOCUMENTS table.
    5. Returns the structured result and record ID.
    """
    clean_text = payload.text.strip()
    if len(clean_text) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text is too short. Minimum length is 5 characters.",
        )

    logger.info("Received text analysis request (%d characters, session: %s)", len(clean_text), x_session_id)

    # Check Snowflake credentials
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Snowflake credentials are not configured. "
                "Please configure backend/.env with SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD."
            ),
        )

    try:
        # Run Cortex AI inference and insert into Snowflake DOCUMENTS table with session_id
        analysis, inserted_id = analyze_and_store_document(clean_text, session_id=x_session_id)

        logger.info(
            "Document analyzed successfully: '%s' [Category: %s, Priority: %s, ID: %s]",
            analysis.title,
            analysis.category,
            analysis.priority,
            inserted_id,
        )

        return AnalyzeResponse(
            success=True,
            data=analysis,
            inserted_id=inserted_id,
            sources=["Text Input"],
            message="Document successfully analyzed by Cortex AI and saved to Snowflake DOCUMENTS table.",
        )

    except ValueError as ve:
        logger.error("Validation/Parsing error during analysis: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Snowflake Cortex response was not valid JSON.",
        )
    except Exception as exc:
        logger.error("Error processing document analysis: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Snowflake Cortex processing error: {str(exc)}",
        )


@app.post(
    "/analyze-pdf",
    response_model=AnalyzeResponse,
    summary="Analyze PDF Document via Snowflake Cortex AI",
    tags=["Analysis"],
)
async def analyze_pdf(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None),
):
    """
    Extracts readable text from an uploaded PDF file and processes it through the decision pipeline:
    1. Validates that the uploaded file is a PDF (.pdf) and contains readable text.
    2. Extracts text across all pages using pypdf.
    3. Reuses the existing Snowflake Cortex AI (AI_COMPLETE with openai-gpt-5) pipeline.
    4. Safely parses structured decision JSON.
    5. Inserts the structured record into Snowflake DECISIONFLOW_DB.PUBLIC.DOCUMENTS table.
    6. Returns the structured result and record ID.
    """
    # 1. Validate file extension
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files (.pdf) are accepted.",
        )

    # 2. Read file contents
    try:
        content = await file.read()
    except Exception as e:
        logger.error("Failed to read uploaded PDF '%s': %s", filename, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty.",
        )

    # 3. Extract text from PDF
    extracted_text_chunks = []
    page_count = 0
    try:
        reader = PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        if page_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF contains no pages.",
            )

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                extracted_text_chunks.append(page_text.strip())

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error extracting text from PDF '%s': %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse PDF content: {str(exc)}",
        )

    combined_text = "\n\n".join(extracted_text_chunks).strip()
    if not combined_text or len(combined_text) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text could be extracted from the uploaded PDF. Please provide a text-based PDF.",
        )

    logger.info(
        "Extracted %d characters from PDF '%s' across %d pages",
        len(combined_text),
        filename,
        page_count,
    )

    # 4. Check Snowflake credentials
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Snowflake credentials are not configured. "
                "Please configure backend/.env with SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD."
            ),
        )

    # 5. Reuse existing Cortex AI analysis and DOCUMENTS insertion pipeline
    try:
        analysis, inserted_id = analyze_and_store_document(combined_text, session_id=x_session_id)

        logger.info(
            "PDF '%s' analyzed successfully: '%s' [Category: %s, Priority: %s, ID: %s]",
            filename,
            analysis.title,
            analysis.category,
            analysis.priority,
            inserted_id,
        )

        return AnalyzeResponse(
            success=True,
            data=analysis,
            inserted_id=inserted_id,
            sources=[filename],
            message="PDF successfully analyzed by Cortex AI and saved to Snowflake DOCUMENTS table.",
        )

    except ValueError as ve:
        logger.error("Validation/Parsing error during PDF analysis: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Snowflake Cortex response was not valid JSON.",
        )
    except Exception as exc:
        logger.error("Error processing PDF document analysis: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Snowflake Cortex processing error: {str(exc)}",
        )


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Unified Multimodal Analysis (PDF, Images, Text)",
    tags=["Analysis"],
)
async def analyze_multimodal(
    pdf: Optional[UploadFile] = File(None),
    images: List[UploadFile] = File(default=[]),
    text: Optional[str] = Form(None),
    x_session_id: Optional[str] = Header(None),
):
    """
    Unified multimodal analysis endpoint.
    Accepts:
    - Optional PDF file (.pdf)
    - Optional list of supporting images (.png, .jpg, .jpeg, .webp, max 5)
    - Optional user text/notes
    At least one input must be provided.
    Processes all inputs as a single unified decision request through Snowflake Cortex AI.
    """
    # Filter empty upload artifacts
    valid_pdf = pdf if (pdf and pdf.filename and len(pdf.filename.strip()) > 0) else None
    valid_images = [img for img in images if img and img.filename and len(img.filename.strip()) > 0]
    valid_text = text.strip() if (text and len(text.strip()) > 0) else None

    # Validation: at least one input required
    if not valid_pdf and not valid_images and not valid_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No input provided. Please provide a PDF document, image(s), or text to analyze.",
        )

    chunks = []
    sources_analyzed = []

    # 1. Process PDF if provided
    if valid_pdf:
        pdf_name = valid_pdf.filename
        if not pdf_name.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format for '{pdf_name}'. Only PDF files (.pdf) are accepted.",
            )

        try:
            pdf_bytes = await valid_pdf.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read PDF '{pdf_name}': {str(e)}",
            )

        if not pdf_bytes or len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The uploaded PDF file '{pdf_name}' is empty.",
            )

        if len(pdf_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PDF '{pdf_name}' exceeds maximum allowed size of 15MB.",
            )

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_text_parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t and t.strip():
                    pdf_text_parts.append(t.strip())
            pdf_text = "\n\n".join(pdf_text_parts).strip()
        except Exception as exc:
            logger.error("Error reading PDF pages for '%s': %s", pdf_name, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to parse PDF content in '{pdf_name}': {str(exc)}",
            )

        sources_analyzed.append(pdf_name)
        if pdf_text:
            chunks.append(f"=== SOURCE: PDF DOCUMENT ({pdf_name}) ===\n{pdf_text}")
        else:
            chunks.append(f"=== SOURCE: PDF DOCUMENT ({pdf_name}) ===\n[Document provided; no embedded machine-readable text detected]")

    # 2. Process Images if provided
    if valid_images:
        if len(valid_images) > MAX_IMAGES_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many images uploaded. A maximum of {MAX_IMAGES_LIMIT} images can be analyzed at once.",
            )

        for img in valid_images:
            img_name = img.filename
            ext = os.path.splitext(img_name.lower())[1]
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type '{img_name}'. Supported formats: PDF, PNG, JPG, JPEG, WEBP.",
                )

            try:
                img_bytes = await img.read()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read image '{img_name}': {str(e)}",
                )

            if not img_bytes or len(img_bytes) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"The uploaded image '{img_name}' is empty.",
                )

            if len(img_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image '{img_name}' exceeds maximum allowed size of 15MB.",
                )

            try:
                img_text = extract_text_from_image(img_bytes, img_name)
            except Exception as e:
                logger.error("OCR extraction failed on '%s': %s", img_name, e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to process image '{img_name}': {str(e)}",
                )

            sources_analyzed.append(img_name)
            if img_text and img_text.strip():
                chunks.append(f"=== SOURCE: SUPPORTING IMAGE ({img_name}) ===\n{img_text.strip()}")
            else:
                chunks.append(f"=== SOURCE: SUPPORTING IMAGE ({img_name}) ===\n[Image attachment analyzed; visual verification noted]")

    # 3. Process text if provided
    if valid_text:
        sources_analyzed.append("User Notes")
        chunks.append(f"=== SOURCE: USER NOTES / TEXT ===\n{valid_text}")

    combined_text = "\n\n".join(chunks).strip()
    if not combined_text or len(combined_text) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable content or text could be extracted from the provided inputs. Please provide readable documents or text.",
        )

    # 4. Check Snowflake credentials
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snowflake credentials are not configured. Please check backend/.env.",
        )

    # 5. Execute Cortex AI analysis and insert into Snowflake
    try:
        analysis, inserted_id = analyze_and_store_document(combined_text, session_id=x_session_id)

        logger.info(
            "Unified analysis succeeded: '%s' [Sources: %s, Priority: %s, ID: %s]",
            analysis.title,
            sources_analyzed,
            analysis.priority,
            inserted_id,
        )

        return AnalyzeResponse(
            success=True,
            data=analysis,
            inserted_id=inserted_id,
            sources=sources_analyzed,
            message="Unified multimodal analysis completed successfully by Cortex AI.",
        )

    except ValueError as ve:
        logger.error("Validation error during multimodal analysis: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Snowflake Cortex response was not valid JSON.",
        )
    except Exception as exc:
        logger.error("Error processing multimodal analysis: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Snowflake Cortex processing error: {str(exc)}",
        )


@app.get(
    "/history",
    response_model=HistoryListResponse,
    summary="Get Active Document History",
    tags=["History"],
)
async def get_history(x_session_id: Optional[str] = Header(None)):
    """
    Returns the list of active analyzed documents from Snowflake DOCUMENTS table for the current session.
    Documents whose deadline has already passed (relative to Asia/Kolkata date) or belonging to other
    sessions/demo test records are excluded.
    Data is NOT deleted — only filtered in the response.
    """
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snowflake credentials are not configured.",
        )
    try:
        docs = get_active_history(session_id=x_session_id)
        items = [HistoryItem(**d) for d in docs]
        logger.info("GET /history (session=%s) returned %d active documents", x_session_id, len(items))
        return HistoryListResponse(success=True, data=items)
    except Exception as exc:
        logger.error("Error fetching document history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document history: {str(exc)}",
        )


@app.get(
    "/history/{document_id}",
    response_model=HistoryDetailResponse,
    summary="Get Document Detail by ID",
    tags=["History"],
)
async def get_history_item(
    document_id: int,
    x_session_id: Optional[str] = Header(None),
):
    """
    Returns the complete details of a specific analyzed document from the Snowflake DOCUMENTS table.
    Enforces session verification so users can only view their own session's documents.
    Returns HTTP 404 if the document ID does not exist or belongs to another session.
    """
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snowflake credentials are not configured.",
        )
    try:
        doc = get_document_by_id(document_id, session_id=x_session_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found.",
            )
        item = HistoryItem(**doc)
        logger.info("GET /history/%d (session=%s) returned document: '%s'", document_id, x_session_id, item.title)
        return HistoryDetailResponse(success=True, data=item)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching document ID %d: %s", document_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document: {str(exc)}",
        )


@app.delete(
    "/history/{document_id}",
    response_model=DeleteResponse,
    summary="Permanently Delete a Document Record",
    tags=["History"],
)
async def delete_history_item(
    document_id: int,
    x_session_id: Optional[str] = Header(None),
):
    """
    Permanently deletes a specific document record from the Snowflake DOCUMENTS table.
    Enforces session verification so users can only delete their own records.
    Returns HTTP 404 if the document ID does not exist or does not belong to the session.
    """
    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snowflake credentials are not configured.",
        )
    try:
        was_deleted = delete_document_by_id(document_id, session_id=x_session_id)
        if not was_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found.",
            )
        logger.info("DELETE /history/%d (session=%s) — document permanently removed.", document_id, x_session_id)
        return DeleteResponse(
            success=True,
            deleted_id=document_id,
            message=f"Document #{document_id} has been permanently deleted.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting document ID %d: %s", document_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(exc)}",
        )


@app.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare 2–3 Documents Side-by-Side",
    tags=["Decision Compare"],
)
async def compare_documents(
    payload: CompareRequest,
    x_session_id: Optional[str] = Header(None),
):
    """
    Compares 2 or 3 analyzed documents side-by-side:
    1. Validates that 2 to 3 document IDs are provided.
    2. Validates session ownership — only documents analyzed within the active user session can be compared.
    3. Analyzes commonalities, differences, conflicts, deadlines, requirements, and missing info.
    4. Generates an objective, action-oriented Decision Summary (strictly neutral, never chooses a winner).
    5. Returns structured comparison intelligence.
    """
    if not payload.document_ids or len(payload.document_ids) < 2 or len(payload.document_ids) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select between 2 and 3 documents to compare.",
        )

    if not x_session_id or not str(x_session_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session header (X-Session-ID) is missing. Cannot verify document ownership.",
        )

    if not SnowflakeConfig.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snowflake credentials are not configured.",
        )

    try:
        comparison = compare_documents_pipeline(
            document_ids=payload.document_ids,
            session_id=x_session_id,
        )
        logger.info(
            "POST /compare (session=%s) successfully compared %d documents: %s",
            x_session_id, len(payload.document_ids), payload.document_ids,
        )
        return CompareResponse(
            success=True,
            data=ComparisonResult(**comparison),
            message=f"Successfully compared {len(payload.document_ids)} documents side-by-side.",
        )
    except ValueError as ve:
        logger.warning("Comparison validation error: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as exc:
        logger.error("Error comparing documents: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare documents: {str(exc)}",
        )


@app.get("/deadlines", response_model=DeadlineListResponse, tags=["Deadline Center"])
async def list_deadlines(x_session_id: Optional[str] = Header(None)):
    """
    Retrieve all deadline items for the current session, categorized by status:
    Overdue, Due Soon, Upcoming, or Completed.
    """
    if not x_session_id or not x_session_id.strip():
        logger.warning("GET /deadlines rejected: missing X-Session-ID header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID header (X-Session-ID) is required to access deadlines.",
        )

    try:
        raw_items = get_deadline_items(session_id=x_session_id.strip())
        items = [DeadlineItem(**item) for item in raw_items]

        # Compute dynamic counts per status category
        counts = {
            "Overdue": 0,
            "Due Soon": 0,
            "Upcoming": 0,
            "Completed": 0,
        }
        for item in items:
            if item.status in counts:
                counts[item.status] += 1
            else:
                counts[item.status] = 1

        logger.info(
            "GET /deadlines (session=%s) returned %d items (counts=%s)",
            x_session_id, len(items), counts,
        )
        return DeadlineListResponse(
            success=True,
            data=items,
            counts=counts,
        )
    except Exception as exc:
        logger.error("Error retrieving deadlines: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deadlines: {str(exc)}",
        )


@app.patch("/deadlines/{document_id}", response_model=UpdateCompletionResponse, tags=["Deadline Center"])
async def update_deadline_completion_status(
    document_id: int,
    payload: UpdateCompletionRequest,
    x_session_id: Optional[str] = Header(None),
):
    """
    Toggle completion status of a document deadline.
    Persisted to the Snowflake DOCUMENTS table.
    """
    if not x_session_id or not x_session_id.strip():
        logger.warning("PATCH /deadlines/%d rejected: missing X-Session-ID header", document_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID header (X-Session-ID) is required to update deadline status.",
        )

    try:
        updated = update_deadline_completion(
            document_id=document_id,
            completed=payload.completed,
            session_id=x_session_id.strip(),
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document #{document_id} not found or does not belong to the current session.",
            )

        status_msg = "completed" if payload.completed else "incomplete"
        logger.info(
            "PATCH /deadlines/%d (session=%s) marked as %s",
            document_id, x_session_id, status_msg,
        )
        return UpdateCompletionResponse(
            success=True,
            document_id=document_id,
            completed=payload.completed,
            message=f"Document deadline successfully marked as {status_msg}.",
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as exc:
        logger.error("Error updating deadline completion for doc %d: %s", document_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deadline status: {str(exc)}",
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    logger.info("Starting DecisionFlow AI server on %s:%d", host, port)
    uvicorn.run("main:app", host=host, port=port, reload=True)
