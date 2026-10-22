# Investment-entity mastering: prototype slice

**Personal prototype · synthetic records · illustrative rules.** This demonstration is not based on or connected to any firm's systems, data, processes or approved policies. It is a learning artifact for discussing investment-entity data quality and stewardship; it is not production MDM or legal/compliance guidance.

## Workflow demonstrated

Four invented source feeds contain duplicate and near-duplicate fund, issuer, holding and manager records. The prototype compares records using normalized legal names, entity type, jurisdiction and synthetic registration keys. It returns `MATCH`, `REVIEW`, `NO_MATCH` or `EXCEPTION`, with a reason. A shared key is a candidate signal, not permission to merge; a key collision across entity type or jurisdiction blocks the merge. Similar names without a shared key go to a steward rather than auto-matching.

For approved groups, the preview applies a field-level source-precedence table and retains the source record behind each selected value. Conflicts in registration key, jurisdiction, entity type or parent relationship remain unresolved and enter the steward queue. Publishing an approved group requires distinct synthetic maker and checker roles. The sample group therefore produces a golden-record preview while leaving its conflicting parent relationship open for review.

## Run

```bash
python -m mdm_prototype demo
python -m mdm_prototype evaluate
python -m mdm_prototype ops
python -m mdm_prototype ops --html
```

The evaluation command reports agreement and match-suggestion precision/recall for 20 synthetic, author-labelled record pairs. The examples and rules were developed together, so this is an illustrative demonstration, not an independent benchmark or evidence of production accuracy. Displayed scores are explicitly labelled **name similarity**; a high name similarity does not decide the outcome or authorize a merge. Do not compare this author-labelled result with a separately authored or held-out evaluation.

## Design choices and boundaries

- Identifier agreement is considered alongside entity type, jurisdiction and name consistency; contradictory identity attributes trigger an exception.
- Names alone can prompt review but never create a merge.
- Survivorship is field-specific and provenance-preserving. Critical identity and hierarchy conflicts are not silently resolved by source precedence.
- The sample maker-checker record illustrates a control, not a configured access-control system. This prototype does not authenticate users or enforce permissions.
- Source authority, thresholds, legal-form normalization and exception SLAs are illustrative inputs that would need validation with data owners, operations, legal and compliance before any real use.
- No real registry identifiers, entities or client data are included. There is no external-system integration, automated ingestion, fuzzy-search service, production workflow, or claim of improved data quality.

The operations layer adds a reproducible synthetic service queue, explicit scorecard definitions and a proposal backlog. See [MDM operations](MDM_OPERATIONS.md) for the metric contract and scenario boundaries. The useful next extension is a separately authored, frozen evaluation set and a steward change workflow with field-level evidence, reviewer decision and before/after golden-record fingerprint. Keep the current demonstration score labelled as author-labelled.
