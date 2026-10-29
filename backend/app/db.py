"""SQLite database layer and query helpers for Agent Wallet."""

import sqlite3
import uuid
from typing import Generator, Optional, List, Dict, Any, Union
from datetime import datetime

from app.config import DATABASE_PATH
from app.models import Payment, Decision


def get_db_connection() -> sqlite3.Connection:
    """Create and return an SQLite connection configured with Row factory and WAL mode."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency for yielding database connections."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables for requests, settings, and vendors with default seeds."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: requests - audit trail for all incoming agent payment requests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            vendor TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            recipient_email TEXT,
            reason TEXT NOT NULL,
            vendor_description TEXT,
            status TEXT NOT NULL,
            decision_reason TEXT,
            risk_score REAL DEFAULT 0.0,
            evaluated_by TEXT DEFAULT 'policy_engine',
            paypal_payout_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Table 2: settings - dynamic policy limits, thresholds, and toggles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Table 3: vendors - registry of allowed, flagged, and blocked recipients
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            category TEXT,
            trust_score REAL DEFAULT 1.0,
            status TEXT DEFAULT 'allowed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed initial default settings if missing
    default_settings = [
        ("max_single_spend_usd", "50.00", "Maximum single transaction cap in USD"),
        ("daily_agent_budget_usd", "200.00", "Daily 24h rolling budget limit per agent in USD"),
        ("escalation_threshold_usd", "35.00", "Transactions above this amount require supervisor review"),
        ("auto_payout_enabled", "false", "Whether approved payments trigger PayPal Sandbox payout automatically"),
        ("groq_model", "llama-3.3-70b-versatile", "Groq LLM model used for policy evaluation"),
    ]
    cursor.executemany("""
        INSERT OR IGNORE INTO settings (key, value, description)
        VALUES (?, ?, ?);
    """, default_settings)

    # Seed known trusted and blocked vendor examples
    default_vendors = [
        (str(uuid.uuid4()), "Tavily Search API", "Search / AI Tooling", 0.95, "allowed"),
        (str(uuid.uuid4()), "OpenAI API", "LLM Inference", 0.98, "allowed"),
        (str(uuid.uuid4()), "Anthropic API", "LLM Inference", 0.98, "allowed"),
        (str(uuid.uuid4()), "GitHub", "Developer Tools", 0.95, "allowed"),
        (str(uuid.uuid4()), "HuggingFace", "AI Models / Compute", 0.92, "allowed"),
        (str(uuid.uuid4()), "Suspicious Offshore Node", "Unverified Proxy", 0.10, "blocked"),
        (str(uuid.uuid4()), "Bypass Gateway Ltd", "High Risk / Fraud", 0.05, "blocked"),
    ]
    cursor.executemany("""
        INSERT OR IGNORE INTO vendors (id, name, category, trust_score, status)
        VALUES (?, ?, ?, ?, ?);
    """, default_vendors)

    conn.commit()
    conn.close()


# ==============================================================================
# Payment Request CRUD & Audit Helpers
# ==============================================================================

def log_payment_request(
    payment: Payment,
    decision: Decision,
    request_id: Optional[str] = None
) -> str:
    """Insert an incoming payment request along with its decision into the audit log."""
    rid = request_id or decision.request_id or str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO requests (
            id, agent_id, vendor, amount, currency, recipient_email,
            reason, vendor_description, status, decision_reason,
            risk_score, evaluated_by, paypal_payout_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
    """, (
        rid,
        str(payment.agent_id),
        payment.vendor,
        payment.amount,
        payment.currency,
        payment.recipient_email,
        payment.reason,
        payment.vendor_description,
        decision.status,
        decision.reason,
        decision.risk_score or 0.0,
        decision.evaluated_by or "policy_engine",
        decision.payout_id
    ))

    conn.commit()
    conn.close()
    return rid


