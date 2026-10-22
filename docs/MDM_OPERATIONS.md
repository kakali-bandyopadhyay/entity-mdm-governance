# MDM service operations: synthetic prototype

**Personal prototype · synthetic data · illustrative service targets.** This operating scenario is not based on or connected to any firm's systems, data, processes or approved policies. It demonstrates how an MDM leader could make intake, quality, timeliness, backlog and improvement work visible; it does not claim measured service performance.

## Run the workflow

```powershell
python -m mdm_prototype ops
python -m mdm_prototype ops --as-of 2026-10-18T12:00:00Z
python -m mdm_prototype ops --html
```

The HTML command writes `docs/mdm_operations.html`, a responsive static scorecard, open queue, synthetic hub view and product/engineering improvement backlog. The report date and service cases are fixed in JSON so the same commands produce reproducible outputs. The `--as-of` option supports a historical queue snapshot; it does not simulate work or change the underlying cases. Since event-level status history is not included, a case with a future completion timestamp is labelled `IN_PROGRESS (inferred)` in an earlier snapshot.

## What is modelled

The scenario has 13 invented cases from 1–21 October 2026 across onboarding, maintenance, hierarchy change, migration, integration exceptions and identity conflicts. Each case has a synthetic owner and hub, priority, created and due timestamps, state, initial/final validation, handoffs and a blocker or root-cause code where applicable. The open items show source follow-up, steward review, migration and maintenance work. All cases are invented and are not based on or connected to any firm's systems, data, processes or approved policies.

The scorecard intentionally shows calculation units rather than free-floating percentages:

| Measure | Example calculation | Source and limitation |
|---|---|---|
| On-time completion | Completed by due timestamp / completed in cohort | `completed_at` and `due_at` in `data/mdm/work_items.json`; calendar timestamps, not staffed-business hours |
| First-pass yield | Completed with initial validation PASS / completed in cohort | `initial_validation`; does not imply quality across every possible data rule |
| Rework rate | Completed with initial validation FAIL / completed in cohort | A synthetic proxy for cases needing correction; not a cost or effort measure |
| Open overdue | Open items past due / open items | Queue state and due timestamps at report cutoff |
| Aged backlog | Open items older than five calendar days / open items | Five-day ageing threshold is configurable illustrative data, not a service commitment |

Each scorecard metric includes its definition, numerator, denominator, source and synthetic owner role. The 90% on-time and first-pass markers are illustrative targets only. The dashboard also shows hub-level case counts, but explicitly does not infer capacity or utilization because the prototype contains no staffing or working-hours model.

## CDE registry and lineage

`data/mdm/cde_registry.json` defines five synthetic critical data elements: registration key, legal name, entity type, jurisdiction and parent key. Each entry includes a business definition, domain, criticality, accountable business owner, steward, illustrative trusted-source assumption, linked quality rules and a numbered source-to-target path. The path shows where the raw value is retained, normalized or validated, reviewed, mastered and delivered downstream. These entries are examples of a glossary and lineage catalogue, not descriptions of a real platform.

## Data-quality controls and exception audit

`data/mdm/dq_rules.json` contains five executable checks: registration-key completeness (25/30), jurisdiction-code validity (30/30), conflicting repeated-key groups (2/7), parent-key reference integrity (3/4), and legal-name completeness (30/30). The repeated-key rule deliberately tests *identity conflicts* across feeds; it does not label expected cross-source copies as duplicate masters. Each check reports its metric definition, numerator, denominator, target direction/value, source and synthetic owner. Thresholds are illustrative, and a breach is a queue signal rather than a regulatory conclusion.

`data/mdm/dq_exceptions.json` records five synthetic issues with rule and case links, source record IDs, owner, severity, root cause, remediation, timestamps and audit events. Closed master-record corrections require closure evidence and a checker distinct from the maker. Where an upstream source defect remains after the master is corrected, the exception scope says so explicitly; the source-level DQ metric can therefore remain in breach until source remediation is complete. Open and escalated issues remain visible with their next action and missing closure evidence.

