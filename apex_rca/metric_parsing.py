"""Parse service names from RCAEval metric column names."""

from __future__ import annotations

import re

import pandas as pd

from apex_rca.config import METRIC_SUFFIXES, SERVICE_ALIASES

SUFFIX_PATTERN = re.compile(
    r"^(.+)_(" + "|".join(map(re.escape, METRIC_SUFFIXES)) + r")$"
)


def parse_service_metric(column: str) -> tuple[str, str] | None:
    """Return (service, metric_suffix) if the column follows the benchmark naming."""
    match = SUFFIX_PATTERN.match(str(column))
    if not match:
        return None
    return match.group(1), match.group(2)


def service_metric_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    """Map service names to their numeric telemetry columns.

    Longest suffixes are matched first so ``latency-50`` is not split as
    ``latency`` with a leftover ``-50``.
    """
    mapping: dict[str, list[str]] = {}
    for col in df.columns:
        parsed = parse_service_metric(str(col))
        if not parsed:
            continue
        service, _suffix = parsed
        if pd.api.types.is_numeric_dtype(df[col]):
            mapping.setdefault(service, []).append(str(col))
    return mapping


def normalize_service_name(name: str | None) -> str:
    """Align trace/log service names with metric prefixes where aliases exist."""
    if name is None:
        return ""
    raw = str(name).strip()
    key = raw.lower()
    return SERVICE_ALIASES.get(key, raw)
