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


def extract_json_from_cortex(raw_output: str) -> Dict[str, Any]:
    """
    Safely extracts and parses any JSON dictionary from Snowflake Cortex LLM output.
    Handles double JSON-encoding, accidental markdown code fences, preambles/epilogues,
    trailing commas, and single quotes.
    """
    if not raw_output or not str(raw_output).strip():
        raise ValueError("Snowflake Cortex response was empty.")

    text = str(raw_output).strip()

    # Step 1: Check if the response is JSON-encoded (e.g. "\"{\\n ... }\"")
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

    return data


def parse_json_safely(raw_output: str) -> Dict[str, Any]:
    """
    Safely extracts and standardizes document analysis JSON from Snowflake Cortex LLM output.
    """
    data = extract_json_from_cortex(raw_output)

    # Standardize and validate required fields for DocumentAnalysis
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


def execute_cortex_prompt(prompt: str) -> str:
    """
    Executes an arbitrary prompt via Snowflake Cortex AI_COMPLETE (or SNOWFLAKE.CORTEX.COMPLETE)
    using the configured model (default: openai-gpt-5).
    """
    model_name = SnowflakeConfig.cortex_model()
    logger.info("Executing Snowflake Cortex call with model: %s", model_name)

    conn = get_snowflake_connection()
    try:
        with conn.cursor() as cur:
            # First attempt: Modern AI_COMPLETE function
            try:
                cur.execute("SELECT AI_COMPLETE(%s, %s)", (model_name, prompt))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
            except ProgrammingError as pe:
                logger.warning("AI_COMPLETE direct call failed (%s). Retrying with SNOWFLAKE.CORTEX.COMPLETE...", pe)
                # Fallback attempt: SNOWFLAKE.CORTEX.COMPLETE
                cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (model_name, prompt))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])

            raise ValueError("Snowflake Cortex returned empty response.")
    finally:
        conn.close()


def run_cortex_complete(text: str) -> str:
    """
    Calls Snowflake Cortex AI_COMPLETE for document analysis.
    """
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

    return execute_cortex_prompt(system_prompt)


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


