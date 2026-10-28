"""Argument parsing and dispatch for the `usage-readiness` command."""

from __future__ import annotations

import argparse

from . import __version__
from . import product as product_cmd
from . import scan as scan_cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="usage-readiness",
        description="Readiness checks for Revenue Cloud usage products "
        "(Manage Usage Resources / STLT).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("product", help="Check a single usage product (and optionally a quote line).")
    p.add_argument("--org", required=True, help="SF alias/username, e.g. rlm-prod")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--product-id", help="Product2 Id (01t...)")
    group.add_argument("--product-code", help="Product2.ProductCode")
    p.add_argument("--quote-id", help="Optional Quote Id; checks the newest line in the quote")
    p.add_argument("--quote-line-id", help="Optional QuoteLineItem Id to run quote-line checks")
    p.set_defaults(func=product_cmd.run)

    s = sub.add_parser("scan", help="Scan many usage products in an org for readiness.")
    s.add_argument("--org", required=True, help="SF alias/username, e.g. rlm-prod")
    s.add_argument(
        "--usage-model-types",
        default=None,
        help="Comma-separated UsageModelType list (default: discover from the org, "
        "falling back to Anchor,Pack,Commit,CommitmentQuantity,CommitmentSpend)",
    )
    s.add_argument("--active-only", action="store_true", help="Scan only active products")
    s.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Exit 1 when any scanned product is not ready",
    )
    s.set_defaults(func=scan_cmd.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
