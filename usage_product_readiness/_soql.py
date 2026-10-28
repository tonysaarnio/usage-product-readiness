"""Thin wrappers around the Salesforce CLI (`sf`) for read-only queries.

Everything here is read-only: `sf data query` and `sf sobject describe`. No DML is
ever issued by this tool.
"""

from __future__ import annotations

import json
import subprocess
import sys
from shutil import which
from typing import Any


def _sf_exe() -> str:
    exe = which("sf") or which("sf.cmd")
    if not exe:
        print("ERROR: Salesforce CLI (`sf`) not found on PATH.", file=sys.stderr)
        raise SystemExit(2)
    return exe


def soql_literal(value: str) -> str:
    r"""Escape a string for use inside a single-quoted SOQL literal.

    Prevents a value such as an apostrophe in a ProductCode (``O'Brien Ltd``) from
    breaking the query or being used for injection. Backslash first, then quote.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def run_soql(org: str, soql: str) -> list[dict[str, Any]]:
    """Run a SOQL query via ``sf data query --json`` and return its records.

    Exits the process with code 2 on any CLI error, echoing the failing query so
    the problem is diagnosable.
    """
    proc = subprocess.run(
        [_sf_exe(), "data", "query", "--json", "--target-org", org, "-q", soql],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print("ERROR: SOQL query failed.", file=sys.stderr)
        print(f"Query: {soql}", file=sys.stderr)
        message = proc.stderr.strip() or proc.stdout.strip()
        if message:
            print(message, file=sys.stderr)
        raise SystemExit(2)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("ERROR: could not parse `sf data query` JSON output.", file=sys.stderr)
        raise SystemExit(2)
    return payload.get("result", {}).get("records", [])


def describe_picklist(org: str, sobject: str, field: str) -> list[str]:
    """Active picklist values for ``sobject.field``, or ``[]`` if unavailable.

    Used to discover ``Product2.UsageModelType`` from the live org rather than
    hardcoding it. A describe failure is non-fatal — the caller falls back to the
    documented static set in :mod:`usage_product_readiness.models`.
    """
    proc = subprocess.run(
        [_sf_exe(), "sobject", "describe", "--sobject", sobject, "--target-org", org, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    try:
        fields = json.loads(proc.stdout)["result"]["fields"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    for f in fields:
        if f.get("name") == field:
            return [
                v["value"]
                for v in f.get("picklistValues", [])
                if v.get("active", True) and v.get("value")
            ]
    return []