def get_documents_by_ids(
    document_ids: List[int],
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves multiple document records belonging to session_id from DOCUMENTS table.
    Enforces strict session isolation: documents belonging to another session are never returned.
    Preserves the exact order of document_ids requested.
    """
    if not document_ids or not session_id or not str(session_id).strip():
        logger.info("get_documents_by_ids called without session_id or empty ids — returning empty list.")
        return []

    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()
    clean_ids = [int(i) for i in document_ids]
    placeholders = ", ".join(["%s"] * len(clean_ids))

    query = f"""
    SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT
    FROM {table_name}
    WHERE ID IN ({placeholders}) AND SESSION_ID = %s
    """
    params = tuple(clean_ids) + (str(session_id).strip(),)

    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            doc_map = {int(row[0]): _format_document_row(row) for row in rows}
            return [doc_map[did] for did in clean_ids if did in doc_map]
    finally:
        conn.close()


def format_deadline_display(deadline_val: Any) -> Optional[str]:
    """Formats deadline string/date into clean readable format (e.g. '30 Sep 2026')."""
    parsed = parse_deadline_date(deadline_val)
    if parsed:
        return parsed.strftime("%d %b %Y")
    if deadline_val and str(deadline_val).strip() and str(deadline_val).lower() not in ("null", "none", "n/a"):
        return str(deadline_val).strip()
    return None


def run_cortex_compare(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calls Snowflake Cortex AI (openai-gpt-5) to perform semantic comparison,
    conflict identification, eligibility analysis, and factual summary generation.
    Returns parsed dictionary or empty dict on failure.
    """
    option_letters = ["Option A", "Option B", "Option C"]
    doc_sections = []
    for idx, doc in enumerate(documents):
        label = option_letters[idx] if idx < len(option_letters) else f"Option {idx + 1}"
        docs_req = ", ".join(doc.get("required_documents") or []) or "None specified"
        actions = ", ".join(doc.get("actions") or []) or "None specified"
        dl = format_deadline_display(doc.get("deadline")) or "Not specified"
        sec = (
            f"=== {label}: {doc.get('title')} ===\n"
            f"Category: {doc.get('category')}\n"
            f"Deadline: {dl}\n"
            f"Priority: {doc.get('priority')}\n"
            f"Summary: {doc.get('summary')}\n"
            f"Required Documents: {docs_req}\n"
            f"Actions: {actions}"
        )
        doc_sections.append(sec)

    docs_text = "\n\n".join(doc_sections)

    prompt = (
        "You are DecisionFlow AI, an impartial decision-comparison intelligence engine. "
        "Analyze the following 2 or 3 official documents/options side by side.\n\n"
        "Your task is to identify:\n"
        "1. Common information across options (shared requirements, shared goals, or shared procedures).\n"
        "2. Key differences between options (differing deadlines, priorities, document counts, eligibility, conditions).\n"
        "3. Conflicting information (contradictory requirements, opposing instructions, or materially inconsistent criteria). "
        "If there are no actual contradictions, you MUST return [\"No conflicting information detected.\"].\n"
        "4. Important conditions (restrictions, GPA/age rules, verification instructions, or submission prerequisites).\n"
        "5. Missing information (any missing deadlines, missing requirements, or unstated eligibility in any option).\n"
        "6. Eligibility per option (concise summary of eligibility criteria for each option, e.g. 'Option A': '...', or 'Not available').\n"
        "7. Decision Summary: 3-5 concise, action-oriented factual findings (e.g., 'Option A has an earlier deadline.', 'Option B requires one additional document.', 'Both options require a valid ID.').\n\n"
        "CRITICAL RULES:\n"
        "- Do NOT choose a winner.\n"
        "- Do NOT declare which option is 'better', 'best', or 'recommended'.\n"
        "- Do NOT tell the user which option to pick. Final decision belongs to the user.\n"
        "- Return ONLY strictly factual and action-oriented statements.\n"
        "- Return ONLY valid JSON. Double quotes for keys and strings. No markdown fences. No preamble.\n\n"
        "Required JSON structure:\n"
        "{\n"
        '  "eligibility_per_option": {\n'
        '    "Option A": "Eligibility summary or Not available",\n'
        '    "Option B": "Eligibility summary or Not available"\n'
        "  },\n"
        '  "important_conditions_per_option": {\n'
        '    "Option A": ["Condition 1", "Condition 2"],\n'
        '    "Option B": ["Condition 1"]\n'
        "  },\n"
        '  "common_information": [\n'
        '    "Factual common point 1",\n'
        '    "Factual common point 2"\n'
        "  ],\n"
        '  "differences": [\n'
        '    "Factual difference 1",\n'
        '    "Factual difference 2"\n'
        "  ],\n"
        '  "conflicts": [\n'
        '    "No conflicting information detected."\n'
        "  ],\n"
        '  "important_conditions": [\n'
        '    "Condition 1",\n'
        '    "Condition 2"\n'
        "  ],\n"
        '  "missing_information": [\n'
        '    "Missing info point or No important information appears to be missing from the selected records."\n'
        "  ],\n"
        '  "decision_summary": [\n'
        '    "Option A has an earlier deadline.",\n'
        '    "Option B requires one additional document.",\n'
        '    "Both options require a valid ID."\n'
        "  ]\n"
        "}\n\n"
        f"DOCUMENTS TO COMPARE:\n{docs_text}"
    )

    try:
        raw_resp = execute_cortex_prompt(prompt)
        return extract_json_from_cortex(raw_resp)
    except Exception as exc:
        logger.warning("Cortex semantic comparison failed or unavailable: %s", exc)
        return {}


def _sanitize_summary_item(text: str) -> Optional[str]:
    """
    Enforces strict neutrality by removing or sanitizing non-factual or biased recommendations.
    """
    if not text or not str(text).strip():
        return None
    cleaned = str(text).strip()
    lower = cleaned.lower()
    forbidden = [
        "is better", "is the best", "we recommend", "recommended option",
        "winner", "should choose", "should select option", "superior choice",
        "preferred choice", "you should choose", "you should pick",
    ]
    for f in forbidden:
        if f in lower:
            return None
    return cleaned


def build_decision_comparison(
    documents: List[Dict[str, Any]],
    cortex_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synthesizes deterministic parameters (deadlines, priorities, document sets)
    with Cortex AI semantic findings into a comprehensive comparison result.
    Strictly neutral; never declares a winner.
    """
    cortex = cortex_data or {}
    option_letters = ["Option A", "Option B", "Option C"]
    num_docs = len(documents)

    # 1. Build OptionDetail profiles
    eligibility_map = cortex.get("eligibility_per_option") or {}
    conditions_map = cortex.get("important_conditions_per_option") or {}

    options_list = []
    for idx, doc in enumerate(documents):
        label = option_letters[idx] if idx < len(option_letters) else f"Option {idx + 1}"
        elig = eligibility_map.get(label)
        if not elig or elig.lower() in ("null", "none", "not available", "unknown", "n/a"):
            elig = "Not available"

        conds = conditions_map.get(label) or []
        if isinstance(conds, str):
            conds = [conds]

        options_list.append({
            "id": doc["id"],
            "title": doc["title"],
            "category": doc["category"],
            "summary": doc["summary"],
            "deadline": doc.get("deadline"),
            "priority": doc.get("priority", "Medium"),
            "actions": doc.get("actions", []),
            "required_documents": doc.get("required_documents", []),
            "eligibility": elig,
            "important_conditions": [str(c).strip() for c in conds if c],
        })

    # 2. Deadline Comparison
    different_deadlines: List[str] = []
    parsed_dates = []
    for idx, doc in enumerate(documents):
        label = option_letters[idx]
        p_date = parse_deadline_date(doc.get("deadline"))
        parsed_dates.append((label, doc["title"], p_date, doc.get("deadline")))
        d_display = format_deadline_display(doc.get("deadline"))
        if d_display:
            different_deadlines.append(f"{label} ({doc['title']}): {d_display}")
        else:
            different_deadlines.append(f"{label} ({doc['title']}): Deadline not available")

    # Chronological / sequence relationship
    dates_with_vals = [(lbl, title, pdate) for lbl, title, pdate, _ in parsed_dates if pdate is not None]
    if len(dates_with_vals) >= 2:
        dates_sorted = sorted(dates_with_vals, key=lambda x: x[2])
        if num_docs == 2:
            d1, d2 = dates_with_vals[0], dates_with_vals[1]
            if d1[2] < d2[2]:
                diff_days = (d2[2] - d1[2]).days
                different_deadlines.append(
                    f"{d1[0]} has an earlier deadline than {d2[0]} (by {diff_days} day{'s' if diff_days != 1 else ''})."
                )
            elif d2[2] < d1[2]:
                diff_days = (d1[2] - d2[2]).days
                different_deadlines.append(
                    f"{d2[0]} has an earlier deadline than {d1[0]} (by {diff_days} day{'s' if diff_days != 1 else ''})."
                )
            else:
                different_deadlines.append(f"Both {d1[0]} and {d2[0]} share the same deadline ({d1[2].strftime('%d %b %Y')}).")
        else:
            # 3 documents
            seq_str = " -> ".join([f"{item[0]} ({item[2].strftime('%d %b %Y')})" for item in dates_sorted])
            different_deadlines.append(f"Chronological order: {seq_str}")
    elif len(dates_with_vals) == 1 and num_docs > 1:
        has_date = dates_with_vals[0]
        missing_labels = [lbl for lbl, _, pdate, _ in parsed_dates if pdate is None]
        different_deadlines.append(
            f"Only {has_date[0]} has a confirmed deadline ({has_date[2].strftime('%d %b %Y')}); deadline is not available for {', '.join(missing_labels)}."
        )
    elif len(dates_with_vals) == 0:
        different_deadlines.append("None of the selected options specify a deadline.")

    # 3. Requirements Comparison (Common vs Per-Option)
    req_sets = {}
    normalized_map = {}
    for idx, doc in enumerate(documents):
        label = option_letters[idx]
        reqs = doc.get("required_documents") or []
        req_sets[label] = set()
        for r in reqs:
            cleaned = str(r).strip()
            if cleaned:
                key = cleaned.lower()
                normalized_map[key] = cleaned
                req_sets[label].add(key)

    # Find common requirements across all
    all_keys = list(req_sets.values())
    if all_keys and all(len(s) > 0 for s in all_keys):
        common_keys = set.intersection(*all_keys)
    else:
        common_keys = set()
    common_req_items = [normalized_map[k] for k in sorted(common_keys)]

    per_option_reqs = {}
    for label, keys in req_sets.items():
        exclusive_keys = keys - common_keys
        per_option_reqs[label] = [normalized_map[k] for k in sorted(exclusive_keys)]

    different_requirements = {
        "common": common_req_items,
        "per_option": per_option_reqs,
    }

    # 4. Common Information
    common_information: List[str] = []
    # Add Cortex common items if present
    cortex_commons = cortex.get("common_information") or []
    for c in cortex_commons:
        if isinstance(c, str) and c.strip():
            common_information.append(c.strip())

    # Augment with deterministic commonalities
    if common_req_items:
        common_req_str = f"All selected options require: {', '.join(common_req_items)}."
        if common_req_str not in common_information:
            common_information.append(common_req_str)

    # Check shared categories
    categories = [d.get("category") for d in documents if d.get("category")]
    if len(categories) == num_docs and len(set(categories)) == 1:
        cat_note = f"All options fall under the '{categories[0]}' category."
        if cat_note not in common_information:
            common_information.append(cat_note)

    # Check shared priorities
    priorities = [d.get("priority") for d in documents if d.get("priority")]
    if len(priorities) == num_docs and len(set(priorities)) == 1:
        prio_note = f"All options share a '{priorities[0]}' priority level."
        if prio_note not in common_information:
            common_information.append(prio_note)

    if not common_information:
        common_information = ["No significant common information was identified across the selected records."]

    # 5. Key Differences
    differences: List[str] = []
    cortex_diffs = cortex.get("differences") or []
    for d in cortex_diffs:
        if isinstance(d, str) and d.strip():
            differences.append(d.strip())

    # Add deterministic deadline difference
    if len(dates_with_vals) >= 2:
        d1, d2 = dates_with_vals[0], dates_with_vals[1]
        if d1[2] != d2[2]:
            dd_note = f"{d1[0]} deadline is {d1[2].strftime('%d %b %Y')}, whereas {d2[0]} deadline is {d2[2].strftime('%d %b %Y')}."
            if not any("deadline" in x.lower() and d1[0] in x for x in differences):
                differences.append(dd_note)

    # Add deterministic priority difference
    if len(set(priorities)) > 1:
        prio_parts = [f"{option_letters[i]} is {doc.get('priority', 'Medium')}" for i, doc in enumerate(documents)]
        prio_diff_note = f"Different priority ratings: {', '.join(prio_parts)}."
        if not any("priority" in x.lower() for x in differences):
            differences.append(prio_diff_note)

    # Add deterministic requirement count difference
    req_counts = [len(doc.get("required_documents") or []) for doc in documents]
    if len(set(req_counts)) > 1:
        if num_docs == 2:
            cnt_diff = abs(req_counts[0] - req_counts[1])
            more_opt = option_letters[0] if req_counts[0] > req_counts[1] else option_letters[1]
            diff_req_note = f"{more_opt} requires {cnt_diff} additional document{'s' if cnt_diff != 1 else ''}."
            if not any("additional document" in x.lower() for x in differences):
                differences.append(diff_req_note)

    if not differences:
        differences = ["The selected options share largely similar parameters."]

    # 6. Conflicting Information
    conflicts: List[str] = []
    cortex_conflicts = cortex.get("conflicts") or []
    for cf in cortex_conflicts:
        if isinstance(cf, str) and cf.strip():
            cf_clean = cf.strip()
            if cf_clean.lower() not in ("none", "no conflicts", "no conflict"):
                conflicts.append(cf_clean)

    if not conflicts or (len(conflicts) == 1 and "no conflicting information" in conflicts[0].lower()):
        conflicts = ["No conflicting information detected."]

    # 7. Missing Information
    missing_info: List[str] = []
    cortex_missing = cortex.get("missing_information") or []
    for m in cortex_missing:
        if isinstance(m, str) and m.strip():
            m_clean = m.strip()
            if m_clean.lower() not in ("none", "no missing information", "nothing missing", "n/a"):
                missing_info.append(m_clean)

    # Add deterministic missing checks
    for idx, doc in enumerate(documents):
        label = option_letters[idx]
        if not doc.get("deadline"):
            miss_dl = f"Deadline information is not available for {label} ({doc['title']})."
            if not any(f"deadline" in x.lower() and label in x for x in missing_info):
                missing_info.append(miss_dl)
        if not doc.get("required_documents"):
            miss_doc = f"No specific required documents are listed for {label} ({doc['title']})."
            if not any(f"document" in x.lower() and label in x for x in missing_info):
                missing_info.append(miss_doc)

    if not missing_info or (len(missing_info) == 1 and "no important information appears to be missing" in missing_info[0].lower()):
        missing_info = ["No important information appears to be missing from the selected records."]

    # 8. Important Conditions
    important_conditions: List[str] = []
    cortex_conditions = cortex.get("important_conditions") or []
    for ic in cortex_conditions:
        if isinstance(ic, str) and ic.strip():
            important_conditions.append(ic.strip())

    if not important_conditions:
        # Fallback to option conditions
        for opt in options_list:
            for c in opt.get("important_conditions", []):
                important_conditions.append(f"{opt['title']}: {c}")

    if not important_conditions:
        important_conditions = ["No special submission or eligibility restrictions noted."]

    # 9. Decision Summary (Key facts to consider)
    decision_summary: List[str] = []
    cortex_summary = cortex.get("decision_summary") or []
    for item in cortex_summary:
        sanitized = _sanitize_summary_item(item)
        if sanitized and sanitized not in decision_summary:
            decision_summary.append(sanitized)

    # Ensure deterministic deadline fact is included if not present
    if len(dates_with_vals) >= 2:
        d1, d2 = dates_with_vals[0], dates_with_vals[1]
        if d1[2] < d2[2]:
            dl_fact = f"{d1[0]} has an earlier deadline ({d1[2].strftime('%d %b %Y')} vs {d2[2].strftime('%d %b %Y')})."
            if not any("earlier deadline" in s.lower() for s in decision_summary):
                decision_summary.insert(0, dl_fact)
        elif d2[2] < d1[2]:
            dl_fact = f"{d2[0]} has an earlier deadline ({d2[2].strftime('%d %b %Y')} vs {d1[2].strftime('%d %b %Y')})."
            if not any("earlier deadline" in s.lower() for s in decision_summary):
                decision_summary.insert(0, dl_fact)

    # Ensure common requirements fact is included
    if common_req_items:
        common_fact = f"All options require: {', '.join(common_req_items)}."
        if not any("all options require" in s.lower() or "both options require" in s.lower() for s in decision_summary):
            decision_summary.append(common_fact)

    # Ensure requirement difference fact is included
    if len(set(req_counts)) > 1 and num_docs == 2:
        diff_n = abs(req_counts[0] - req_counts[1])
        more_lbl = option_letters[0] if req_counts[0] > req_counts[1] else option_letters[1]
        req_fact = f"{more_lbl} requires {diff_n} additional document{'s' if diff_n != 1 else ''}."
        if not any("additional document" in s.lower() for s in decision_summary):
            decision_summary.append(req_fact)

    # Check for missing eligibility warning
    for opt in options_list:
        if opt["eligibility"] == "Not available":
            miss_elig = f"Check eligibility criteria for {opt['title']} before applying (not specified in record)."
            if not any("eligibility" in s.lower() and opt['title'] in s for s in decision_summary):
                decision_summary.append(miss_elig)

    # Sanitize again
    final_summary = []
    for item in decision_summary:
        s = _sanitize_summary_item(item)
        if s and s not in final_summary:
            final_summary.append(s)

    if not final_summary:
        final_summary = [
            f"Review deadline differences carefully across all {num_docs} options.",
            "Verify all required documents are prepared prior to submission.",
            "Confirm eligibility conditions with the respective issuing authority.",
        ]

    return {
        "options": options_list,
        "common_information": common_information,
        "differences": differences,
        "conflicts": conflicts,
        "different_deadlines": different_deadlines,
        "different_requirements": different_requirements,
        "missing_information": missing_info,
        "important_conditions": important_conditions,
        "decision_summary": final_summary,
    }


def compare_documents_pipeline(
    document_ids: List[int],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full Decision Compare pipeline:
    1. Verifies document count (2 to 3).
    2. Validates session ownership and fetches structured records from DOCUMENTS.
    3. Executes Snowflake Cortex AI comparison for semantic insights (if configured).
    4. Computes deterministic timeline and requirements comparisons.
    5. Returns structured comparison result.
    """
    if len(document_ids) < 2:
        raise ValueError("At least 2 documents are required for comparison.")
    if len(document_ids) > 3:
        raise ValueError("A maximum of 3 documents can be compared at once.")

    if not session_id or not str(session_id).strip():
        raise ValueError("A valid session ID is required to compare documents.")

    docs = get_documents_by_ids(document_ids, session_id=session_id)
    if len(docs) != len(document_ids):
        found_ids = {d["id"] for d in docs}
        missing_ids = [did for did in document_ids if did not in found_ids]
        logger.warning(
            "Comparison failed: session %s does not own or could not find documents %s",
            session_id, missing_ids,
        )
        raise ValueError(f"One or more documents ({missing_ids}) not found or do not belong to current session.")

    cortex_data = {}
    if SnowflakeConfig.is_configured():
        try:
            cortex_data = run_cortex_compare(docs)
        except Exception as exc:
            logger.warning("Cortex comparison call failed; falling back to deterministic comparison: %s", exc)

    return build_decision_comparison(docs, cortex_data=cortex_data)





# ── Deadline Center ──────────────────────────────────────────────────────────

def ensure_completed_column(conn, table_name: str) -> bool:
    """
    Ensures the COMPLETED BOOLEAN DEFAULT FALSE column exists in the DOCUMENTS table.
    Lazy migration — runs once on first Deadline Center access.
    """
    try:
        existing = inspect_table_columns(conn, table_name)
        if "COMPLETED" in existing:
            return False
        with conn.cursor() as cur:
            cur.execute(
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS COMPLETED BOOLEAN DEFAULT FALSE"
            )
            conn.commit()
            logger.info("Added COMPLETED column to %s.", table_name)
        return True
    except Exception as exc:
        logger.warning("Could not ensure COMPLETED column on %s: %s", table_name, exc)
        return False


def _compute_deadline_status(deadline_val: Any, completed: bool, today) -> tuple:
    """
    Computes (status, days_remaining). Completed takes precedence over date categories.
    Returns (None, None) when deadline is absent and not completed.
    """
    parsed = parse_deadline_date(deadline_val)
    if completed:
        days = (parsed - today).days if parsed else None
        return "Completed", days
    if parsed is None:
        return None, None
    days = (parsed - today).days
    if days < 0:
        return "Overdue", days
    elif days <= 7:
        return "Due Soon", days
    else:
        return "Upcoming", days


def get_deadline_items(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves ALL documents for the session and computes Deadline Center status.
    Documents without a deadline are excluded unless completed.
    """
    if not session_id or not str(session_id).strip():
        logger.info("get_deadline_items: no session_id — empty list.")
        return []

    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()
    ensure_completed_column(conn, table_name)
    col_meta = inspect_table_columns(conn, table_name)
    has_completed_col = "COMPLETED" in col_meta

    if has_completed_col:
        query = (
            f"SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, "
            f"ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT, COMPLETED "
            f"FROM {table_name} WHERE SESSION_ID = %s "
            f"ORDER BY CASE WHEN DEADLINE IS NULL THEN 1 ELSE 0 END ASC, "
            f"DEADLINE ASC, CREATED_AT DESC"
        )
    else:
        query = (
            f"SELECT ID, TITLE, CATEGORY, SUMMARY, DEADLINE, PRIORITY, "
            f"ACTIONS, REQUIRED_DOCUMENTS, CREATED_AT, FALSE AS COMPLETED "
            f"FROM {table_name} WHERE SESSION_ID = %s "
            f"ORDER BY CASE WHEN DEADLINE IS NULL THEN 1 ELSE 0 END ASC, "
            f"DEADLINE ASC, CREATED_AT DESC"
        )

    kolkata_tz = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(kolkata_tz).date()

    try:
        with conn.cursor() as cur:
            cur.execute(query, (str(session_id).strip(),))
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for row in rows:
        (doc_id, title, category, summary, deadline, priority,
         actions_raw, req_docs_raw, created_at, completed_raw) = row

        parsed_actions: List[str] = []
        if actions_raw:
            if isinstance(actions_raw, list):
                parsed_actions = [str(a).strip() for a in actions_raw if a]
            elif isinstance(actions_raw, str):
                try:
                    loaded = json.loads(actions_raw)
                    if isinstance(loaded, list):
                        parsed_actions = [str(a).strip() for a in loaded if a]
                    else:
                        parsed_actions = [str(loaded).strip()]
                except Exception:
                    parsed_actions = [actions_raw.strip()]

        deadline_str: Optional[str] = None
        if deadline:
            if hasattr(deadline, "isoformat"):
                deadline_str = deadline.isoformat()
            else:
                s = str(deadline).strip()
                deadline_str = s if s and s.lower() not in ("null", "none", "n/a") else None

        created_str: Optional[str] = None
        if created_at:
            if hasattr(created_at, "isoformat"):
                created_str = created_at.isoformat()
            else:
                created_str = str(created_at).strip()

        completed = bool(completed_raw) if completed_raw is not None else False
        status, days_remaining = _compute_deadline_status(deadline_str, completed, today)

        if status is None:
            continue

        required_action = parsed_actions[0] if parsed_actions else "Action not specified"

        results.append({
            "document_id": int(doc_id),
            "task": str(title or "Untitled Document").strip(),
            "source_document": str(title or "Untitled Document").strip(),
            "category": str(category or "General").strip(),
            "deadline": deadline_str,
            "days_remaining": days_remaining,
            "priority": str(priority or "Medium").strip().capitalize(),
            "required_action": required_action,
            "actions": parsed_actions,
            "status": status,
            "completed": completed,
            "created_at": created_str,
        })

    return results


def update_deadline_completion(
    document_id: int,
    completed: bool,
    session_id: Optional[str] = None,
) -> bool:
    """
    Persists COMPLETED state for a document with session ownership validation.
    Returns True if updated, False if not found / not owned.
    """
    if not session_id or not str(session_id).strip():
        raise ValueError("A valid session ID is required to update completion state.")

    conn = get_snowflake_connection()
    table_name = SnowflakeConfig.documents_table()
    ensure_completed_column(conn, table_name)

    query = f"UPDATE {table_name} SET COMPLETED = %s WHERE ID = %s AND SESSION_ID = %s"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (completed, document_id, str(session_id).strip()))
            affected = cur.rowcount
            conn.commit()
            logger.info(
                "update_deadline_completion doc=%d completed=%s session=%s affected=%d",
                document_id, completed, session_id, affected,
            )
            return affected > 0
    finally:
        conn.close()
