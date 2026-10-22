# Governed data products — personal prototype

**Synthetic data · illustrative controls and targets · no firm systems or policies.** This one-page product brief describes a personal prototype that connects entity mastering and wealth data quality to a governed data product.

## Users and problem

- **Data producers:** understand definitions, source authority, transformation and quality expectations before publishing.
- **Data consumers:** discover a product, its schema, freshness, limitations and request only fields needed for a stated purpose.
- **Stewards and owners:** review quality exceptions, access requests, lineage gaps and remediation evidence.
- **Control functions:** inspect metric definitions, numerator/denominator, source evidence, ownership and closure history.

The scenario addresses fragmented definitions and lineage, unclear source trust, inconsistent quality measurement and manual evidence gathering. The product catalogue connects a schema and contract to CDEs, DQ checks, owners, lineage, access review and scorecards.

## Product vision

Make governed reference data discoverable and reusable with evidence attached: every published field has a definition, accountable owner, trusted-source path, quality status, permitted-use review and change history.

## Roadmap

| Horizon | Scope | Intended outcome |
|---|---|---|
| **Now (prototype)** | Synthetic entity and wealth data; CDE registry and glossary; hop-by-hop lineage; deterministic DQ rules; product contract; manual owner access decision; scorecards and audit evidence | Demonstrate the governance lifecycle and expose gaps without implying production readiness |
| **Next** | Validate definitions and thresholds with real domain owners; test continuity; add versioned change workflow and consumer feedback; measure exception handling time and data reuse | Confirm whether controls fit actual operating needs and establish a measurable baseline |
| **Later** | Consider authenticated policy enforcement, catalog/workflow integration, automated ingestion and broader domains; evaluate any bounded AI suggestions under steward control | Scale only after ownership, control evidence, security and outcome measures are agreed |

## Prioritisation

Rank work by **control urgency**, **consumer impact**, **reuse across teams**, **dependencies**, and **effort**. Resolve high-severity control gaps first; then prioritize improvements that unblock multiple consumers and have clear owners. Make trade-offs in a monthly synthetic governance forum with data owners, stewards, operations, technology and consumer representatives. The forum and cadence are illustrative.

## Success measures

Prototype measures include CDE definition and lineage completeness, DQ pass numerator/denominator by rule and country, open/overdue exceptions, independent closure evidence, access decision and purpose narrowing, subscribers, consuming use cases, and time from publication to first consumption. Definitions, source and denominator should accompany every metric. Values and targets in this repo are invented and are not measured outcomes.

## Deliberate v1 exclusions

- **Real access control or identity enforcement:** requires enterprise security, identity and policy integration.
- **Workflow engine or automated ingestion:** would imply operational execution not present in this demonstration.
- **ML matching or AI recommendations:** deterministic rules make the control path inspectable; a future bounded suggestion requires a frozen evaluation set, human review and approval.
- **Production/regulatory assertions:** synthetic examples cannot establish compliance, control effectiveness or business impact.

## Product boundary

The catalogue, approvals, role model, values and policies are synthetic or illustrative. The AI-ready flag is a deterministic readiness check only; no AI model is included. This is a personal prototype, not a deployed data marketplace.
