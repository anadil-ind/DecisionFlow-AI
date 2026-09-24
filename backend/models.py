"""
Pydantic data models for DecisionFlow AI Backend.
Defines schemas for incoming requests, Cortex structured analysis, and API responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """
    Input payload for document/notice text analysis.
    Accepts arbitrary unstructured text (notices, circulars, instructions, reports, etc.).
    """
    text: str = Field(
        ...,
        description="The raw unstructured text content to analyze.",
        min_length=5,
        examples=["Notice: All quarterly compliance audits must be submitted by Oct 15, 2026."]
    )


class DocumentAnalysis(BaseModel):
    """
    Structured extraction schema produced by Snowflake Cortex AI (openai-gpt-5).
    """
    title: str = Field(
        ...,
        description="Concise, descriptive title for the document/notice."
    )
    category: str = Field(
        ...,
        description="Categorization of the document (e.g., Academic, Administrative, Financial, Legal, Operations, HR, General)."
    )
    summary: str = Field(
        ...,
        description="Clear and comprehensive summary of key points and objectives."
    )
    deadline: Optional[str] = Field(
        default=None,
        description="Specific deadline or date mentioned (YYYY-MM-DD or descriptive text), or null if not applicable."
    )
    priority: str = Field(
        default="Medium",
        description="Priority rating (High, Medium, Low) based on urgency and consequences of inaction."
    )
    actions: List[str] = Field(
        default_factory=list,
        description="List of actionable next steps required."
    )
    required_documents: List[str] = Field(
        default_factory=list,
        description="List of documents, certificates, forms, or credentials required."
    )


class AnalyzeResponse(BaseModel):
    """
    API response returned by the analysis endpoints (/analyze, /analyze-text, /analyze-pdf).
    """
    success: bool = Field(True, description="Indicates if the analysis and insertion succeeded.")
    data: DocumentAnalysis = Field(..., description="The structured intelligence extracted by Cortex AI.")
    inserted_id: Optional[str] = Field(None, description="Record identifier generated or returned from Snowflake.")
    sources: List[str] = Field(default_factory=list, description="List of source file names or input identifiers analyzed.")
    message: Optional[str] = Field(None, description="Optional status or informational message.")


class HealthResponse(BaseModel):
    """
    Health check response model.
    """
    status: str
    snowflake_configured: bool
    database: str
    schema_name: str
    table: str
    cortex_model: str


class HistoryItem(BaseModel):
    """
    Schema representing an analyzed document record from Snowflake DOCUMENTS table.
    """
    id: int
    title: str
    category: str
    summary: str
    deadline: Optional[str] = None
    priority: str
    actions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class HistoryListResponse(BaseModel):
    """
    API response returned by GET /history.
    """
    success: bool = Field(True, description="Indicates if the query succeeded.")
    data: List[HistoryItem] = Field(default_factory=list, description="List of active analyzed documents.")


class HistoryDetailResponse(BaseModel):
    """
    API response returned by GET /history/{document_id}.
    """
    success: bool = Field(True, description="Indicates if document retrieval succeeded.")
    data: HistoryItem = Field(..., description="Complete document details.")


class DeleteResponse(BaseModel):
    """
    API response returned by DELETE /history/{document_id}.
    """
    success: bool = Field(..., description="True if the document was deleted, False if not found.")
    deleted_id: int = Field(..., description="The ID of the document that was targeted for deletion.")
    message: str = Field(..., description="Human-readable result message.")


class CompareRequest(BaseModel):
    """
    Request payload for comparing 2 or 3 analyzed documents.
    """
    document_ids: List[int] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="List of 2 to 3 document IDs to compare side by side."
    )


class OptionDetail(BaseModel):
    """
    Structured profile of an individual analyzed document in the comparison.
    """
    id: int
    title: str
    category: str
    summary: str
    deadline: Optional[str] = None
    priority: str
    actions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    eligibility: Optional[str] = None
    important_conditions: List[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    """
    Comprehensive multi-document decision comparison result.
    Combines deterministic parameter differences with Cortex AI semantic insights.
    Strictly factual; never declares a winner or recommends an option.
    """
    options: List[OptionDetail] = Field(default_factory=list)
    common_information: List[str] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    different_deadlines: List[str] = Field(default_factory=list)
    different_requirements: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    important_conditions: List[str] = Field(default_factory=list)
    decision_summary: List[str] = Field(default_factory=list)


class CompareResponse(BaseModel):
    """
    API response returned by POST /compare.
    """
    success: bool = Field(True, description="Indicates if the comparison succeeded.")
    data: ComparisonResult = Field(..., description="Structured comparison intelligence.")
    message: Optional[str] = Field(None, description="Optional informational message.")


# ── Deadline Center ────────────────────────────────────────────────────────────

class DeadlineItem(BaseModel):
    """
    A single deadline record derived from an analyzed DOCUMENTS entry.
    Includes computed status classification and days_remaining.
    """
    document_id: int = Field(..., description="Snowflake DOCUMENTS table row ID.")
    task: str = Field(..., description="Title / task name from the analyzed document.")
    source_document: str = Field(..., description="Same as task — human-readable source document name.")
    category: str = Field(default="General", description="Category extracted during analysis.")
    deadline: Optional[str] = Field(None, description="Deadline in ISO format (YYYY-MM-DD) or None if absent.")
    days_remaining: Optional[int] = Field(None, description="Calendar days until deadline; negative = overdue.")
    priority: str = Field(default="Medium", description="Priority level: High, Medium, or Low.")
    required_action: str = Field(default="Action not specified", description="Primary required action from document.")
    actions: List[str] = Field(default_factory=list, description="All extracted action items from the document.")
    status: str = Field(..., description="Computed status: Overdue | Due Soon | Upcoming | Completed.")
    completed: bool = Field(default=False, description="Whether the user has manually marked this deadline complete.")
    created_at: Optional[str] = Field(None, description="Record insertion timestamp.")


class DeadlineListResponse(BaseModel):
    """
    API response returned by GET /deadlines.
    """
    success: bool = Field(True, description="Indicates if the query succeeded.")
    data: List[DeadlineItem] = Field(default_factory=list, description="List of deadline records for the current session.")
    counts: Dict[str, int] = Field(default_factory=dict, description="Summary counts per status category.")


class UpdateCompletionRequest(BaseModel):
    """
    Request payload for PATCH /deadlines/{document_id}.
    Allows toggling completion state.
    """
    completed: bool = Field(..., description="True to mark complete; False to mark incomplete.")


class UpdateCompletionResponse(BaseModel):
    """
    API response returned by PATCH /deadlines/{document_id}.
    """
    success: bool = Field(True, description="Indicates if the update succeeded.")
    document_id: int = Field(..., description="ID of the updated document.")
    completed: bool = Field(..., description="New completion state after the update.")
    message: str = Field(..., description="Human-readable result message.")

