import re
from pathlib import Path

import pytest

from mdm_prototype import entity_mdm, mdm_ops, product


def test_sql_and_python_wealth_rules_match_at_monthly_cutoff():
    data = product.load()
    py = {x["id"]: (x["numerator"], x["denominator"]) for x in product.rule_results(data, "2026-10")}
    assert product.sql_rule_results(data, "2026-10") == py


def test_sql_and_python_entity_rules_match():
    ops = mdm_ops.load()
    py = {x["id"]:(x["numerator"],x["denominator"]) for x in mdm_ops.build(ops)["quality_metrics"]}
    assert product.entity_sql_rule_results(ops) == {key:py[key] for key in ("DQ-C01","DQ-C02","DQ-C03","DQ-C04","DQ-C05")}


def test_all_cdes_link_to_approved_glossary_terms():
    data = product.load()
    approved = {cid for term in data["glossary"]["terms"] if term["status"] == "approved" for cid in term["cde_ids"]}
    assert {c["id"] for c in data["cdes"]} <= approved


def test_all_seeded_rule_suites_pass_before_activation():
    data = product.load()
    states = product.validate_rules(data)
    assert len(states) == 5
    assert all(x["status"] == "ACTIVE" and x["valid_seed_rows_pass"] and x["invalid_seed_rows_caught"] for x in states)


def test_access_requester_cannot_approve_own_request():
    req = {"id":"T","requester":"same person","requested_fields":["x"]}
    with pytest.raises(ValueError, match="cannot approve"):
        product.adjudicate_access(req, "same person", ["x"])


def test_access_fields_outside_approved_purpose_are_narrowed():
    req = {"id":"T","requester":"consumer","requested_fields":["safe","sensitive"]}
    result = product.adjudicate_access(req, "owner", ["safe"])
    assert result["status"] == "PARTIALLY_GRANTED"
    assert result["granted_fields"] == ["safe"]
    assert "sensitive" in result["reason"]


def test_pending_access_request_grants_nothing():
    req = {"id":"T","requester":"consumer","requested_fields":["safe"],"status":"PENDING"}
    result = product.adjudicate_access(req, "owner", ["safe"])
    assert result["status"] == "PENDING" and result["granted_fields"] == []


def test_access_queue_has_explicit_decision_or_pending_reason():
    assert all(x["reason"] and x["decision_owner"] != x["requester"] for x in product.access_decisions(product.load()))


def test_country_scorecards_have_numerators_denominators_owner_and_source():
    cards = product.scorecards(product.load())
    assert cards["monthly"] and cards["quarterly"]
    assert all(x["owner"] and x["source"] and 0 <= x["numerator"] <= x["denominator"] for x in cards["monthly"] + cards["quarterly"])


def test_country_scorecard_trend_compares_prior_period():
    rows = product.scorecards(product.load())["monthly"]
    assert any(x["prior_value"] is not None and x["trend_pp"] == pytest.approx((x["value"] - x["prior_value"]) * 100, abs=0.1) for x in rows)
    assert any(x["trend_pp"] == pytest.approx(-8.3, abs=0.1) for x in rows)


def test_executive_summary_is_deterministic():
    data = product.load()
    assert product.scorecards(data)["executive_summary"] == product.scorecards(data)["executive_summary"]


def test_lineage_checker_reports_cde_without_consumer():
    data = product.load()
    findings = product.lineage_findings(data)
    assert any(x["cde_id"] == "CDE-ENTITY-TYPE" and "no downstream consumer recorded" in x["issues"] for x in findings)


def test_lineage_checker_detects_missing_transformation_note():
    data = product.load()
    target = next(x for x in data["cdes"] if x["id"] == "CDE-W-RISK")
    target["lineage"][0].pop("action")
    assert "hop missing transformation note" in next(x for x in product.lineage_findings(data) if x["cde_id"] == "CDE-W-RISK")["issues"]


def test_ai_ready_flag_explains_failing_quality_rule():
    data = product.load()
    entity = mdm_ops.build(mdm_ops.load())
    results = product.cde_readiness(data, entity["quality_metrics"])
    hierarchy = next(x for x in results if x["cde_id"] == "CDE-W-HIERARCHY")
    assert not hierarchy["ready"]
    assert any("DQ-W04" in x for x in hierarchy["reasons"])


def test_audit_pack_includes_overdue_exception_and_lineage_evidence():
    data = product.load()
    report = mdm_ops.build(mdm_ops.load())
    pack = product.audit_markdown(data, report["quality_metrics"])
    assert "OVERDUE_EXCEPTION" in pack
    assert "LINEAGE_GAP" in pack
    assert "opened" in pack and "due" in pack and "Owner:" in pack


