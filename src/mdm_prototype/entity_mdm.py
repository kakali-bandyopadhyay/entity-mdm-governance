"""Synthetic investment-entity mastering vertical slice.

Recommendations are deterministic and explainable. A MATCH is only a candidate: a distinct maker and checker must
approve a merge. Unresolved conflicts in identity or parent fields remain open instead of being silently overwritten.
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from .data import ROOT

MDM_DATA = ROOT / "data" / "mdm"
LABEL = "Personal MDM prototype. Synthetic records, illustrative rules; not based on any firm's systems or data."


def load(data_dir: Path = MDM_DATA) -> dict:
    read = lambda name: json.loads((data_dir / name).read_text(encoding="utf-8-sig"))
    data = {"records_file": read("records.json"), "rules": read("rules.json"),
            "evaluation": read("evaluation_pairs.json"), "decisions": read("steward_decisions.json"),
            "data_dir": data_dir}
    records = data["records_file"]["records"]
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate MDM record ID")
    sources = set(data["records_file"]["sources"])
    for r in records:
        if r["source"] not in sources:
            raise ValueError(f"{r['id']} has unknown source {r['source']}")
        if not r.get("entity_type") or not r.get("fields", {}).get("legal_name"):
            raise ValueError(f"{r['id']} needs entity_type and legal_name")
    known = set(ids)
    for p in data["evaluation"]["pairs"]:
        if p["left"] not in known or p["right"] not in known:
            raise ValueError(f"{p['id']} refers to an unknown record")
    return data


def normalize_name(value: str, rules: dict) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    tokens = re.findall(r"[a-z0-9]+", value)
    suffixes = set(rules["legal_suffixes"])
    while tokens and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens)


def compare(a: dict, b: dict, rules: dict) -> dict:
    na, nb = normalize_name(a["fields"]["legal_name"], rules), normalize_name(b["fields"]["legal_name"], rules)
    similarity = SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0
    ka, kb = a["fields"].get("registration_key"), b["fields"].get("registration_key")
    same_type = a["entity_type"] == b["entity_type"]
    same_country = a["fields"].get("jurisdiction") == b["fields"].get("jurisdiction")
    result = {"left": a["id"], "right": b["id"], "name_similarity": round(similarity, 3),
              "verdict": "NO_MATCH", "score": round(similarity * 100), "reason": "name similarity below review threshold"}
    if ka and kb and ka != kb:
        result.update(verdict="NO_MATCH", reason="both sources provide different synthetic registration keys")
    elif ka and kb and ka == kb:
        if not same_type or not same_country:
            result.update(verdict="EXCEPTION",
                          reason="same synthetic key but entity type or jurisdiction conflicts; merge blocked")
        elif similarity < rules["same_key_name_floor"]:
            result.update(verdict="EXCEPTION",
                          reason="same synthetic key but legal names materially conflict; source correction required")
        else:
            result.update(verdict="MATCH",
                          reason="same synthetic key, entity type and jurisdiction; steward approval still required")
    elif not same_type or not same_country:
        result.update(verdict="NO_MATCH", reason="entity type or jurisdiction differs")
    elif similarity >= rules["name_review_threshold"]:
        result.update(verdict="REVIEW",
                      reason="name similarity meets review threshold, but no shared registration key proves identity")
    return result


def _records(data: dict) -> dict[str, dict]:
    return {r["id"]: r for r in data["records_file"]["records"]}


def _source_rank(rules: dict, field: str, source: str) -> int:
    order = rules["source_precedence"].get(field, [])
    return order.index(source) if source in order else len(order) + 100


def survivorship(members: list[dict], rules: dict) -> dict:
    fields = sorted({k for r in members for k in r["fields"]} | {"entity_type"})
    output, exceptions = {}, []
    unresolved = set(rules["unresolved_conflict_fields"])
    for field in fields:
        values = []
        for r in members:
            value = r["entity_type"] if field == "entity_type" else r["fields"].get(field)
            if value is not None and value != "":
                values.append({"value": value, "record": r["id"], "source": r["source"],
                               "source_record": r["source_record"], "rank": _source_rank(rules, field, r["source"]),
                               "updated_at": r["updated_at"]})
        if not values:
            output[field] = {"state": "MISSING", "value": None, "selected_from": None, "alternatives": []}
            continue
        best_rank = min(x["rank"] for x in values)
        best = [x for x in values if x["rank"] == best_rank]
        distinct_best = {str(x["value"]) for x in best}
        all_values = {str(x["value"]) for x in values}
        ordered = sorted(values, key=lambda x: (x["rank"], x["updated_at"], x["record"]))
        if field in unresolved and len(all_values) > 1:
            exceptions.append({"type": "FIELD_CONFLICT", "field": field, "state": "OPEN",
                               "values": [{"value": x["value"], "source": x["source"], "record": x["record"]} for x in ordered]})
            output[field] = {"state": "NEEDS_STEWARD_DECISION", "value": None, "selected_from": None,
                             "proposed_value": ordered[0]["value"], "proposed_from": ordered[0]["source"],
                             "alternatives": ordered}
        elif len(distinct_best) > 1:
            exceptions.append({"type": "EQUAL_PRIORITY_CONFLICT", "field": field, "state": "OPEN",
                               "values": [{"value": x["value"], "source": x["source"], "record": x["record"]} for x in best]})
            output[field] = {"state": "NEEDS_STEWARD_DECISION", "value": None, "selected_from": None,
                             "alternatives": best}
        else:
            winner = sorted(best, key=lambda x: (x["updated_at"], x["record"]))[-1]
            alternatives = [x for x in ordered if x["value"] != winner["value"]]
            output[field] = {"state": "SELECTED", "value": winner["value"],
                             "selected_from": {"source": winner["source"], "record": winner["record"],
                                               "source_record": winner["source_record"]},
                             "alternatives": alternatives}
    return {"fields": output, "exceptions": exceptions}


def master_records(data: dict) -> list[dict]:
    records = _records(data)
    out = []
    for group in data["decisions"]["merge_groups"]:
        if group["status"] != "APPROVED":
            continue
        if data["rules"].get("two_person_approval") and group["maker"] == group["checker"]:
            continue
        members = [records[rid] for rid in group["members"]]
        resolved = survivorship(members, data["rules"])
        out.append({"id": group["master_id"], "member_ids": group["members"], "decision": group,
                    **resolved})
    return out


def evaluate(data: dict) -> dict:
    records = _records(data)
    rows = []
    for pair in data["evaluation"]["pairs"]:
        result = compare(records[pair["left"]], records[pair["right"]], data["rules"])
        rows.append({**pair, **result, "correct": result["verdict"] == pair["expected"]})
    n = len(rows)
    counts = {key: sum(r["verdict"] == key for r in rows) for key in ("MATCH", "REVIEW", "NO_MATCH", "EXCEPTION")}
    matches_expected = sum(r["expected"] == "MATCH" for r in rows)
    exact_match = sum(r["expected"] == "MATCH" and r["verdict"] == "MATCH" for r in rows)
    auto_precision = f"{exact_match}/{counts['MATCH']}" if counts["MATCH"] else "n/a"
    auto_recall = f"{exact_match}/{matches_expected}" if matches_expected else "n/a"
    return {"rows": rows, "summary": {"pairs": n, "decision_accuracy": f"{sum(r['correct'] for r in rows)}/{n}",
            "match_suggestion_precision": auto_precision, "match_suggestion_recall": auto_recall,
            "false_match_suggestions": sum(r["verdict"] == "MATCH" and r["expected"] != "MATCH" for r in rows),
            "outcomes": counts,
            "label": data["evaluation"]["label"]}}


def pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def as_text(data: dict, *, evaluation: bool = False) -> str:
    lines = [LABEL]
    if evaluation:
        result = evaluate(data)
        lines += ["", "## Synthetic pair evaluation", result["summary"]["label"],
                  f"Pairs: {result['summary']['pairs']} · decision agreement: {result['summary']['decision_accuracy']}",
                  f"Match-suggestion precision: {result['summary']['match_suggestion_precision']} · recall: {result['summary']['match_suggestion_recall']}",
                  f"False match suggestions: {result['summary']['false_match_suggestions']}", "",
                  "Pair | Expected | Proposed | Name similarity | Rationale", "--- | --- | --- | ---: | ---"]
        lines.extend(f"{r['left']}↔{r['right']} | {r['expected']} | {r['verdict']} | {r['name_similarity']:.3f} | {r['reason']}" for r in result["rows"])
        lines += ["", "The pairs are synthetic and author-labelled with the rules; these figures are a demonstration, not independent validation."]
        return "\n".join(lines)

    records = _records(data)
    pair_ids = [("R001", "R002"), ("R009", "R010"), ("R007", "R008"), ("R011", "R012")]
    lines += ["", "## Matching decisions (recommendations only)"]
    for left, right in pair_ids:
        r = compare(records[left], records[right], data["rules"])
        lines.append(f"{left} ↔ {right}: {r['verdict']} · name similarity {r['score']} · {r['reason']}")
    lines += ["", "## Golden-record preview (approved cluster only)"]
    masters = master_records(data)
    for m in masters:
        lines.append(f"{m['id']} ← {', '.join(m['member_ids'])} · {len(m['exceptions'])} open field conflict(s)")
        for field, v in m["fields"].items():
            if v["state"] == "SELECTED":
                origin = v["selected_from"]
                lines.append(f"  {field}: {v['value']}  [{origin['source']} / {origin['source_record']}]")
            elif v["state"] == "NEEDS_STEWARD_DECISION":
                lines.append(f"  {field}: PENDING steward decision · proposed {v.get('proposed_value')} from {v.get('proposed_from')}")
    lines += ["", "## Steward queue"]
    for item in data["decisions"]["pair_reviews"]:
        lines.append(f"{item['status']}: {' ↔ '.join(item['pair'])} · owner {item['owner']} · {item['reason']}")
    for item in data["decisions"]["field_reviews"]:
        lines.append(f"{item['status']}: {item['master_id']} {item['field']} · due {item['due']} · {item['reason']}")
    lines += ["", "## Approval and audit evidence"]
    for g in data["decisions"]["merge_groups"]:
        lines.append(f"{g['id']} {g['status']}: maker {g['maker']} → checker {g['checker']} at {g['at']}; {g['rationale']}")
    lines += ["", "No record is merged from a name score alone. Candidate decisions, source values and unresolved exceptions remain visible."]
    return "\n".join(lines)
