from mdm_prototype import entity_mdm


def test_pair_evaluation_is_labelled_and_reproducible():
    result = entity_mdm.evaluate(entity_mdm.load())
    assert result["summary"]["pairs"] == 20
    assert result["summary"]["decision_accuracy"] == "20/20"
    assert result["summary"]["label"].startswith("Synthetic, author-labelled")


def test_matching_and_master_preview_preserve_steward_boundaries():
    data = entity_mdm.load()
    records = {r["id"]: r for r in data["records_file"]["records"]}
    assert entity_mdm.compare(records["R007"], records["R008"], data["rules"])["verdict"] == "EXCEPTION"
    assert entity_mdm.compare(records["R009"], records["R010"], data["rules"])["verdict"] == "REVIEW"
    assert any(field["state"] == "NEEDS_STEWARD_DECISION"
               for master in entity_mdm.master_records(data) for field in master["fields"].values())