def test_audit_pack_flags_cde_without_accountable_owner():
    data = product.load()
    cde = next(x for x in data["cdes"] if x["id"] == "CDE-W-RISK")
    cde["business_owner"] = ""
    report = product.audit_report(data, mdm_ops.build(mdm_ops.load())["quality_metrics"])
    assert any(x["type"] == "CDE_WITHOUT_OWNER" and x["id"] == "CDE-W-RISK" for x in report["gaps"])


def test_triage_prefills_owner_due_date_and_failing_row_evidence():
    triage = product.triage_failures(product.load())
    assert triage
    assert all(x["owner"] and x["due_date"] and x["evidence"] and x["failing_rows"] for x in triage)


def test_manual_effort_estimate_states_assumptions_and_is_not_measured():
    report = product.audit_report(product.load(), mdm_ops.build(mdm_ops.load())["quality_metrics"])
    estimate = report["effort_estimate"]
    assert estimate["manual_steps_avoided"] == len(report["triage"]) * 3
    assert "no time saving has been measured" in estimate["assumption"]


def test_every_data_product_schema_link_resolves_to_a_cde():
    data = product.load()
    ids = {c["id"] for c in data["cdes"]}
    assert all(set(row["cde_links"]) <= ids for row in data["product"]["contract"]["schema"])


def test_product_adoption_metrics_have_calculation_contract():
    contract = product.load()["product"]["contract"]
    metrics = contract["adoption_metrics"]
    assert {m["id"] for m in metrics} == {"ADOPT-01","ADOPT-02","ADOPT-03"}
    assert all(m["definition"] and m["source"] and m["numerator"] is not None and m["denominator"] for m in metrics)
    scenario=contract["adoption_scenario"]
    assert len(scenario["subscribed_consumer_teams"]) == metrics[0]["numerator"]
    assert len(scenario["consuming_use_cases"]) == metrics[1]["numerator"]
    assert metrics[2]["value"] == (int(scenario["first_consumption_date"][-2:])-int(scenario["publication_date"][-2:]))


def test_every_wealth_rule_has_sql_and_seeded_examples():
    data = product.load()
    for rule in data["wealth_rules"]["rules"]:
        assert (product.SQL_DIR / f"{rule['id'].lower()}.sql").is_file()
        assert rule["test_rows"]["valid"] and rule["test_rows"]["invalid"]


def test_all_synthetic_wealth_records_have_domain_and_period_keys():
    records = product.load()["wealth"]["records"]
    assert len(records) == 108
    assert {r["snapshot_month"] for r in records} == {"2026-08", "2026-09", "2026-10"}
    assert all(r["id"].startswith("W-") and r["snapshot_month"].startswith("2026-") for r in records)
    for month in ("2026-08", "2026-09", "2026-10"):
        for country in ("United States", "United Kingdom", "Singapore"):
            assert sum(r["snapshot_month"] == month and r["booking_country"] == country for r in records) == 12


def test_scorecard_denominators_and_trends_use_percentage_points():
    cards = product.scorecards(product.load())
    assert {row["denominator"] for row in cards["monthly"]} == {12}
    assert {row["denominator"] for row in cards["quarterly"]} == {24}
    assert all(row["period"] == "2026-10" for row in cards["monthly"])
    assert all(row["period"] == "2026-Q3 (Aug-Sep partial)" for row in cards["quarterly"])
    assert any("pp" in line for line in cards["executive_summary"])
    text = product.as_text(product.load(), mdm_ops.build(mdm_ops.load())["quality_metrics"])
    assert "trend -8.3 pp" in text
    assert "50.0%" not in text


def test_product_output_is_a_readable_catalogue_and_schema_summary():
    text = product.as_text(product.load(), mdm_ops.build(mdm_ops.load())["quality_metrics"])
    assert "Data product catalogue" in text and "Schema (field · type · CDE)" in text
    assert "| entity_id | string | CDE-ENTITY-KEY |" in text
    assert '"catalogue": {' not in text and '"contract": {' not in text


def test_ops_output_points_to_product_without_repeating_it():
    text = mdm_ops.as_text(mdm_ops.build(mdm_ops.load()))
    assert "python -m mdm_prototype product" in text
    assert "Data product catalogue" not in text


def test_scenario_as_of_is_consistent_across_ops_product_and_audit():
    ops_report = mdm_ops.build(mdm_ops.load())
    audit = product.audit_report(product.load(), ops_report["quality_metrics"])
    text = product.as_text(product.load(), ops_report["quality_metrics"])
    assert ops_report["as_of"] == product.AS_OF_TIMESTAMP == audit["as_of"]
    assert product.AS_OF_TIMESTAMP in text


