from mdm_prototype import mdm_ops


def test_service_scorecard_has_explicit_denominators_and_expected_synthetic_values():
    report = mdm_ops.build(mdm_ops.load())
    metrics = {m["id"]: m for m in report["metrics"]}
    assert len(report["items"]) == 13
    assert len(report["completed"]) == 8
    assert len(report["open"]) == 5
    assert metrics["on_time_completion_rate"]["numerator"] == 5
    assert metrics["on_time_completion_rate"]["denominator"] == 8
    assert metrics["first_pass_yield"]["numerator"] == 6
    assert metrics["first_pass_yield"]["denominator"] == 8
    assert metrics["rework_rate"]["numerator"] == 2
    assert metrics["open_overdue"]["numerator"] == 1
    assert metrics["aged_backlog"]["numerator"] == 1
    assert report["handoffs"] == 14
    assert all(m["definition"] and m["source"] and m["owner"] for m in report["metrics"])
    handoff_improvement = next(x for x in report["improvements"] if x["id"] == "IMP-03")
    assert handoff_improvement["linked_count"] == 11


def test_cde_registry_lineage_dq_metrics_and_exception_evidence_are_explicit():
    report = mdm_ops.build(mdm_ops.load())
    assert len(report["cdes"]) == 10
    assert all(c["definition"] and c["business_owner"] and c["trusted_source"] and c["lineage"] for c in report["cdes"])
    dq = {m["id"]: m for m in report["quality_metrics"]}
    assert (dq["DQ-C01"]["numerator"], dq["DQ-C01"]["denominator"]) == (25, 30)
    assert (dq["DQ-C02"]["numerator"], dq["DQ-C02"]["denominator"]) == (30, 30)
    assert (dq["DQ-C03"]["numerator"], dq["DQ-C03"]["denominator"]) == (2, 7)
    assert (dq["DQ-C04"]["numerator"], dq["DQ-C04"]["denominator"]) == (3, 4)
    assert (dq["DQ-C05"]["numerator"], dq["DQ-C05"]["denominator"]) == (30, 30)
    assert all(m["definition"] and m["source"] and m["owner"] and m["status"] for m in dq.values())
    assert report["audit_metric"]["numerator"] == report["audit_metric"]["denominator"] == 2
    assert {x["id"] for x in report["exceptions"] if x["status_at_cutoff"] != "CLOSED"} == {"DQE-003", "DQE-004", "DQE-005"}
    assert report["operating_model"]["continuity_scenarios"][0]["validation"].startswith("TABLETOP_REQUIRED")


def test_cutoff_recomputes_open_queue_without_future_cases():
    report = mdm_ops.build(mdm_ops.load(), "2026-10-18T12:00:00Z")
    assert all(item["created_at"] <= "2026-10-18T12:00:00Z" for item in report["items"])
    assert len(report["items"]) < 12
    assert len(report["completed"]) < 8
    before_completion = next(item for item in report["open"] if item["id"] == "MDM-008")
    assert before_completion["status_at_cutoff"] == "IN_PROGRESS (inferred)"


def test_html_dashboard_labels_simulation_and_does_not_claim_capacity():
    page = mdm_ops.as_html(mdm_ops.build(mdm_ops.load()))
    assert "synthetic scenario" in page
    assert "not capacity or utilization" in page
    assert "not based on or connected to any firm's systems, data, processes or approved policies" in page
    assert "For an as-of cutoff before a recorded completion" in page
    assert "Critical data elements and lineage" in page
    assert "Exception remediation and audit trail" in page
    assert "Continuity scenarios" in page
