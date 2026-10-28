"""Synthetic MDM service-operations scorecard and queue view.

All rules, targets and cases are illustrative. Metrics are calculated from the included scenario records and are not
operational results or service commitments.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .data import ROOT

DATA_DIR = ROOT / "data" / "mdm"
LABEL = "Personal MDM service-operations prototype · synthetic scenario · illustrative targets"


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def load(data_dir: Path = DATA_DIR) -> dict:
    def read(name: str) -> dict:
        return json.loads((data_dir / name).read_text(encoding="utf-8-sig"))

    rules, queue, backlog = (read("operations_rules.json"), read("work_items.json"),
                             read("improvement_backlog.json"))
    cde_registry, dq_rules = read("cde_registry.json"), read("dq_rules.json")
    dq_exceptions, operating_model = read("dq_exceptions.json"), read("operating_model.json")
    entity_data, match_rules = read("records.json"), read("rules.json")
    as_of = _dt(rules["as_of"])
    cohort_start = _dt(rules["cohort_start"])
    ids = [x["id"] for x in queue["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate MDM work-item ID")
    for item in queue["items"]:
        created, due, completed = _dt(item["created_at"]), _dt(item["due_at"]), _dt(item.get("completed_at"))
        if not created or not due or due < created:
            raise ValueError(f"{item['id']} has invalid created_at or due_at")
        if completed and (completed < created or item["status"] != "DELIVERED"):
            raise ValueError(f"{item['id']} has an inconsistent completion timestamp/status")
        if not completed and item["status"] == "DELIVERED":
            raise ValueError(f"{item['id']} is delivered without completed_at")
        if item["initial_validation"] not in {"PASS", "FAIL", "PENDING"}:
            raise ValueError(f"{item['id']} has unknown initial validation state")
    for row in backlog["items"]:
        if row["issue_code"] and not any(i.get("issue_code") == row["issue_code"] for i in queue["items"]):
            raise ValueError(f"{row['id']} refers to an issue code absent from the work queue")
    cde_ids = {x["id"] for x in cde_registry["elements"]}
    wealth_dq_rules = read("wealth_dq_rules.json")
    dq_ids = {x["id"] for x in dq_rules["rules"]} | {x["id"] for x in wealth_dq_rules["rules"]}
    if any(x["cde_id"] not in cde_ids for x in dq_rules["rules"]):
        raise ValueError("a DQ rule refers to an unknown CDE")
    if any(rule_id not in dq_ids for x in cde_registry["elements"] for rule_id in x["quality_rules"]):
        raise ValueError("a CDE refers to an unknown DQ rule")
    if any(x["rule_id"] not in dq_ids for x in dq_exceptions["exceptions"]):
        raise ValueError("a DQ exception refers to an unknown rule")
    case_ids = set(ids)
    if any(x["case_id"] not in case_ids for x in dq_exceptions["exceptions"]):
        raise ValueError("a DQ exception refers to an unknown work case")
    record_ids = {x["id"] for x in entity_data["records"]}
    if any(rid not in record_ids for x in dq_exceptions["exceptions"] for rid in x["record_ids"]):
        raise ValueError("a DQ exception refers to an unknown source record")
    if any(x["status"] == "CLOSED" and (not x.get("closure_evidence") or not x.get("checker") or x["checker"] == x["maker"])
           for x in dq_exceptions["exceptions"]):
        raise ValueError("a closed DQ exception needs closure evidence and an independent checker")
    return {"rules": rules, "items": queue["items"], "backlog": backlog["items"],
            "cdes": cde_registry["elements"], "dq_rules": dq_rules, "dq_exceptions": dq_exceptions["exceptions"],
            "operating_model": operating_model, "entity_records": entity_data["records"], "match_rules": match_rules,
            "as_of": as_of, "cohort_start": cohort_start, "data_dir": data_dir}


def _quality_metrics(data: dict) -> list[dict]:
    from . import entity_mdm

    records = data["entity_records"]
    allowed = set(data["dq_rules"]["jurisdiction_allowed_values"])
    keys: dict[str, list[dict]] = {}
    for record in records:
        key = record["fields"].get("registration_key")
        if key:
            keys.setdefault(key, []).append(record)
    repeated = {key: group for key, group in keys.items() if len(group) > 1}
    collision_groups = []
    for key, group in repeated.items():
        conflict = any(entity_mdm.compare(a, b, data["match_rules"])["verdict"] == "EXCEPTION"
                       for i, a in enumerate(group) for b in group[i + 1:])
        if conflict:
            collision_groups.append(key)
    keys_present = set(keys)
    parents = [r["fields"].get("parent_key") for r in records if r["fields"].get("parent_key")]
    outcomes = {}
    for rule in data["dq_rules"]["rules"]:
        kind, field = rule["kind"], rule["field"]
        if kind == "completeness":
            numerator, denominator = sum(bool(r["fields"].get(field)) for r in records), len(records)
        elif kind == "allowed_value":
            numerator, denominator = sum(r["fields"].get(field) in allowed for r in records), len(records)
        elif kind == "key_collision":
            numerator, denominator = len(collision_groups), len(repeated)
        elif kind == "parent_reference":
            numerator, denominator = sum(p in keys_present for p in parents), len(parents)
        else:
            raise ValueError(f"unknown DQ check kind: {kind}")
        value = numerator / denominator if denominator else None
        target = rule["target"]
        passed = value is not None and (value >= target if rule["direction"] == "MINIMUM" else value <= target)
        outcomes[rule["id"]] = {**rule, "numerator": numerator, "denominator": denominator, "value": value,
                                 "status": "PASS" if passed else "BREACH",
                                 "target_label": "minimum" if rule["direction"] == "MINIMUM" else "maximum",
                                 "evidence_records": collision_groups if kind == "key_collision" else []}
    return list(outcomes.values())


def build(data: dict, as_of: str | None = None) -> dict:
    cutoff = _dt(as_of) if as_of else data["as_of"]
    start = data["cohort_start"]
    if cutoff < start:
        raise ValueError("as_of must be on or after cohort_start")
    items = [x for x in data["items"] if start <= _dt(x["created_at"]) <= cutoff]
    completed = [x for x in items if _dt(x.get("completed_at")) and _dt(x["completed_at"]) <= cutoff]
    completed_ids = {x["id"] for x in completed}
    opened = []
    for item in items:
        if item["id"] in completed_ids:
            continue
        view = dict(item)
        view["status_at_cutoff"] = "IN_PROGRESS (inferred)" if item.get("completed_at") else item["status"].replace("_", " ")
        opened.append(view)
    on_time = [x for x in completed if _dt(x["completed_at"]) <= _dt(x["due_at"])]
    first_pass = [x for x in completed if x["initial_validation"] == "PASS"]
    reworked = [x for x in completed if x["initial_validation"] == "FAIL"]
    overdue = [x for x in opened if _dt(x["due_at"]) < cutoff]
    age_limit = data["rules"]["backlog_age_threshold_calendar_days"]
    aged = [x for x in opened if (cutoff - _dt(x["created_at"])).total_seconds() > age_limit * 86400]

    def pct(n: int, d: int) -> float | None:
        return n / d if d else None

    completed_n = len(completed)
    open_n = len(opened)
    metrics = [
        {"id": "on_time_completion_rate", "label": "Completed on time", "numerator": len(on_time),
         "denominator": completed_n, "value": pct(len(on_time), completed_n),
         "target": data["rules"]["targets"]["on_time_completion_rate"],
         "definition": data["rules"]["metric_notes"]["on_time_completion_rate"],
         "source": "data/mdm/work_items.json: completed_at and due_at", "owner": "MDM operations lead (synthetic role)"},
        {"id": "first_pass_yield", "label": "First-pass validation", "numerator": len(first_pass),
         "denominator": completed_n, "value": pct(len(first_pass), completed_n),
         "target": data["rules"]["targets"]["first_pass_yield"],
         "definition": data["rules"]["metric_notes"]["first_pass_yield"],
         "source": "data/mdm/work_items.json: initial_validation", "owner": "Data quality lead (synthetic role)"},
        {"id": "rework_rate", "label": "Completed cases requiring rework", "numerator": len(reworked),
         "denominator": completed_n, "value": pct(len(reworked), completed_n), "target": None,
         "definition": "Completed cases with initial_validation FAIL divided by all completed cases in the cohort.",
         "source": "data/mdm/work_items.json: initial_validation", "owner": "Data quality lead (synthetic role)"},
        {"id": "open_overdue", "label": "Open and overdue", "numerator": len(overdue), "denominator": open_n,
         "value": pct(len(overdue), open_n), "target": 0.0,
         "definition": data["rules"]["metric_notes"]["open_overdue"],
         "source": "data/mdm/work_items.json: status, due_at; report as_of", "owner": "Queue owners (synthetic roles)"},
        {"id": "aged_backlog", "label": f"Open backlog aged > {age_limit} calendar days", "numerator": len(aged),
         "denominator": open_n, "value": pct(len(aged), open_n), "target": 0.0,
         "definition": data["rules"]["metric_notes"]["aged_backlog"],
         "source": "data/mdm/work_items.json: created_at, status; report as_of", "owner": "MDM operations lead (synthetic role)"},
    ]
    type_counts: dict[str, int] = {}
    for item in items:
        type_counts[item["work_type"]] = type_counts.get(item["work_type"], 0) + 1
    hub_counts = []
    for hub in sorted({x["hub"] for x in items}):
        hub_items = [x for x in items if x["hub"] == hub]
        open_ids = {x["id"] for x in opened}
        hub_counts.append({"hub": hub, "total": len(hub_items), "open": sum(x["id"] in open_ids for x in hub_items),
                           "delivered": sum(x in completed for x in hub_items)})
    issues = []
    for candidate in data["backlog"]:
        if candidate.get("issue_code"):
            linked = [x["id"] for x in items if x.get("issue_code") == candidate["issue_code"]]
        elif candidate.get("link_rule") == "any_handoffs_recorded":
            linked = [x["id"] for x in items if x.get("handoffs", 0) > 0]
        else:
            linked = []
        issues.append({**candidate, "linked_cases": linked, "linked_count": len(linked)})
    quality_metrics = _quality_metrics(data)
    exceptions = []
    for exception in data["dq_exceptions"]:
        opened_at, closed_at = _dt(exception["opened_at"]), _dt(exception.get("closed_at"))
        if opened_at > cutoff:
            continue
        view = dict(exception)
        view["status_at_cutoff"] = exception["status"] if not closed_at or closed_at <= cutoff else "OPEN (inferred)"
        exceptions.append(view)
    closed = [x for x in exceptions if x["status_at_cutoff"] == "CLOSED"]
    closure_evidence = [x for x in closed if x.get("closure_evidence") and x.get("checker") and x["checker"] != x["maker"]]
    audit_metric = {"id": "closure_evidence", "label": "Closed exceptions with independent-checker evidence",
                    "numerator": len(closure_evidence), "denominator": len(closed),
                    "value": len(closure_evidence) / len(closed) if closed else None,
                    "target": 1.0, "definition": "Closed DQ exceptions with closure evidence and a checker distinct from the maker divided by all closed DQ exceptions.",
                    "source": "data/mdm/dq_exceptions.json: status, closure_evidence, maker, checker",
                    "owner": "Data governance lead (synthetic role)",
                    "status": "NOT_APPLICABLE" if not closed else ("PASS" if len(closure_evidence) == len(closed) else "BREACH")}
    return {"label": LABEL, "as_of": cutoff.isoformat().replace("+00:00", "Z"),
            "cohort_start": data["rules"]["cohort_start"], "cohort_end": cutoff.isoformat().replace("+00:00", "Z"),
            "items": items, "completed": completed, "open": opened, "overdue": overdue, "aged": aged,
            "historical_state_note": "For an as-of cutoff before a recorded completion timestamp, open state is inferred as IN_PROGRESS because event-level status history is not included.",
            "metrics": metrics, "type_counts": type_counts, "hub_counts": hub_counts,
            "handoffs": sum(x["handoffs"] for x in items), "improvements": issues,
            "data_label": data["rules"]["label"], "age_limit_days": age_limit,
            "cdes": data["cdes"], "quality_metrics": quality_metrics,
            "exceptions": exceptions, "audit_metric": audit_metric,
            "operating_model": data["operating_model"]}


def _fmt_ratio(metric: dict) -> str:
    v = metric["value"]
    if v is None:
        return "n/a"
    return f"{metric['numerator']}/{metric['denominator']} ({v:.1%})"


def as_text(report: dict) -> str:
    lines = [report["label"], report["data_label"],
             f"Cohort: {report['cohort_start'][:10]} to {report['cohort_end'][:10]} · as of {report['as_of']}", "",
             "## Monthly service scorecard (month-to-date)"]
    for m in report["metrics"]:
        target = f" · illustrative target {m['target']:.0%}" if m["target"] is not None else ""
        lines.append(f"{m['label']}: {_fmt_ratio(m)}{target}")
    lines += ["", f"Work received: {len(report['items'])} · delivered: {len(report['completed'])} · open: {len(report['open'])} · handoffs: {report['handoffs']}",
              "Work mix: " + ", ".join(f"{k.lower()} {v}" for k, v in sorted(report["type_counts"].items())), "",
              "## Open queue"]
    for item in sorted(report["open"], key=lambda x: (x["due_at"], x["id"])):
        due_flag = "OVERDUE" if item in report["overdue"] else "open"
        block = f" · blocker: {item['blocker']}" if item["blocker"] else ""
        lines.append(f"{item['id']} {item['work_type']} {item['priority']} · {due_flag} · due {item['due_at']} · {item['owner']} / {item['hub']}{block}")
    lines += ["", "## Hub view (synthetic)" ]
    lines.extend(f"{x['hub']}: {x['open']} open / {x['total']} total" for x in report["hub_counts"])
    lines += ["", "## Product and engineering improvement backlog"]
    for x in report["improvements"]:
        lines.append(f"{x['id']} {x['priority']} {x['title']} · {x['linked_count']} linked case(s): {', '.join(x['linked_cases']) or 'none'}")
        lines.append(f"  Change: {x['change']}")
        lines.append(f"  Measure: {x['success_measure']}")
    lines += ["", "## Critical data elements and lineage", "CDE | Owner | Trusted source | Quality rules"]
    for cde in report["cdes"]:
        lines.append(f"{cde['id']} {cde['name']} | {cde['business_owner']} | {cde['trusted_source']} | {', '.join(cde['quality_rules'])}")
        lines.extend(f"  {step['step']}. {step['system']}.{step['field']} — {step['action']}" for step in cde["lineage"])
    lines += ["", "## Data-quality rule results"]
    for m in report["quality_metrics"]:
        target = f"{m['target_label']} {m['target']:.0%}"
        val = "n/a" if m["value"] is None else f"{m['value']:.1%}"
        lines.append(f"{m['id']} {m['name']}: {m['numerator']}/{m['denominator']} ({val}) · target {target} · {m['status']}")
        lines.append(f"  {m['definition']} Source: {m['source']} · owner {m['owner']}")
        if m["evidence_records"]:
            lines.append(f"  Conflicting key groups: {', '.join(m['evidence_records'])}")
    lines.append(f"Audit closure evidence: {report['audit_metric']['numerator']}/{report['audit_metric']['denominator']} closed exception(s) have distinct-checker evidence.")
    lines += ["", "## DQ exception register"]
    for x in report["exceptions"]:
        lines.append(f"{x['id']} {x['status_at_cutoff']} · {x['rule_id']} · case {x['case_id']} · owner {x['owner']} · {x['root_cause']}")
        lines.append(f"  Remediation: {x['remediation']}")
        if x.get("closure_evidence"):
            lines.append(f"  Closure evidence: {x['closure_evidence']} · maker {x['maker']} / checker {x['checker']}")
        for event in x["events"]:
            lines.append(f"  Audit: {event['at']} {event['action']} by {event['by']}")
    lines += ["", "## Governance cadence and continuity", "Governance forums:"]
    for x in report["operating_model"]["review_cadence"]:
        lines.append(f"{x['cadence']}: {x['forum']} · output: {x['output']}")
    lines.append("Role coverage:")
    for x in report["operating_model"]["roles"]:
        lines.append(f"{x['role']}: primary {x['primary_hub']} / backup {x['backup_hub']} · {x['coverage']}")
    lines.append("Continuity scenarios (tabletop required; not tested):")
    for x in report["operating_model"]["continuity_scenarios"]:
        lines.append(f"{x['scenario']} · trigger {x['trigger']} · fallback {x['fallback']} · evidence {x['evidence']}")
    lines += ["", "Governed product catalogue, schema and second-domain scorecards: run `python -m mdm_prototype product`.",
              "Metric definitions, numerators/denominators, sources and owners: see docs/MDM_OPERATIONS.md.",
              "Scenario figures are calculated from the included synthetic queue; they are not real service metrics or results.",
              ""]
    return "\n".join(lines)


def as_html(report: dict) -> str:
    esc = lambda x: html.escape(str(x))
    from . import product
    product_section = product.extra_html(product.load(), report["quality_metrics"])
    cards = []
    for m in report["metrics"]:
        target = f"<small>Illustrative target: {m['target']:.0%}</small>" if m["target"] is not None else "<small>Observed in synthetic scenario</small>"
        cards.append(f"<article class='metric'><span>{esc(m['label'])}</span><strong>{esc(_fmt_ratio(m))}</strong>{target}<details><summary>Definition and provenance</summary><p>{esc(m['definition'])}</p><p><b>Source:</b> {esc(m['source'])}<br><b>Owner:</b> {esc(m['owner'])}</p></details></article>")
    queue_rows = []
    for x in sorted(report["open"], key=lambda i: (i["due_at"], i["id"])):
        status = "OVERDUE" if x in report["overdue"] else x["status_at_cutoff"]
        queue_rows.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in (x["id"], x["work_type"].replace("_", " "), x["priority"], status, x["due_at"][:10], x["owner"], x["hub"], x["blocker"] or "—")) + "</tr>")
    hub_rows = "".join(f"<tr><td>{esc(x['hub'])}</td><td>{x['total']}</td><td>{x['open']}</td><td>{x['delivered']}</td></tr>" for x in report["hub_counts"])
    improvements = "".join(f"<article class='action'><h3>{esc(x['id'])} · {esc(x['priority'])} · {esc(x['title'])}</h3><p>{esc(x['change'])}</p><p><b>Linked synthetic cases:</b> {esc(', '.join(x['linked_cases']) or 'none')}</p><p><b>Measure after a future release:</b> {esc(x['success_measure'])}</p><p><b>Owner:</b> {esc(x['owner'])}</p></article>" for x in report["improvements"])
    cde_rows = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in (c["id"], c["name"], c["definition"], c["business_owner"], c["data_steward"], c["trusted_source"], ", ".join(c["quality_rules"]))) + "</tr>" for c in report["cdes"])
    lineage = "".join(f"<details class='lineage'><summary>{esc(c['id'])} · {esc(c['name'])} · view lineage</summary><ol>" + "".join(f"<li><b>{esc(s['system'])}.{esc(s['field'])}</b> — {esc(s['action'])}</li>" for s in c["lineage"]) + "</ol></details>" for c in report["cdes"])
    dq_rows = "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in (m["id"], m["name"], f"{m['numerator']}/{m['denominator']}", "n/a" if m["value"] is None else f"{m['value']:.1%}", f"{m['target_label']} {m['target']:.0%}", m["status"], m["owner"], m["source"])) + f"</tr><tr><td colspan='8'>{esc(m['definition'])}</td></tr>" for m in report["quality_metrics"])
    audit_exceptions = "".join(f"<article class='action'><h3>{esc(x['id'])} · {esc(x['status_at_cutoff'])} · {esc(x['severity'])}</h3><p><b>Rule / case:</b> {esc(x['rule_id'])} / {esc(x['case_id'])} · <b>Owner:</b> {esc(x['owner'])}</p><p><b>Root cause:</b> {esc(x['root_cause'])}</p><p><b>Remediation:</b> {esc(x['remediation'])}</p><p><b>Closure evidence:</b> {esc(x.get('closure_evidence') or 'open; closure evidence pending')}</p><ol>" + "".join(f"<li>{esc(e['at'])} · {esc(e['action'])} · {esc(e['by'])}</li>" for e in x["events"]) + "</ol></article>" for x in report["exceptions"])
    roles = "".join(f"<article class='action'><h3>{esc(x['role'])}</h3><p><b>Primary / backup:</b> {esc(x['primary_hub'])} / {esc(x['backup_hub'])}</p><p><b>Coverage:</b> {esc(x['coverage'])}</p><p>{esc(x['responsibilities'])}</p></article>" for x in report["operating_model"]["roles"])
    cadence = "".join(f"<tr><td>{esc(x['cadence'])}</td><td>{esc(x['forum'])}</td><td>{esc(', '.join(x['participants']))}</td><td>{esc(x['output'])}</td></tr>" for x in report["operating_model"]["review_cadence"])
    continuity = "".join(f"<article class='action'><h3>{esc(x['scenario'])}</h3><p><b>Trigger:</b> {esc(x['trigger'])}</p><p><b>Fallback:</b> {esc(x['fallback'])}</p><p><b>Evidence:</b> {esc(x['evidence'])}</p><p><b>Validation:</b> {esc(x['validation'])}</p></article>" for x in report["operating_model"]["continuity_scenarios"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Synthetic MDM service operations scorecard and queue prototype">
<link rel="icon" href="/assets/favicon-32x32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<title>MDM Service Operations · Personal Prototype</title>
<style>
:root{{color-scheme:light dark;--bg:#f4f6fa;--panel:#fff;--ink:#1c2738;--muted:#58677d;--line:#d7dfeb;--accent:#2167a5;--warn:#9b5d05}}
@media(prefers-color-scheme:dark){{:root{{--bg:#101722;--panel:#182333;--ink:#edf3fb;--muted:#b4c1d3;--line:#34445a;--accent:#83baff;--warn:#ffd184}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,Segoe UI,sans-serif}}main{{max-width:1180px;margin:auto;padding:32px 20px 56px}}h1{{line-height:1.15;margin:.3em 0}}h2{{margin-top:2rem}}p,.muted,small{{color:var(--muted)}}.banner{{padding:14px 18px;border:1px solid var(--line);background:var(--panel);border-radius:10px;margin:18px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}.metric,.action,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}}.metric span{{display:block;color:var(--muted);font-size:.94rem}}.metric strong{{display:block;font-size:1.8rem;margin:.35rem 0}}details{{margin-top:12px;font-size:.9rem}}summary{{cursor:pointer;color:var(--accent)}}.table-wrap{{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:850px}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:.9rem;color:var(--muted)}}.actions{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}.action h3{{margin:.2rem 0 .7rem;font-size:1rem}}footer{{margin-top:30px;color:var(--muted);font-size:.88rem}}@media(max-width:600px){{main{{padding:22px 14px 40px}}h1{{font-size:1.8rem}}}}
</style></head><body><main>
<p class="muted">{esc(report['label'])}</p><h1>MDM Service Operations</h1>
<p class="muted">Cohort {esc(report['cohort_start'][:10])} to {esc(report['cohort_end'][:10])} · simulated report as of {esc(report['as_of'])}</p>
<aside class="banner"><b>Scenario boundary:</b> {esc(report['data_label'])} The cases, owners, hubs, thresholds and service figures are invented for demonstration. They are not based on or connected to any firm's systems, data, processes or approved policies.</aside>
<h2>Monthly governance scorecard (month-to-date)</h2><section class="grid">{''.join(cards)}</section>
<section class="grid" style="margin-top:12px"><article class="panel"><b>{len(report['items'])}</b><br>cases in cohort</article><article class="panel"><b>{len(report['completed'])}</b><br>delivered</article><article class="panel"><b>{len(report['open'])}</b><br>open backlog</article><article class="panel"><b>{report['handoffs']}</b><br>recorded handoffs</article></section>
<h2>Open queue and blockers</h2><div class="table-wrap"><table><thead><tr><th>Case</th><th>Work type</th><th>Priority</th><th>State</th><th>Due</th><th>Owner</th><th>Hub</th><th>Blocker</th></tr></thead><tbody>{''.join(queue_rows)}</tbody></table></div><p class="muted">{esc(report['historical_state_note'])}</p>
<h2>Distributed team view</h2><div class="table-wrap"><table><thead><tr><th>Simulated hub</th><th>Total cases</th><th>Open</th><th>Delivered</th></tr></thead><tbody>{hub_rows}</tbody></table></div><p class="muted">Queue counts are not capacity or utilization measures; no staffing capacity is modelled.</p>
<h2>Improvement backlog</h2><section class="actions">{improvements}</section>
<h2>Critical data elements and lineage</h2><p class="muted">Definitions, accountable roles, trusted-source assumptions and quality-rule links are synthetic. Expand each CDE to follow the source-to-target path.</p><div class="table-wrap"><table><thead><tr><th>CDE</th><th>Name</th><th>Business definition</th><th>Accountable owner</th><th>Steward</th><th>Trusted source (illustrative)</th><th>Rules</th></tr></thead><tbody>{cde_rows}</tbody></table></div><section class="panel">{lineage}</section>
<h2>Data-quality control scorecard</h2><p class="muted">Each rate shows its explicit numerator, denominator, target, owner and source. A breach is an exception signal, not an assertion of regulatory non-compliance.</p><div class="table-wrap"><table><thead><tr><th>Rule</th><th>Control</th><th>Pass / exception count</th><th>Rate</th><th>Illustrative threshold</th><th>Status</th><th>Owner</th><th>Source</th></tr></thead><tbody>{dq_rows}</tbody></table></div><p><b>Audit closure evidence:</b> {report['audit_metric']['numerator']}/{report['audit_metric']['denominator']} closed exceptions have evidence and independent checker review.</p>
<h2>Exception remediation and audit trail</h2><section class="actions">{audit_exceptions}</section>
<h2>Governance operating model</h2><div class="table-wrap"><table><thead><tr><th>Cadence</th><th>Forum</th><th>Participants</th><th>Output</th></tr></thead><tbody>{cadence}</tbody></table></div><section class="actions">{roles}</section>
<h2>Continuity scenarios</h2><p class="muted">Illustrative runbooks only; tabletop validation remains required.</p><section class="actions">{continuity}</section>
{product_section}
<aside class="banner"><b>AI boundary:</b> no AI model classifies these exceptions. The included categories come from deterministic data rules. A future model could suggest an exception category only as a reviewable aid, with steward confirmation and a separately labelled evaluation set.</aside>
<footer>Personal prototype · synthetic data · illustrative service targets · no firm systems or data. The on-time measure uses calendar timestamps, not staffed business hours. No reported figure represents measured operational performance.</footer>
</main></body></html>"""