def update_request_status(
    request_id: str,
    status: str,
    decision_reason: Optional[str] = None,
    payout_id: Optional[str] = None,
    evaluated_by: Optional[str] = None
) -> bool:
    """Update status, rationale, and payout info for a specific request (e.g. after supervisor approval)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: List[Any] = [status]

    if decision_reason is not None:
        fields.append("decision_reason = ?")
        params.append(decision_reason)

    if payout_id is not None:
        fields.append("paypal_payout_id = ?")
        params.append(payout_id)

    if evaluated_by is not None:
        fields.append("evaluated_by = ?")
        params.append(evaluated_by)

    params.append(request_id)
    query = f"UPDATE requests SET {', '.join(fields)} WHERE id = ?;"

    cursor.execute(query, params)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_request_by_id(request_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full details of a specific payment request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE id = ?;", (request_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_activity(
    limit: int = 50,
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve recent payment request transactions ordered by newest first."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if status_filter:
        cursor.execute(
            "SELECT * FROM requests WHERE status = ? ORDER BY created_at DESC LIMIT ?;",
            (status_filter, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM requests ORDER BY created_at DESC LIMIT ?;",
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_agent_rolling_24h_spend(agent_id: Union[str, int]) -> float:
    """Calculate the total approved/disbursed amount spent by an agent in the last 24 hours."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0.0) AS total_spend
        FROM requests
        WHERE agent_id = ?
          AND status IN ('approve', 'disbursed')
          AND datetime(created_at) >= datetime('now', '-24 hours');
    """, (str(agent_id),))

    result = cursor.fetchone()
    conn.close()
    return float(result["total_spend"]) if result else 0.0


# ==============================================================================
# Settings Management Helpers
# ==============================================================================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve the string value of a setting from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def get_all_settings() -> Dict[str, Dict[str, str]]:
    """Retrieve all configurable settings and their descriptions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, description, updated_at FROM settings;")
    rows = cursor.fetchall()
    conn.close()
    return {
        row["key"]: {
            "value": row["value"],
            "description": row["description"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    }


def update_setting(key: str, value: str) -> bool:
    """Update a specific setting value."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE settings
        SET value = ?, updated_at = CURRENT_TIMESTAMP
        WHERE key = ?;
    """, (value, key))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# ==============================================================================
# Vendor Whitelist / Blacklist Helpers
# ==============================================================================

def get_vendor(name: str) -> Optional[Dict[str, Any]]:
    """Look up a vendor by name (case-insensitive)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vendors WHERE name = ? COLLATE NOCASE;", (name.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_vendors() -> List[Dict[str, Any]]:
    """List all registered vendors with their trust ratings and status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vendors ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def upsert_vendor(
    name: str,
    category: Optional[str] = None,
    trust_score: float = 1.0,
    status: str = "allowed"
) -> Dict[str, Any]:
    """Insert or update a vendor record."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO vendors (id, name, category, trust_score, status, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name) DO UPDATE SET
            category = COALESCE(excluded.category, vendors.category),
            trust_score = excluded.trust_score,
            status = excluded.status;
    """, (str(uuid.uuid4()), name.strip(), category, trust_score, status))

    conn.commit()
    cursor.execute("SELECT * FROM vendors WHERE name = ? COLLATE NOCASE;", (name.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


# ==============================================================================
# Dashboard Metrics Helpers
# ==============================================================================

def get_dashboard_stats() -> Dict[str, Any]:
    """Calculate aggregate statistics for display on the dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status IN ('approve', 'disbursed') THEN amount ELSE 0 END), 0.0) AS total_processed,
            COUNT(*) AS total_requests,
            COALESCE(SUM(CASE WHEN status IN ('approve', 'disbursed') THEN 1 ELSE 0 END), 0) AS approved_count,
            COALESCE(SUM(CASE WHEN status = 'deny' THEN 1 ELSE 0 END), 0) AS denied_count,
            COALESCE(SUM(CASE WHEN status = 'escalate' THEN 1 ELSE 0 END), 0) AS escalated_count
        FROM requests;
    """)
    stats_row = cursor.fetchone()

    cursor.execute("SELECT value FROM settings WHERE key = 'auto_payout_enabled';")
    auto_payout_row = cursor.fetchone()
    auto_payout = auto_payout_row["value"].lower() == "true" if auto_payout_row else False

    conn.close()

    return {
        "total_processed_usd": float(stats_row["total_processed"]) if stats_row else 0.0,
        "total_requests": int(stats_row["total_requests"]) if stats_row else 0,
        "approved_count": int(stats_row["approved_count"]) if stats_row else 0,
        "denied_count": int(stats_row["denied_count"]) if stats_row else 0,
        "escalated_count": int(stats_row["escalated_count"]) if stats_row else 0,
        "auto_payout_enabled": auto_payout,
    }
