import re
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "ARCHITECTURE.md"


def test_mermaid_components_are_backed_by_code_or_scenario_data():
    text = DOC.read_text(encoding="utf-8")
    diagrams = re.findall(r"```mermaid\s+(.*?)```", text, flags=re.DOTALL)
    assert len(diagrams) == 6
    joined = "\n".join(diagrams)

    # Each function label in the diagrams must remain tied to an existing implementation.
    implementations = {
        "entity_mdm.load()": ("src/mdm_prototype/entity_mdm.py", "def load("),
        "entity_mdm.compare()": ("src/mdm_prototype/entity_mdm.py", "def compare("),
        "entity_mdm.master_records()": ("src/mdm_prototype/entity_mdm.py", "def master_records("),
        "mdm_ops.load()": ("src/mdm_prototype/mdm_ops.py", "def load("),
        "mdm_ops.build()": ("src/mdm_prototype/mdm_ops.py", "def build("),
        "product.load()": ("src/mdm_prototype/product.py", "def load("),
        "product.entity_sql_rule_results()": ("src/mdm_prototype/product.py", "def entity_sql_rule_results("),
        "product.cde_readiness()": ("src/mdm_prototype/product.py", "def cde_readiness("),
        "product.scorecards()": ("src/mdm_prototype/product.py", "def scorecards("),
        "product.access_decisions()": ("src/mdm_prototype/product.py", "def access_decisions("),
        "product.audit_markdown()": ("src/mdm_prototype/product.py", "def audit_markdown("),
        "mdm_ops.as_html()": ("src/mdm_prototype/mdm_ops.py", "def as_html("),
    }
    for label, (path, token) in implementations.items():
        source = (ROOT / path).read_text(encoding="utf-8")
        assert label in joined
        assert token in source

    # Fixture, SQL, and generated artifact names in the diagrams must exist in the repo.
    artifacts = [
        "data/mdm/records.json", "rules.json", "steward_decisions.json",
        "cde_registry.json", "work_items.json", "data_products.json", "access_requests.json",
        "improvement_backlog.json", "operating_model.json", "dq_exceptions.json",
        "sql/dq_rules/*.sql", "CDE-ENTITY-KEY",
    ]
    for label in artifacts:
        assert label in joined
    assert (ROOT / "data/mdm/records.json").exists()
    assert (ROOT / "data/mdm/steward_decisions.json").exists()
    assert (ROOT / "data/mdm/improvement_backlog.json").exists()
    assert list((ROOT / "sql/dq_rules").glob("*.sql"))

    # The registered lineage diagram must retain the systems, fields and transformation notes in its source CDE.
    cdes = json.loads((ROOT / "data/mdm/cde_registry.json").read_text(encoding="utf-8"))["elements"]
    entity_key = next(cde for cde in cdes if cde["id"] == "CDE-ENTITY-KEY")
    lineage_diagram = diagrams[4]
    for hop in entity_key["lineage"]:
        assert hop["system"] in lineage_diagram
        assert hop["field"] in lineage_diagram
        assert hop["action"] in lineage_diagram

    # Work-type and hub labels in the operating-model diagram track the scenario records.
    work_items = json.loads((ROOT / "data/mdm/work_items.json").read_text(encoding="utf-8"))["items"]
    ops_diagram = diagrams[3]
    assert {item["work_type"] for item in work_items} <= set(re.findall(r"ONBOARDING|MAINTENANCE|HIERARCHY_CHANGE|MIGRATION|INTEGRATION_EXCEPTION|IDENTITY_CONFLICT", ops_diagram))
    for hub in {item["hub"] for item in work_items}:
        assert hub.replace(" (synthetic)", "") in ops_diagram

    for diagram in diagrams:
        assert "Synthetic roles and data; illustrative" in diagram
        for legend in ("Legend: system step", "Legend: human decision", "Legend: control", "Legend: output"):
            assert legend in diagram


def test_readme_links_architecture_document():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/ARCHITECTURE.md" in readme
    assert "**Conceptual flow; the prototype implements each step separately.**" in readme
    readme_diagrams = re.findall(r"```mermaid\s+(.*?)```", readme, flags=re.DOTALL)
    architecture = DOC.read_text(encoding="utf-8")
    architecture_diagrams = re.findall(r"```mermaid\s+(.*?)```", architecture, flags=re.DOTALL)
    assert readme_diagrams == [architecture_diagrams[1]]


def test_conceptual_business_flow_is_explicitly_not_a_runtime_pipeline():
    text = DOC.read_text(encoding="utf-8")
    assert "## Conceptual business flow" in text
    assert "The prototype implements each step separately" in text
    assert "arrows in this diagram are conceptual relationships, not automated handoffs" in text