## Governance cadence, multi-hub coverage and continuity

`data/mdm/operating_model.json` shows synthetic role ownership across three generic hubs, primary/backup coverage, a daily queue review, weekly root-cause forum and monthly governance scorecard. It includes two illustrative continuity scenarios: a hub outage and a failed feed during migration. Each names a trigger, fallback, owner and evidence to retain. The status is `TABLETOP_REQUIRED`; the prototype does not claim the plan has been exercised, does not contain real staffing data and does not calculate team capacity. Treat it as an operating-model discussion aid, not a business-continuity plan.

The prototype does not use an AI model to classify exceptions. Current categories come from deterministic data rules. A future bounded model could suggest a category for steward review, but would need a human confirmation step and a separately labelled evaluation set before any operational use.

## Governed data product and wealth-domain controls

`python -m mdm_prototype product` shows a synthetic product catalogue and contract: schema fields linked to CDEs, illustrative quality SLOs, lineage reference, refresh cadence, version and change policy. The access-request queue shows synthetic owner decisions; it is not identity management or access enforcement. Requests are granted, narrowed, denied or left pending with a reason.

The second domain contains 108 synthetic client/account snapshot rows: 12 records per country in each of August, September and October 2026. Five wealth CDEs link to glossary terms and source-to-target hops. Any relevance tags are illustrative mappings only, not statements of regulatory requirements. Each new wealth DQ rule has seeded passing/failing test rows and is marked active in the example only because those tests pass. Readable SQL queries cover both domains, run over in-memory SQLite tables and return the same metric counts as the Python checks. Monthly and quarterly scorecard changes are shown as percentage-point differences.

The service-operations, product and audit-support views share one illustrative scenario cutoff: **2026-10-21 12:00 UTC**. The monthly scorecard shows October against September. The quarterly panel shows the available August–September Q3 snapshots (24 records per country) and is explicitly marked partial; no quarter-over-quarter trend is invented because a full comparison period is not included.

Consumer-adoption measures are also supplied with definitions, numerator, denominator and source: subscribers per product, consuming use cases per product and calendar days to first consumption. These values are illustrative and not measured. Monthly and quarterly country scorecards provide numerator, denominator, trend, source and synthetic owner. The deterministic executive summary lists the largest deteriorations, first three open exceptions and a decision prompt. Its values are generated from the frozen synthetic rows, not production observations. The AI-ready flag is a data-readiness check, not an AI capability; any failing linked rule or missing definition, lineage or owner explains why a CDE is not ready.

`python -m mdm_prototype audit` writes `out/mdm_audit_evidence_pack.md` with rule and lineage gaps, evidence, timestamps, owners, remediation state and a deterministic triage prefill. The manual-steps-avoided figure is an illustrative estimate based on three assumed copy/search steps per grouped rule/root-cause record; no time saving has been measured. The output directory is ignored by Git.

## Operating improvement loop

The work queue links recurring exception codes and recorded handoffs to proposed product and engineering changes. For example, missing registration identifiers prompt a proposed source-side validation change; parent-key conflicts prompt an evidence panel and steward rationale; handoff improvement proposes explicit receiving-owner acknowledgement. Each backlog item names the synthetic owner role and a measure to evaluate after a future release. Those measures are proposals, not claimed outcomes.

An example operating rhythm for discussion is a daily queue review of due/blocked cases and a weekly quality and improvement review of recurring issues, rework and handoffs. The prototype supplies the evidence view; it does not schedule meetings, assign real work, or model regional capacity.

## Boundaries

- The only measured values are calculations over the included synthetic case file; nothing is observed from a live operation.
- Target thresholds, roles, hubs, dates, priorities and due times are all illustrative.
- No user authentication, access control, workflow engine, external feed, staffed-hours calendar, capacity planning or SLA enforcement is implemented.
- The scorecard does not establish causation or prove that any proposed automation improves quality or timeliness.
- Before real use, data owners and operations would define authoritative sources, quality rules, severity, clock calendars, service targets, ownership, escalation and audit requirements.
