"""
Snowflake and Snowflake Cortex integration module for DecisionFlow AI.
Handles database connections, Cortex LLM prompt execution (AI_COMPLETE with openai-gpt-5),
safe JSON parsing of decision intelligence, and storing results in the DOCUMENTS table.
"""

import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as date_parser
import snowflake.connector
from snowflake.connector.errors import DatabaseError, ProgrammingError
from dotenv import load_dotenv

from models import DocumentAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("decisionflow.snowflake")

# Load environment variables
load_dotenv()


class SnowflakeConfig:
    """Reads and validates Snowflake configuration from environment variables."""

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        return {
            "account": os.getenv("SNOWFLAKE_ACCOUNT", "").strip(),
            "user": os.getenv("SNOWFLAKE_USER", "").strip(),
            "password": os.getenv("SNOWFLAKE_PASSWORD", "").strip(),
            "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN").strip(),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH").strip(),
            "database": os.getenv("SNOWFLAKE_DATABASE", "DECISIONFLOW_DB").strip(),
            "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC").strip(),
        }

    @classmethod
    def cortex_model(cls) -> str:
        return os.getenv("CORTEX_MODEL", "openai-gpt-5").strip()

    @classmethod
    def documents_table(cls) -> str:
        return os.getenv("DOCUMENTS_TABLE", "DOCUMENTS").strip()

    @classmethod
    def is_configured(cls) -> bool:
        cfg = cls.get_config()
        # Account, user, and password are the bare minimum requirements
        return bool(cfg["account"] and cfg["user"] and cfg["password"])


def get_snowflake_connection():
    """
    Creates and returns an active Snowflake connection using environment credentials.
    Raises ValueError if required connection credentials are not populated.
    """
    if not SnowflakeConfig.is_configured():
        raise ValueError(
            "Snowflake credentials are not fully configured. "
            "Please copy backend/.env.example to backend/.env and populate SNOWFLAKE_ACCOUNT, "
            "SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD."
        )

    config = SnowflakeConfig.get_config()
    conn_params = {
        "account": config["account"],
        "user": config["user"],
        "password": config["password"],
        "database": config["database"],
        "schema": config["schema"],
    }

    if config.get("warehouse"):
        conn_params["warehouse"] = config["warehouse"]
    if config.get("role"):
        conn_params["role"] = config["role"]

    return snowflake.connector.connect(**conn_params)


def parse_json_safely(raw_output: str) -> Dict[str, Any]:
    """
    Safely extracts and parses JSON from the Snowflake Cortex LLM output.
    Handles JSON-encoded string responses, accidental markdown code fences,
    surrounding commentary or whitespace, and repairs minor formatting quirks.
    """
    if not raw_output or not str(raw_output).strip():
        raise ValueError("Snowflake Cortex response was empty.")

    text = str(raw_output).strip()

    # Step 1: Check if the response is JSON-encoded (e.g. "\"{\\n ... }\"")
    # Snowflake connector often returns Cortex completions as JSON-serialized strings.
    data = None
    try:
        data = json.loads(text)
    except Exception:
        pass

    # If first pass returned a string (double-encoded JSON string), use that inner string
    if isinstance(data, str):
        text = data.strip()
        data = None

    # Step 2: If data is not yet a dict, clean and parse
    if not isinstance(data, dict):
        # Handle accidental markdown code fences (```json ... ``` or ``` ... ```)
        if "```" in text:
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
            if fence_match:
                text = fence_match.group(1).strip()
            else:
                text = re.sub(r"```[a-zA-Z]*", "", text)
                text = text.replace("```", "").strip()

        # Extract substring between outermost { and } to strip surrounding commentary or whitespace
        start_brace = text.find("{")
        end_brace = text.rfind("}")
        if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
            text = text[start_brace : end_brace + 1].strip()

        # Parse using json.loads()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback 1: Remove trailing commas in arrays/objects (e.g. [1, 2,] or {"a": 1,})
            cleaned = re.sub(r",\s*([\]}])", r"\1", text)
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Fallback 2: Fix single-quoted property names and string values (e.g. {'title': '...'})
                fixed_quotes = re.sub(r"(?<=[\{\[\,\:\s])'|'(?=[\}\]\,\:\s])", '"', cleaned)
                try:
                    data = json.loads(fixed_quotes)
                except json.JSONDecodeError as err:
                    logger.error("Failed to parse JSON from Cortex response: %s", raw_output)
                    raise ValueError("Snowflake Cortex response was not valid JSON.") from err

    if not isinstance(data, dict):
        raise ValueError("Snowflake Cortex response was not a valid JSON object.")

    # Step 3: Standardize and validate required fields
    standardized = {
        "title": str(data.get("title") or "Untitled Document").strip(),
        "category": str(data.get("category") or "General").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "deadline": data.get("deadline") if data.get("deadline") not in (None, "", "null", "None", "N/A", "n/a") else None,
        "priority": str(data.get("priority") or "Medium").strip().capitalize(),
        "actions": [str(a).strip() for a in data.get("actions", []) if a],
        "required_documents": [str(d).strip() for d in data.get("required_documents", []) if d],
    }

    if standardized["priority"] not in ("High", "Medium", "Low"):
        standardized["priority"] = "Medium"

    return standardized


