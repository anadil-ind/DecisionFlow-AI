"""
Pydantic data models for DecisionFlow AI Backend.
Defines schemas for incoming requests, Cortex structured analysis, and API responses.
"""

from typing import List, Optional
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

