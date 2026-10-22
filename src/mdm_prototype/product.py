"""Synthetic governed-data-product, DQ, lineage and audit-support layer.

All records, role names, thresholds, results and effort estimates are illustrative.
No external systems, services or models are used.
"""
from __future__ import annotations

import html
import json
import sqlite3
from difflib import SequenceMatcher
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from .data import ROOT

DATA_DIR = ROOT / "data" / "mdm"
SQL_DIR = ROOT / "sql" / "dq_rules"
AS_OF = date(2026, 10, 21)
AS_OF_TIMESTAMP = "2026-10-21T12:00:00Z"


def _read(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def format_trend(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f} pp"


def load():
    return {
        "product": _read("data_products.json"),
        "access": _read("access_requests.json"),
        "wealth": _read("wealth_records.json"),
        "wealth_rules": _read("wealth_dq_rules.json"),
        "glossary": _read("glossary.json"),
        "cdes": _read("cde_registry.json")["elements"],
        "dq_exceptions": _read("dq_exceptions.json")["exceptions"],
    }


def rule_results(data: dict, month: str | None = None) -> list[dict]:
    rows = data["wealth"]["records"]
    if month:
        rows = [r for r in rows if r["snapshot_month"] == month]
    known_clients = {r["client_id"] for r in rows}
    results = []
    for rule in data["wealth_rules"]["rules"]:
        field, kind = rule["field"], rule["kind"]
        if kind == "completeness":
            passing = [r for r in rows if r.get(field) not in (None, "")]
        elif kind == "validity":
            passing = [r for r in rows if r.get(field) in rule["allowed_values"]]
        elif kind == "uniqueness":
            counts = Counter(r.get(field) for r in rows)
            passing = [r for r in rows if r.get(field) and counts[r[field]] == 1]
        elif kind == "hierarchy":
            passing = [r for r in rows if not r.get(field) or r[field] in known_clients]
        else:
            raise ValueError(f"unknown wealth DQ rule kind: {kind}")
        denominator = len(rows)
        numerator = len(passing)
        ratio = numerator / denominator if denominator else None
        threshold = rule["illustrative_threshold"]
        status = "NO_DATA" if ratio is None else ("PASS" if ratio >= threshold else "BREACH")
        results.append({**rule, "numerator": numerator, "denominator": denominator,
                        "value": ratio, "status": status,
                        "source": "data/mdm/wealth_records.json (synthetic snapshot)",
                        "owner": rule["owner_role"]})
    return results


def validate_rules(data: dict) -> list[dict]:
    """Rule activation requires all seeded invalid rows caught and valid rows accepted."""
    result = []
    for rule in data["wealth_rules"]["rules"]:
        tests = rule["test_rows"]
        def passes(row):
            value = row.get(rule["field"])
            if rule["kind"] == "completeness": return value not in (None, "")
            if rule["kind"] == "validity": return value in rule["allowed_values"]
            if rule["kind"] == "uniqueness": return bool(value)
            if rule["kind"] == "hierarchy": return not value or value in row.get("known_clients", [])
            return False
        if rule["kind"] == "uniqueness":
            valid_values=[x.get(rule["field"]) for x in tests["valid"]]
            invalid_values=[x.get(rule["field"]) for x in tests["invalid"]]
            valid_ok=all(valid_values) and len(valid_values)==len(set(valid_values))
            invalid_caught=bool(invalid_values) and any(invalid_values.count(v)>1 for v in set(invalid_values) if v)
        else:
            valid_ok = all(passes(x) for x in tests["valid"])
            invalid_caught = all(not passes(x) for x in tests["invalid"])
        result.append({"id": rule["id"], "status": "ACTIVE" if valid_ok and invalid_caught else "DRAFT",
                       "valid_seed_rows_pass": valid_ok, "invalid_seed_rows_caught": invalid_caught})
    return result


def sql_rule_results(data: dict, month: str = "2026-10") -> dict[str, tuple[int, int]]:
    """Run the same wealth rules as readable SQL over an in-memory SQLite snapshot."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE wealth (record_id TEXT, snapshot_month TEXT, client_id TEXT, account_id TEXT, risk_rating TEXT, kyc_status TEXT, booking_country TEXT, account_status TEXT, client_segment TEXT, parent_client_id TEXT)")
    conn.executemany("INSERT INTO wealth VALUES (:id,:snapshot_month,:client_id,:account_id,:risk_rating,:kyc_status,:booking_country,:account_status,:client_segment,:parent_client_id)", data["wealth"]["records"])
    conn.execute("CREATE TABLE rule_scope AS SELECT * FROM wealth WHERE snapshot_month = ?", (month,))
    results = {}
    for rule in data["wealth_rules"]["rules"]:
        sql = (SQL_DIR / f"{rule['id'].lower()}.sql").read_text(encoding="utf-8")
        failures = conn.execute(sql).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM rule_scope").fetchone()[0]
        results[rule["id"]] = (total - len(failures), total)
    conn.close()
    return results


def entity_sql_rule_results(ops_data: dict) -> dict[str, tuple[int, int]]:
    """Run the entity-domain rule queries and return numerators in scorecard units."""
    conn=sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE entities (record_id TEXT, registration_key TEXT, legal_name TEXT, entity_type TEXT, jurisdiction TEXT, parent_key TEXT)")
    conn.executemany("INSERT INTO entities VALUES (?,?,?,?,?,?)",[(r["id"],r["fields"].get("registration_key"),r["fields"].get("legal_name"),r["entity_type"],r["fields"].get("jurisdiction"),r["fields"].get("parent_key")) for r in ops_data["entity_records"]])
    allowed=ops_data["dq_rules"]["jurisdiction_allowed_values"]
    conn.create_function("name_similarity",2,lambda a,b:SequenceMatcher(None,re.sub(r"\s+"," ",(a or "").lower()).strip(),re.sub(r"\s+"," ",(b or "").lower()).strip()).ratio())
    conn.execute("CREATE TEMP TABLE allowed_jurisdictions (code TEXT)")
    conn.executemany("INSERT INTO allowed_jurisdictions VALUES (?)",[(x,) for x in allowed])
    rules={x["id"]:x for x in ops_data["dq_rules"]["rules"]}
    results={}
    for rid in ("DQ-C01","DQ-C02","DQ-C03","DQ-C04","DQ-C05"):
        failures=(SQL_DIR/f"{rid.lower()}.sql").read_text(encoding="utf-8")
        rows=conn.execute(failures).fetchall()
        if rid=="DQ-C03":
            denominator=conn.execute("SELECT COUNT(*) FROM (SELECT registration_key FROM entities WHERE registration_key IS NOT NULL GROUP BY registration_key HAVING COUNT(*)>1)").fetchone()[0]
            numerator=len(rows)
        elif rid=="DQ-C04":
            denominator=conn.execute("SELECT COUNT(*) FROM entities WHERE parent_key IS NOT NULL AND parent_key != ''").fetchone()[0]
            numerator=denominator-len(rows)
        else:
            denominator=conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            numerator=denominator-len(rows)
        results[rid]=(numerator,denominator)
    conn.close()
    return results


def cde_readiness(data: dict, entity_metrics: list[dict], month: str = "2026-10") -> list[dict]:
    wealth_metrics = {r["id"]: r for r in rule_results(data, month)}
    all_metrics = {r["id"]: r for r in entity_metrics}
    all_metrics.update(wealth_metrics)
    results = []
    for cde in data["cdes"]:
        reasons = []
        if not cde.get("definition"):
            reasons.append("missing business definition")
        if not cde.get("business_owner"):
            reasons.append("missing named accountable owner")
        lineage = cde.get("lineage", [])
        if not lineage:
            reasons.append("lineage missing")
        else:
            if any(not x.get("action") for x in lineage): reasons.append("lineage hop missing transformation note")
            if not cde.get("downstream_consumer"): reasons.append("downstream consumer not documented")
        for rid in cde.get("quality_rules", []):
            metric = all_metrics.get(rid)
            if not metric:
                reasons.append(f"quality result unavailable: {rid}")
            elif metric["status"] != "PASS":
                reasons.append(f"quality rule not passing: {rid} ({metric['status']})")
        results.append({"cde_id": cde["id"], "name": cde["name"], "ready": not reasons, "reasons": reasons})
    return results


def adjudicate_access(request: dict, owner_approver: str, approved_fields: list[str]) -> dict:
    if owner_approver == request["requester"]:
        raise ValueError("requester cannot approve their own data access request")
    if request.get("status") == "PENDING":
        return {**request, "status": "PENDING", "granted_fields": [], "decision_owner": owner_approver,
                "reason": "Awaiting data-owner decision; no fields are granted in this synthetic queue."}
    requested = set(request["requested_fields"])
    allowed = requested.intersection(approved_fields)
    denied = requested - allowed
    if not allowed:
        return {**request, "status": "DENIED", "granted_fields": [], "decision_owner": owner_approver,
                "reason": "No requested fields are within the approved purpose scope."}
    if denied:
        return {**request, "status": "PARTIALLY_GRANTED", "granted_fields": sorted(allowed),
                "decision_owner": owner_approver, "reason": "Fields outside purpose scope were narrowed: " + ", ".join(sorted(denied))}
    return {**request, "status": "APPROVED", "granted_fields": sorted(allowed),
            "decision_owner": owner_approver, "reason": "Requested fields align to the stated purpose."}


def access_decisions(data: dict) -> list[dict]:
    out = []
    for row in data["access"]["requests"]:
        out.append(adjudicate_access(row, row["decision_owner"], row["scope_fields"]))
    return out


def scorecards(data: dict) -> dict:
    rows = data["wealth"]["records"]
    def period(start: str, end: str, label: str):
        selected = [r for r in rows if start <= r["snapshot_month"] <= end]
        by_country = defaultdict(list)
        for row in selected: by_country[row["booking_country"]].append(row)
        out = []
        for country, country_rows in sorted(by_country.items()):
            for rule in data["wealth_rules"]["rules"]:
                if rule["kind"] == "completeness": passing = [r for r in country_rows if r.get(rule["field"]) not in (None, "")]
                elif rule["kind"] == "validity": passing = [r for r in country_rows if r.get(rule["field"]) in rule["allowed_values"]]
                elif rule["kind"] == "uniqueness":
                    counts = Counter(r.get(rule["field"]) for r in country_rows)
                    passing = [r for r in country_rows if r.get(rule["field"]) and counts[r[rule["field"]]] == 1]
                else:
                    known = {r["client_id"] for r in country_rows}
                    passing = [r for r in country_rows if not r.get(rule["field"]) or r[rule["field"]] in known]
                out.append({"period": label, "country": country, "rule_id": rule["id"], "metric": rule["name"],
                            "numerator": len(passing), "denominator": len(country_rows), "owner": rule["owner_role"],
                            "source": "synthetic wealth_records.json", "value": len(passing)/len(country_rows) if country_rows else None})
        return out
    monthly = period("2026-10", "2026-10", "2026-10")
    prior_month = period("2026-09", "2026-09", "2026-09")
    quarterly = period("2026-08", "2026-09", "2026-Q3 (Aug-Sep partial)")
    # The included snapshots do not cover a full prior quarter. Show the partial Q3
    # aggregate without inventing a quarter-over-quarter trend; monthly trends use
    # the adjacent September and October snapshots instead.
    def with_trend(current, previous):
        prev = {(r["country"], r["rule_id"]): r for r in previous}
        for row in current:
            old = prev.get((row["country"], row["rule_id"]))
            row["prior_value"] = old["value"] if old else None
            row["trend_pp"] = None if not old else round((row["value"] - old["value"]) * 100, 1)
        return current
    quarterly = [{**row, "prior_value": None, "trend_pp": None} for row in quarterly]
    return {"monthly": with_trend(monthly, prior_month), "quarterly": quarterly,
            "executive_summary": executive_summary(with_trend(list(monthly), prior_month))}


def executive_summary(metrics: list[dict]) -> list[str]:
    deteriorations = sorted((m for m in metrics if m.get("trend_pp") is not None and m["trend_pp"] < 0), key=lambda x:x["trend_pp"])
    open_exceptions = [x for x in load()["dq_exceptions"] if x["status"] != "CLOSED"]
    summary = [f"Deterioration: {m['country']} {m['metric']} fell by {abs(m['trend_pp']):.1f} pp vs prior period." for m in deteriorations[:3]]
    if not summary: summary.append("No country-level deterioration is indicated by the included synthetic monthly snapshots.")
    summary += [f"Open exception: {x['id']} ({x['severity']}) owned by {x['owner']}" for x in open_exceptions[:3]]
    summary.append("Decision needed: confirm owners and dates for overdue or escalated exceptions; validate illustrative thresholds with business owners before operational use.")
    return summary


def lineage_findings(data: dict) -> list[dict]:
    out=[]
    for cde in data["cdes"]:
        issues=[]
        hops=cde.get("lineage", [])
        if not hops: issues.append("lineage has no hops")
        if any(not h.get("system") or not h.get("field") for h in hops): issues.append("hop missing source/target field")
        if any(not h.get("action") for h in hops): issues.append("hop missing transformation note")
        if not cde.get("downstream_consumer"): issues.append("no downstream consumer recorded")
        if issues: out.append({"cde_id":cde["id"],"issues":issues,"owner":cde.get("business_owner") or "UNASSIGNED"})
    return out


def audit_report(data: dict, entity_metrics: list[dict]) -> dict:
    gaps=[]
    timestamp=AS_OF_TIMESTAMP
    for cde in data["cdes"]:
        if not cde.get("business_owner"):
            gaps.append({"type":"CDE_WITHOUT_OWNER","id":cde["id"],"evidence":"business_owner is empty","owner":"UNASSIGNED","status":"OPEN","timestamp":timestamp})
    open_rules={x["rule_id"] for x in data["dq_exceptions"] if x["status"]!="CLOSED"}
    metrics={x["id"]:x for x in entity_metrics}
    metrics.update({x["id"]:x for x in rule_results(data)})
    triage_by_rule={x["rule_id"]:x for x in triage_failures(data)}
    for rid,m in metrics.items():
        if m["status"]=="BREACH" and rid not in open_rules:
            failing=triage_by_rule.get(rid,{}).get("failing_rows",m.get("evidence_records",[]))
            gaps.append({"type":"BREACH_WITHOUT_EXCEPTION","id":rid,"evidence":f"rule {rid}; {m['numerator']}/{m['denominator']} passing; failing rows {', '.join(failing) or 'see metric evidence'}; status BREACH","owner":m.get("owner","synthetic role"),"status":"OPEN","timestamp":timestamp})
    for ex in data["dq_exceptions"]:
        if ex["status"]!="CLOSED" and ex.get("due_at") and ex["due_at"] < AS_OF.isoformat():
            gaps.append({"type":"OVERDUE_EXCEPTION","id":ex["id"],"evidence":f"due {ex['due_at']}; opened {ex['opened_at']}; rule {ex['rule_id']}; source rows {', '.join(ex.get('record_ids', []))}","owner":ex["owner"],"status":ex["status"],"timestamp":timestamp})
    for x in lineage_findings(data):
        gaps.append({"type":"LINEAGE_GAP","id":x["cde_id"],"evidence":"; ".join(x["issues"]),"owner":x["owner"],"status":"OPEN","timestamp":timestamp})
    triage=triage_failures(data)
    return {"label":"Synthetic audit-support report; illustrative evidence only.","as_of":AS_OF_TIMESTAMP,"gaps":gaps,"triage":triage,
            "effort_estimate":{"manual_steps_avoided":len(triage)*3,"assumption":"Illustrative estimate: each grouped rule/root-cause packet pre-fills three manual steps (finding the rule, locating failing rows, copying evidence); no time saving has been measured."}}


def triage_failures(data: dict) -> list[dict]:
    rows=data["wealth"]["records"]
    groups=[]
    for rule in rule_results(data):
        if rule["status"]!="BREACH": continue
        failures=[]
        counts=Counter(row.get(rule["field"]) for row in rows) if rule["kind"] == "uniqueness" else None
        for row in rows:
            value=row.get(rule["field"])
            ok=(value not in (None, "") if rule["kind"]=="completeness" else value in rule.get("allowed_values",[]) if rule["kind"]=="validity" else bool(value) and counts[value] == 1 if rule["kind"]=="uniqueness" else not value or value in {r["client_id"] for r in rows})
            if not ok: failures.append(row["id"])
        groups.append({"rule_id":rule["id"],"root_cause":rule["kind"],"failing_rows":failures,"owner":rule["owner_role"],
                       "due_date":(AS_OF+timedelta(days=5)).isoformat(),"evidence":f"{rule['numerator']}/{rule['denominator']} passing; source data/mdm/wealth_records.json"})
    return groups


def as_text(data: dict, entity_metrics: list[dict]) -> str:
    readiness=cde_readiness(data,entity_metrics)
    cards=scorecards(data)
    product=data["product"]["catalogue"]
    contract=data["product"]["contract"]
    lines=[f"Personal governed-data-product prototype · synthetic records · illustrative targets; no model used · scenario as of {AS_OF_TIMESTAMP}.","",
           "## Data product catalogue",
           f"Name: {product['name']}",f"Owner: {product['owner_role']}",f"Domain: {product['domain']}",
           f"Version: {contract['version']}",f"Refresh: {contract['refresh_cadence']}",f"Change policy: {contract['change_policy']}","",
           "Schema (field · type · CDE)","| Field | Type | CDE |","|---|---|---|"]
    for field in contract["schema"]:
        lines.append(f"| {field['name']} | {field['type']} | {', '.join(field['cde_links']) or '—'} |")
    lines += ["","## Data contract and AI-ready status (readiness flag only)"]
    lines += [f"{x['cde_id']} {x['name']}: {'READY' if x['ready'] else 'NOT READY'}"+(" · "+"; ".join(x['reasons']) if x['reasons'] else "") for x in readiness]
    lines += ["","## Access request queue (synthetic; owner decision is illustrative)"]
    lines += [f"{x['id']} {x['status']} · requester {x['requester']} · purpose {x['purpose']} · granted {', '.join(x['granted_fields']) or 'none'} · {x['reason']}" for x in access_decisions(data)]
    lines += ["","## Business glossary"]
    lines += [f"{x['term']} ({x['status']} v{x['version']}) — {x['definition']} · linked: {', '.join(x['cde_ids'])}" for x in data['glossary']['terms']]
    lines += ["","## Consumer adoption metrics (synthetic; illustrative, not measured)"]
    lines += [f"{m['name']}: {m['numerator']}/{m['denominator']} = {m['value']} {m['unit']} · {m['definition']} Source: {m['source']}" for m in data['product']['contract']['adoption_metrics']]
    lines += ["","## Lineage completeness review"]
    findings=lineage_findings(data)
    lines += [f"{x['cde_id']} · owner {x['owner']} · {'; '.join(x['issues'])}" for x in findings] or ["No lineage gaps found in this synthetic snapshot."]
    lines += ["","Regulatory relevance tags below are illustrative mappings only, not statements of regulatory requirements."]
    lines += [f"{c['id']}: {', '.join(c.get('regulatory_tags', []))}" for c in data['cdes'] if c.get('regulatory_tags')]
    for label,key in (("Monthly","monthly"),("Quarterly","quarterly")):
        lines += ["",f"## {label} country scorecard (synthetic / illustrative)"]
        lines += [f"{x['period']} {x['country']} {x['rule_id']}: {x['numerator']}/{x['denominator']} · trend {format_trend(x['trend_pp'])} · owner {x['owner']}" for x in cards[key]]
    lines += ["","## Deterministic executive summary"]+cards['executive_summary']
    lines += ["","Rule activation checks"]+[f"{x['id']}: {x['status']} · valid seeds pass={x['valid_seed_rows_pass']} · invalid seeds caught={x['invalid_seed_rows_caught']}" for x in validate_rules(data)]
    return "\n".join(lines)


def extra_html(data: dict, entity_metrics: list[dict]) -> str:
    esc=lambda x:html.escape(str(x))
    readiness=cde_readiness(data,entity_metrics)
    ready_rows="".join(f"<tr><td>{esc(x['cde_id'])}</td><td>{esc(x['name'])}</td><td>{'READY' if x['ready'] else 'NOT READY'}</td><td>{esc('; '.join(x['reasons']) or 'All criteria met')}</td></tr>" for x in readiness)
    access="".join(f"<tr><td>{esc(x['id'])}</td><td>{esc(x['consumer_team'])}</td><td>{esc(x['purpose'])}</td><td>{esc(x['status'])}</td><td>{esc(', '.join(x['granted_fields']) or 'None')}</td><td>{esc(x['reason'])}</td></tr>" for x in access_decisions(data))
    glossary="".join(f"<tr><td>{esc(x['term'])}</td><td>{esc(x['definition'])}</td><td>{esc(x['owner_role'])}</td><td>{esc(x['status'])} v{esc(x['version'])}</td><td>{esc(', '.join(x['cde_ids']))}</td></tr>" for x in data['glossary']['terms'])
    adoption="".join(f"<tr><td>{esc(x['name'])}</td><td>{x['numerator']}/{x['denominator']}</td><td>{x['value']} {esc(x['unit'])}</td><td>{esc(x['definition'])}</td><td>{esc(x['source'])}</td></tr>" for x in data['product']['contract']['adoption_metrics'])
    lineage_gaps="".join(f"<li><b>{esc(x['cde_id'])}</b> · owner {esc(x['owner'])} · {esc('; '.join(x['issues']))}</li>" for x in lineage_findings(data)) or "<li>No gaps found in this synthetic snapshot.</li>"
    regulatory_tags="".join(f"<tr><td>{esc(c['id'])}</td><td>{esc(c['name'])}</td><td>{esc(', '.join(c.get('regulatory_tags', [])))}</td></tr>" for c in data['cdes'] if c.get('regulatory_tags'))
    scores=scorecards(data)
    def score_rows(key):
        def trend_text(row):
            return format_trend(row["trend_pp"])
        return "".join(f"<tr><td>{esc(x['period'])}</td><td>{esc(x['country'])}</td><td>{esc(x['metric'])}</td><td>{x['numerator']}/{x['denominator']}</td><td>{trend_text(x)}</td><td>{esc(x['owner'])}</td><td>{esc(x['source'])}</td></tr>" for x in scores[key])
    executive="".join(f"<li>{esc(x)}</li>" for x in scores['executive_summary'])
    return f"""<h2 id='data-product'>Governed data product (synthetic)</h2><p>Catalogue, data contract and purpose-limited owner-reviewed access requests. This is a demonstration queue; it does not enforce access.</p><section class='panel'><h3>{esc(data['product']['catalogue']['name'])}</h3><p>{esc(data['product']['catalogue']['description'])}</p><p><b>Version:</b> {esc(data['product']['contract']['version'])} · <b>Refresh:</b> {esc(data['product']['contract']['refresh_cadence'])} · <b>Change policy:</b> {esc(data['product']['contract']['change_policy'])}</p><p><b>Schema:</b> {esc(', '.join(x['name'] for x in data['product']['contract']['schema']))}</p><p><b>Quality SLOs (illustrative):</b> {esc('; '.join(x['rule_id']+': '+str(x['target']) for x in data['product']['contract']['quality_slos']))}</p></section>
<h3>AI-ready criteria flag (no AI model)</h3><div class='table-wrap'><table><thead><tr><th>CDE</th><th>Name</th><th>Status</th><th>Criterion gaps</th></tr></thead><tbody>{ready_rows}</tbody></table></div>
<h3>Consumer access queue (synthetic)</h3><div class='table-wrap'><table><thead><tr><th>Request</th><th>Team</th><th>Purpose</th><th>Status</th><th>Fields granted</th><th>Reason</th></tr></thead><tbody>{access}</tbody></table></div>
<h2>Business glossary (synthetic)</h2><div class='table-wrap'><table><thead><tr><th>Term</th><th>Definition</th><th>Owner role</th><th>Status / version</th><th>CDE links</th></tr></thead><tbody>{glossary}</tbody></table></div>
<h3>Consumer adoption metrics (synthetic; illustrative, not measured)</h3><div class='table-wrap'><table><thead><tr><th>Measure</th><th>Numerator / denominator</th><th>Illustrative value</th><th>Definition</th><th>Source</th></tr></thead><tbody>{adoption}</tbody></table></div>
<h3>Lineage completeness and illustrative relevance tags</h3><ul>{lineage_gaps}</ul><p class='muted'>Any programme or regulatory relevance tag is an illustrative mapping only; it does not state regulatory requirements.</p><div class='table-wrap'><table><thead><tr><th>CDE</th><th>Name</th><th>Illustrative relevance tag</th></tr></thead><tbody>{regulatory_tags}</tbody></table></div>
<h2>Country data-quality scorecards</h2><p>Monthly and quarterly views with explicit numerator, denominator, trend and synthetic owner. Targets and results are illustrative.</p><h3>Monthly</h3><div class='table-wrap'><table><thead><tr><th>Period</th><th>Country</th><th>Metric</th><th>Pass / total</th><th>Trend</th><th>Owner</th><th>Source</th></tr></thead><tbody>{score_rows('monthly')}</tbody></table></div><h3>Quarterly</h3><div class='table-wrap'><table><thead><tr><th>Period</th><th>Country</th><th>Metric</th><th>Pass / total</th><th>Trend</th><th>Owner</th><th>Source</th></tr></thead><tbody>{score_rows('quarterly')}</tbody></table></div><section class='panel'><b>Deterministic executive summary</b><ul>{executive}</ul></section>"""


def audit_markdown(data: dict, entity_metrics: list[dict]) -> str:
    report=audit_report(data,entity_metrics)
    lines=["# Synthetic audit-support evidence pack","",report['label'],f"As of {report['as_of']} (illustrative scenario).","","## Control gaps"]
    if not report['gaps']: lines.append("No control gaps found in this synthetic snapshot.")
    for x in report['gaps']:
        lines.append(f"- **{x['type']} {x['id']}** — {x['evidence']}. Observed as of {x['timestamp']}. Owner: {x['owner']}; remediation status: {x['status']}.")
    lines += ["","## Deterministic exception triage (suggestions for steward review)"]
    for x in report['triage']:
        lines.append(f"- {x['rule_id']} / {x['root_cause']}: failing rows {', '.join(x['failing_rows']) or 'none'}; proposed owner {x['owner']}; proposed due {x['due_date']}; evidence {x['evidence']}.")
    est=report['effort_estimate']
    lines += ["",f"Illustrative manual steps avoided estimate: {est['manual_steps_avoided']} ({est['assumption']})","","No real audit, control test, remediation or time saving is claimed."]
    return "\n".join(lines)