def run_cortex_complete(text: str) -> str:
    """
    Calls Snowflake Cortex AI_COMPLETE using the configured model (default: openai-gpt-5).
    Falls back to SNOWFLAKE.CORTEX.COMPLETE if AI_COMPLETE is not available.
    """
    model_name = SnowflakeConfig.cortex_model()

    system_prompt = (
        "You are DecisionFlow AI, an expert decision-intelligence engine. "
        "Analyze all provided information from the PDF, text, and images together.\n\n"
        "Identify:\n"
        "- What the document/information is about\n"
        "- Important deadlines\n"
        "- Required actions\n"
        "- Required documents\n"
        "- Urgency/priority (High, Medium, or Low)\n"
        "- Important conditions or instructions\n\n"
        "Do not invent missing information.\n\n"
        "STRICT OUTPUT INSTRUCTIONS:\n"
        "1. Return ONLY valid JSON.\n"
        "2. Use double quotes for all JSON keys and string values. Never use single quotes.\n"
        "3. No markdown.\n"
        "4. No ```json code fences.\n"
        "5. No explanation before or after the JSON.\n\n"
        "Follow this exact JSON structure:\n"
        "{\n"
        '  "title": "Concise descriptive title",\n'
        '  "category": "Appropriate category (e.g., Academic, Administrative, Financial, Legal, Healthcare, HR, Operations, Compliance, General)",\n'
        '  "summary": "Comprehensive summary of core message and obligations",\n'
        '  "deadline": "Specific deadline or date mentioned (YYYY-MM-DD or text), or null",\n'
        '  "priority": "High, Medium, or Low",\n'
        '  "actions": ["Action item 1", "Action item 2"],\n'
        '  "required_documents": ["Required document or prerequisite 1", "Required document 2"]\n'
        "}\n\n"
        f"INFORMATION TO ANALYZE:\n{text}"
    )

    logger.info("Executing Snowflake Cortex AI_COMPLETE with model: %s", model_name)

    conn = get_snowflake_connection()
    try:
        with conn.cursor() as cur:
            # First attempt: Modern AI_COMPLETE function
            try:
                cur.execute("SELECT AI_COMPLETE(%s, %s)", (model_name, system_prompt))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
            except ProgrammingError as pe:
                logger.warning("AI_COMPLETE direct call failed (%s). Retrying with SNOWFLAKE.CORTEX.COMPLETE...", pe)
                # Fallback attempt: SNOWFLAKE.CORTEX.COMPLETE
                cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (model_name, system_prompt))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])

            raise ValueError("Snowflake Cortex returned empty response.")
    finally:
        conn.close()


