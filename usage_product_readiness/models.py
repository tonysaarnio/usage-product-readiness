"""UsageModelType picklist values and readiness policy constants.

``Product2.UsageModelType`` is a **restricted** picklist. Verified against the org
describe on Salesforce 262 and 264 (Winter '27), its values are exactly:

    Anchor, Pack, Commit, CommitmentQuantity, CommitmentSpend

There is no ``Token`` or ``CommitmentToken`` value — those are not real
UsageModelType entries. Because the picklist is restricted, the scan prefers to
**discover** the live values from the org (``_soql.describe_picklist``) and only
falls back to :data:`USAGE_MODEL_TYPES` when the describe is unavailable.
"""

from __future__ import annotations

#: Documented fallback — the full restricted picklist (Anchor/Pack + the three
#: commitment types). Keep this in sync with the org describe if the schema changes.
USAGE_MODEL_TYPES = ("Anchor", "Pack", "Commit", "CommitmentQuantity", "CommitmentSpend")

#: Commitment models. A ``UsagePrdGrantBindingPolicy`` is **not** required for these
#: — the platform only accepts a binding policy for Anchor/Pack grants
#: ("Select a Product with the Usage Model Type as Anchor or Pack").
COMMITMENT_USAGE_MODELS = frozenset({"Commit", "CommitmentQuantity", "CommitmentSpend"})

#: Models that participate in the guided usage (Manage Usage Resources) flow.
#: Every real UsageModelType value qualifies; a product whose value is outside this
#: set is flagged (non-blocking) as an unexpected/legacy model.
GUIDED_USAGE_MODELS = frozenset(USAGE_MODEL_TYPES)
