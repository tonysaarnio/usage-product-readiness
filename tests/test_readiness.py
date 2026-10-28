"""Offline unit tests — no org required.

Run from the repo root with:  python -m unittest discover -s tests
"""

import unittest

from usage_product_readiness._soql import soql_literal
from usage_product_readiness.cli import build_parser
from usage_product_readiness.models import (
    COMMITMENT_USAGE_MODELS,
    GUIDED_USAGE_MODELS,
    USAGE_MODEL_TYPES,
)
from usage_product_readiness.readiness import evaluate_product


def _ready_rows():
    return dict(
        pur_rows=[{"Id": "pur1", "Status": "Active"}],
        purp_rows=[{"ProductUsageResourceId": "pur1"}],
        pug_rows=[{"Id": "pug1", "Status": "Active", "UsageDefinitionProductId": "def1"}],
        binding_rows=[{"Id": "b1"}],
        usage_def_active={"def1": True},
    )


class ModelTypeTests(unittest.TestCase):
    def test_picklist_is_exactly_the_real_values(self):
        self.assertEqual(
            set(USAGE_MODEL_TYPES),
            {"Anchor", "Pack", "Commit", "CommitmentQuantity", "CommitmentSpend"},
        )

    def test_bogus_token_values_absent(self):
        self.assertNotIn("Token", USAGE_MODEL_TYPES)
        self.assertNotIn("CommitmentToken", USAGE_MODEL_TYPES)

    def test_commit_is_a_commitment_model(self):
        self.assertIn("Commit", COMMITMENT_USAGE_MODELS)

    def test_commit_participates_in_guided_flow(self):
        self.assertIn("Commit", GUIDED_USAGE_MODELS)


class EvaluateTests(unittest.TestCase):
    def test_anchor_fully_configured_is_ready(self):
        p = {"Id": "01t", "IsActive": True, "UsageModelType": "Anchor"}
        self.assertTrue(evaluate_product(p, **_ready_rows()).is_ready)

    def test_anchor_missing_binding_is_not_ready(self):
        p = {"Id": "01t", "IsActive": True, "UsageModelType": "Anchor"}
        rows = _ready_rows()
        rows["binding_rows"] = []
        r = evaluate_product(p, **rows)
        self.assertFalse(r.is_ready)
        self.assertIn("missing UsagePrdGrantBindingPolicy", r.reasons())

    def test_commit_without_binding_is_ready(self):
        # The core fix: a Commit product needs no binding policy and is a valid model.
        p = {"Id": "01t", "IsActive": True, "UsageModelType": "Commit"}
        rows = _ready_rows()
        rows["binding_rows"] = []
        r = evaluate_product(p, **rows)
        self.assertTrue(r.is_ready, r.reasons())
        self.assertTrue(all("unknown UsageModelType" not in x for x in r.reasons()))

    def test_inactive_grant_definition_blocks(self):
        p = {"Id": "01t", "IsActive": True, "UsageModelType": "Anchor"}
        rows = _ready_rows()
        rows["usage_def_active"] = {"def1": False}
        self.assertFalse(evaluate_product(p, **rows).is_ready)

    def test_missing_resource_is_not_ready(self):
        p = {"Id": "01t", "IsActive": True, "UsageModelType": "Pack"}
        rows = _ready_rows()
        rows["pur_rows"] = []
        r = evaluate_product(p, **rows)
        self.assertFalse(r.is_ready)
        self.assertIn("no ProductUsageResource", r.reasons())


class SoqlLiteralTests(unittest.TestCase):
    def test_escapes_single_quote(self):
        self.assertEqual(soql_literal("O'Brien"), "O\\'Brien")

    def test_escapes_backslash_first(self):
        self.assertEqual(soql_literal("a\\b"), "a\\\\b")


class CliTests(unittest.TestCase):
    def test_product_requires_id_or_code(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["product", "--org", "x"])

    def test_product_rejects_both_id_and_code(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["product", "--org", "x", "--product-id", "01t", "--product-code", "C"])

    def test_scan_parses(self):
        args = build_parser().parse_args(["scan", "--org", "x", "--fail-on-not-ready"])
        self.assertEqual(args.command, "scan")
        self.assertTrue(args.fail_on_not_ready)


if __name__ == "__main__":
    unittest.main()