def inspect_table_columns(conn, table_name: str) -> Dict[str, Dict[str, str]]:
    """
    Inspects existing column names, data types, and default definitions in the target Snowflake table.
    Returns a dictionary mapping UPPERCASE column names to their metadata dict.
    """
    columns = {}
    with conn.cursor() as cur:
        try:
            cur.execute(f"DESCRIBE TABLE {table_name}")
            for row in cur.fetchall():
                # DESCRIBE TABLE returns: name, type, kind, null?, default, ...
                col_name = str(row[0]).upper()
                col_type = str(row[1]).upper()
                col_default = str(row[4]).upper() if row[4] else ""
                columns[col_name] = {"type": col_type, "default": col_default}
        except Exception as e:
            logger.warning("Table DESCRIBE failed on %s: %s. Attempting fallback query.", table_name, e)
            cur.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_DEFAULT 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = %s
                """,
                (table_name.upper(),),
            )
            for row in cur.fetchall():
                col_name = str(row[0]).upper()
                col_type = str(row[1]).upper()
                col_default = str(row[2]).upper() if row[2] else ""
                columns[col_name] = {"type": col_type, "default": col_default}

    return columns


def insert_document_record(
    analysis: DocumentAnalysis,
    raw_text: str = "",
    session_id: Optional[str] = None,
) -> Optional[str]:
    """
    Inserts the structured analysis into the existing DECISIONFLOW_DB.PUBLIC.DOCUMENTS table.
    Inspects the actual table schema to dynamically map fields, preserving the existing table structure
    and saving SESSION_ID to isolate user sessions.
    """
    table_name = SnowflakeConfig.documents_table()
    conn = get_snowflake_connection()
    new_id = str(uuid.uuid4())

    try:
        col_meta = inspect_table_columns(conn, table_name)
        logger.info("Detected columns in table %s: %s", table_name, list(col_meta.keys()))

        if not col_meta:
            # Fallback if table inspection returns no columns
            logger.info("Using standard fallback insert into %s", table_name)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {table_name} 
                    (TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, ACTIONS, REQUIRED_DOCUMENTS, SESSION_ID)
                    SELECT %s, %s, %s, TRY_TO_DATE(CAST(%s AS VARCHAR)), %s, PARSE_JSON(%s), PARSE_JSON(%s), %s
                    """,
                    (
                        analysis.title,
                        analysis.category,
                        analysis.summary,
                        analysis.deadline,
                        analysis.priority,
                        json.dumps(analysis.actions),
                        json.dumps(analysis.required_documents),
                        session_id,
                    ),
                )
                conn.commit()
                cur.execute(f"SELECT ID FROM {table_name} ORDER BY ID DESC LIMIT 1")
                row = cur.fetchone()
                return str(row[0]) if row and row[0] is not None else new_id

        # Build dynamic insert based on detected columns
        insert_cols = []
        val_placeholders = []
        params = []

        for col_name, meta in col_meta.items():
            col_type = meta["type"]
            col_default = meta["default"]

            # Skip identity / autoincrement ID columns so Snowflake auto-generates them
            if col_name == "ID":
                if "IDENTITY" in col_default or "AUTOINCREMENT" in col_default or "NUMBER" in col_type:
                    # Let Snowflake auto-generate
                    continue
                else:
                    insert_cols.append("ID")
                    val_placeholders.append("%s")
                    params.append(new_id)

            elif col_name == "TITLE":
                insert_cols.append("TITLE")
                val_placeholders.append("%s")
                params.append(analysis.title)

            elif col_name == "CATEGORY":
                insert_cols.append("CATEGORY")
                val_placeholders.append("%s")
                params.append(analysis.category)

            elif col_name == "SUMMARY":
                insert_cols.append("SUMMARY")
                val_placeholders.append("%s")
                params.append(analysis.summary)

            elif col_name == "DEADLINE":
                insert_cols.append("DEADLINE")
                if "DATE" in col_type or "TIME" in col_type:
                    val_placeholders.append("TRY_TO_DATE(CAST(%s AS VARCHAR))")
                else:
                    val_placeholders.append("%s")
                params.append(analysis.deadline)

            elif col_name == "PRIORITY":
                insert_cols.append("PRIORITY")
                val_placeholders.append("%s")
                params.append(analysis.priority)

            elif col_name == "ACTIONS":
                insert_cols.append("ACTIONS")
                if "ARRAY" in col_type or "VARIANT" in col_type:
                    val_placeholders.append("PARSE_JSON(%s)")
                    params.append(json.dumps(analysis.actions))
                else:
                    val_placeholders.append("%s")
                    params.append(json.dumps(analysis.actions))

            elif col_name in ("REQUIRED_DOCUMENTS", "REQUIREMENTS", "DOCUMENTS_REQUIRED"):
                insert_cols.append(col_name)
                if "ARRAY" in col_type or "VARIANT" in col_type:
                    val_placeholders.append("PARSE_JSON(%s)")
                    params.append(json.dumps(analysis.required_documents))
                else:
                    val_placeholders.append("%s")
                    params.append(json.dumps(analysis.required_documents))

            elif col_name in ("RAW_TEXT", "CONTENT", "ORIGINAL_TEXT", "DOCUMENT_TEXT"):
                insert_cols.append(col_name)
                val_placeholders.append("%s")
                params.append(raw_text)

            elif col_name in ("METADATA", "PAYLOAD", "DATA", "STRUCTURED_RESULT"):
                insert_cols.append(col_name)
                if "VARIANT" in col_type or "OBJECT" in col_type:
                    val_placeholders.append("PARSE_JSON(%s)")
                    params.append(json.dumps(analysis.model_dump()))
                else:
                    val_placeholders.append("%s")
                    params.append(json.dumps(analysis.model_dump()))

            elif col_name in ("CREATED_AT", "INSERTED_AT", "TIMESTAMP"):
                if "CURRENT_TIMESTAMP" in col_default:
                    # Let default fill it
                    continue
                else:
                    insert_cols.append(col_name)
                    val_placeholders.append("CURRENT_TIMESTAMP()")

            elif col_name == "SESSION_ID":
                insert_cols.append("SESSION_ID")
                val_placeholders.append("%s")
                params.append(session_id)

        if not insert_cols:
            raise ValueError(f"No recognizable columns found to insert in table {table_name}")

        query = f"INSERT INTO {table_name} ({', '.join(insert_cols)}) SELECT {', '.join(val_placeholders)}"
        logger.info("Executing insert query into %s with %d columns", table_name, len(insert_cols))

        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            conn.commit()

            # Retrieve the newly inserted ID
            try:
                cur.execute(f"SELECT ID FROM {table_name} ORDER BY ID DESC LIMIT 1")
                row = cur.fetchone()
                if row and row[0] is not None:
                    return str(row[0])
            except Exception as e:
                logger.warning("Could not fetch last inserted ID: %s", e)

        return new_id

    finally:
        conn.close()


