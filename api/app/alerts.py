"""Helpers for inserting rows into the ``alerts`` table.

Called from the eval / pipeline / search code when something notable
happens. The dashboard's "System Status & Alerts" panel reads from
this table.

Failures here are non-fatal -- if the alert insert errors, the caller
should still continue. We log and swallow.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from app import db
from app.logging import get_logger


log = get_logger(__name__)

Severity = Literal["info", "warning", "error"]


async def emit_alert(
    *,
    severity: Severity,
    title:    str,
    body:     str | None = None,
    source:   str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort insert into ``alerts``."""
    try:
        async with db.get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO alerts (severity, title, body, source, metadata)
                VALUES ($1::alert_severity, $2, $3, $4, $5::jsonb)
                """,
                severity, title, body, source, json.dumps(metadata or {}),
            )
    except Exception as exc:
        log.warning("alerts.insert_failed", error=str(exc), title=title)