def test_audit_pack_separates_evidence_from_observed_timestamp():
    pack = product.audit_markdown(product.load(), mdm_ops.build(mdm_ops.load())["quality_metrics"])
    assert ". Observed as of 2026-10-21T12:00:00Z." in pack


def test_regulatory_mapping_is_explicitly_labelled_illustrative():
    text = product.as_text(product.load(), mdm_ops.build(mdm_ops.load())["quality_metrics"])
    assert "illustrative mappings only" in text
    assert "not statements of regulatory requirements" in text


def test_product_cli_dashboard_section_is_renderable():
    report = mdm_ops.build(mdm_ops.load())
    page = mdm_ops.as_html(report)
    assert "Governed data product" in page
    assert "Consumer access queue" in page
    assert "Business glossary" in page
    assert "Consumer adoption metrics" in page
    assert "Lineage completeness" in page


def test_dashboard_file_matches_fresh_render():
    expected = mdm_ops.as_html(mdm_ops.build(mdm_ops.load())).replace("\r\n", "\n")
    actual = (Path(__file__).parents[1] / "docs" / "mdm_operations.html").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual == expected


def test_repo_has_no_real_firm_names_from_blocklist():
    root = Path(__file__).parents[1]
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*")
                     if p.is_file() and not ({".git", "__pycache__", ".venv", "venv", "site-packages", ".pytest_cache", "out"} & set(p.parts))
                     and p.suffix.lower() in {".md", ".py", ".html", ".json", ".sql", ".toml"})
    firms = ["Black"+"Rock", "Al"+"addin", "E"+"QT", "Black"+"stone", "D. E. "+"Shaw",
             "Ci"+"ti", "Ci"+"ti"+"group", "Swiss "+"Re", "Delo"+"itte", "P"+"wC", "Inform"+"atica",
             "Coll"+"ibra", "Nov"+"artis", "R"+"oche"]
    for firm in firms:
        flags = re.IGNORECASE if firm.lower() != ("ci"+"ti").lower() else re.IGNORECASE
        pattern = rf"\b{re.escape(firm)}\b" if firm.lower() == ("ci"+"ti").lower() else re.escape(firm)
        assert not re.search(pattern, text, flags), firm


def test_entity_queue_scorecard_is_hand_counted_from_work_items():
    data = mdm_ops.load()
    report = mdm_ops.build(data)
    as_of = report["as_of"]
    expected = [x for x in data["items"] if data["cohort_start"] <= mdm_ops._dt(x["created_at"]) <= mdm_ops._dt(as_of)]
    assert len(expected) == len(report["items"])
    assert sum(bool(x.get("completed_at")) and x["completed_at"] <= as_of for x in expected) == len(report["completed"])


def test_different_registration_keys_never_match_even_for_identical_names():
    data = entity_mdm.load()
    left = {"id":"A","entity_type":"ISSUER","fields":{"legal_name":"Same Name Ltd","jurisdiction":"GB","registration_key":"SYN-1"}}
    right = {"id":"B","entity_type":"ISSUER","fields":{"legal_name":"Same Name Ltd","jurisdiction":"GB","registration_key":"SYN-2"}}
    result = entity_mdm.compare(left,right,data["rules"])
    assert result["verdict"] == "NO_MATCH"
    assert result["score"] == 100  # name similarity is evidence, not the decision


def test_same_person_cannot_serve_as_merge_maker_and_checker():
    data = entity_mdm.load()
    group = data["decisions"]["merge_groups"][0]
    group["checker"] = group["maker"]
    assert all(master["decision"]["master_id"] != group["master_id"] for master in entity_mdm.master_records(data))


def test_exception_pair_is_never_in_an_approved_merge():
    data = entity_mdm.load()
    records = {r["id"]:r for r in data["records_file"]["records"]}
    assert entity_mdm.compare(records["R007"],records["R008"],data["rules"])["verdict"] == "EXCEPTION"
    assert not any({"R007","R008"} <= set(group["members"]) for group in data["decisions"]["merge_groups"] if group["status"] == "APPROVED")


def test_survivorship_does_not_publish_open_parent_conflict():
    data = entity_mdm.load()
    parent = next(master["fields"]["parent_key"] for master in entity_mdm.master_records(data))
    assert parent["state"] == "NEEDS_STEWARD_DECISION"
    assert parent["value"] is None


def test_as_of_earlier_than_cohort_start_has_clear_error():
    with pytest.raises(ValueError,match="on or after cohort_start"):
        mdm_ops.build(mdm_ops.load(),"2026-09-30T23:59:59Z")


def test_displayed_match_score_is_labeled_name_similarity():
    text=entity_mdm.as_text(entity_mdm.load())
    assert "name similarity" in text
    assert " · score " not in text