def parse_deadline_date(deadline_val: Any) -> Optional[date]:
    """
    Parses deadline string into a datetime.date object.
    Supports ISO formats (YYYY-MM-DD), natural language dates, and common date formats.
    Returns None if deadline is empty, null, or unparseable.
    """
    if not deadline_val or not isinstance(deadline_val, (str, bytes)):
        return None
    text = str(deadline_val).strip()
    if not text or text.lower() in ("null", "none", "n/a", "tbd", "unknown"):
        return None

    # Try ISO match YYYY-MM-DD first (ensures year-month-day is never confused with day-first)
    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # Clean ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
    try:
        dt = date_parser.parse(cleaned, fuzzy=True, yearfirst=True)
        return dt.date()
    except Exception:
        return None


def calculate_priority_from_deadline(deadline_val: Any, fallback_priority: str = "Medium") -> str:
    """
    Deterministic priority classification based on extracted deadline:
    - If deadline has already passed -> HIGH
    - If 0 to 4 calendar days remain -> HIGH
    - If 5 to 11 calendar days remain -> MEDIUM
    - If more than 11 calendar days remain -> LOW
    - If no valid/extracted deadline -> fallback to AI-derived priority

    Calculated relative to Asia/Kolkata timezone (UTC+05:30) calendar date context.
    """
    parsed_date = parse_deadline_date(deadline_val)
    if parsed_date is None:
        normalized = str(fallback_priority or "Medium").strip().capitalize()
        return normalized if normalized in ("High", "Medium", "Low") else "Medium"

    # Asia/Kolkata timezone context (UTC+05:30)
    kolkata_tz = timezone(timedelta(hours=5, minutes=30))
    today_kolkata = datetime.now(kolkata_tz).date()
    days_remaining = (parsed_date - today_kolkata).days

    if days_remaining <= 4:
        return "High"
    elif 5 <= days_remaining <= 11:
        return "Medium"
    else:
        return "Low"


def analyze_and_store_document(
    text: str,
    session_id: Optional[str] = None,
) -> Tuple[DocumentAnalysis, Optional[str]]:
    """
    Full pipeline:
    1. Sends text to Snowflake Cortex AI_COMPLETE with openai-gpt-5
    2. Parses returned structured JSON
    3. Computes deterministic priority based on extracted deadline
    4. Inserts document record with session_id into Snowflake DOCUMENTS table
    5. Returns parsed DocumentAnalysis and inserted record id
    """
    raw_response = run_cortex_complete(text)
    parsed_dict = parse_json_safely(raw_response)

    # Apply deterministic deadline-based priority calculation
    original_ai_priority = parsed_dict.get("priority", "Medium")
    corrected_priority = calculate_priority_from_deadline(
        parsed_dict.get("deadline"),
        fallback_priority=original_ai_priority,
    )
    if corrected_priority != original_ai_priority:
        logger.info(
            "Deterministic priority applied: deadline='%s' (parsed=%s) -> priority shifted from '%s' to '%s'",
            parsed_dict.get("deadline"),
            parse_deadline_date(parsed_dict.get("deadline")),
            original_ai_priority,
            corrected_priority,
        )
    parsed_dict["priority"] = corrected_priority

    analysis = DocumentAnalysis(**parsed_dict)

    inserted_id = insert_document_record(analysis, text, session_id=session_id)
    return analysis, inserted_id


def _format_document_row(row: Tuple[Any, ...]) -> Dict[str, Any]:
    """
    Safely normalizes a row from the DOCUMENTS table into a clean dictionary.
    Handles Snowflake VARIANT / JSON arrays, dates, and timestamps.
    """
    doc_id, title, category, summary, deadline, priority, actions, required_documents, created_at = row

    # Parse actions if string/JSON
    parsed_actions: List[str] = []
    if actions:
        if isinstance(actions, list):
            parsed_actions = [str(a).strip() for a in actions if a]
        elif isinstance(actions, str):
            try:
                loaded = json.loads(actions)
                if isinstance(loaded, list):
                    parsed_actions = [str(a).strip() for a in loaded if a]
                else:
                    parsed_actions = [str(loaded).strip()]
            except Exception:
                parsed_actions = [actions.strip()]

    # Parse required_documents if string/JSON
    parsed_docs: List[str] = []
    if required_documents:
        if isinstance(required_documents, list):
            parsed_docs = [str(d).strip() for d in required_documents if d]
        elif isinstance(required_documents, str):
            try:
                loaded = json.loads(required_documents)
                if isinstance(loaded, list):
                    parsed_docs = [str(d).strip() for d in loaded if d]
                else:
                    parsed_docs = [str(loaded).strip()]
            except Exception:
                parsed_docs = [required_documents.strip()]

    # Format deadline
    deadline_str = None
    if deadline:
        if hasattr(deadline, "isoformat"):
            deadline_str = deadline.isoformat()
        else:
            deadline_str = str(deadline).strip()

    # Format created_at
    created_str = None
    if created_at:
        if hasattr(created_at, "isoformat"):
            created_str = created_at.isoformat()
        else:
            created_str = str(created_at).strip()

    return {
        "id": int(doc_id),
        "title": str(title or "Untitled Document").strip(),
        "category": str(category or "General").strip(),
        "summary": str(summary or "").strip(),
        "deadline": deadline_str,
        "priority": str(priority or "Medium").strip().capitalize(),
        "actions": parsed_actions,
        "required_documents": parsed_docs,
        "created_at": created_str,
    }


def get_active_history(
    session_id: Optional[str] = None,
    today_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves active analyzed documents from the Snowflake DOCUMENTS table.
    Enforces isolation by session_id:
    - If session_id is None or empty, returns an empty list to avoid leaking cross-session or demo data.
    - Filters out documents whose deadline has already passed (< today's date in Asia/Kolkata).
    - Documents with NULL deadline remain in active history.
    - Sorted by deadline ascending (when present), then created_at descending.
    """
    if not session_id or not str(session_id).strip():
        logger.info("get_active_history called without session_id — returning empty list.")
        return []

    if today_date is None:
        kolkata_tz = timezone(timedelta(hours=5, minutes=30))
        today_date = datetime.now(kolkata_tz).date()

    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()

    query = f"""
    SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT
    FROM {table_name}
    WHERE SESSION_ID = %s AND (DEADLINE IS NULL OR DEADLINE >= %s)
    ORDER BY 
        CASE WHEN DEADLINE IS NULL THEN 1 ELSE 0 END ASC,
        DEADLINE ASC,
        CREATED_AT DESC
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query, (str(session_id).strip(), str(today_date)))
            rows = cur.fetchall()
            return [_format_document_row(r) for r in rows]
    finally:
        conn.close()


def get_document_by_id(
    document_id: int,
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves the complete document record from Snowflake DOCUMENTS table by its ID.
    Enforces session isolation if session_id is provided, preventing cross-session inspection.
    """
    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()

    if session_id and str(session_id).strip():
        query = f"""
        SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT
        FROM {table_name}
        WHERE ID = %s AND SESSION_ID = %s
        """
        params = (document_id, str(session_id).strip())
    else:
        query = f"""
        SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT
        FROM {table_name}
        WHERE ID = %s
        """
        params = (document_id,)

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            return _format_document_row(row)
    finally:
        conn.close()


def delete_document_by_id(
    document_id: int,
    session_id: Optional[str] = None,
) -> bool:
    """
    Permanently deletes a specific document record belonging to session_id from DOCUMENTS table.
    Enforces session verification so users can only delete their own records.
    Returns True if a row was deleted, False if no matching record was found.
    """
    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()

    if session_id and str(session_id).strip():
        query = f"DELETE FROM {table_name} WHERE ID = %s AND SESSION_ID = %s"
        params = (document_id, str(session_id).strip())
    else:
        query = f"DELETE FROM {table_name} WHERE ID = %s"
        params = (document_id,)

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            deleted_count = cur.rowcount
            conn.commit()
            logger.info(
                "DELETE /history/%d (session=%s) — %d row(s) removed from %s",
                document_id, session_id, deleted_count, table_name,
            )
            return deleted_count > 0
    finally:
        conn.close()


