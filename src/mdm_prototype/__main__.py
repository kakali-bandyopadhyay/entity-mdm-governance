from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import entity_mdm, mdm_ops, product


def main(argv: list[str] | None = None) -> int:
    # The demo includes arrows and other Unicode characters; make the default Windows console reliable.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Synthetic MDM governance prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="show match candidates, survivorship and stewardship decisions")
    sub.add_parser("evaluate", help="score the author-labelled synthetic pair set")
    ops = sub.add_parser("ops", help="show DQ and service-operations scorecards")
    ops.add_argument("--as-of", help="report cutoff timestamp (ISO date or timestamp)")
    ops.add_argument("--html", action="store_true", help="write the static dashboard")
    ops.add_argument("--out", default="docs/mdm_operations.html", help="dashboard output path")
    sub.add_parser("product", help="show governed data product, CDE readiness, access and scorecards")
    sub.add_parser("audit", help="create a synthetic audit-support evidence pack in out/")
    args = parser.parse_args(argv)

    if args.command == "ops":
        report = mdm_ops.build(mdm_ops.load(), args.as_of)
        if args.html:
            output = Path(args.out)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(mdm_ops.as_html(report), encoding="utf-8")
            print(f"Synthetic MDM operations dashboard written to {output}")
        else:
            print(mdm_ops.as_text(report))
    elif args.command == "product":
        report = mdm_ops.build(mdm_ops.load())
        print(product.as_text(product.load(), report["quality_metrics"]))
    elif args.command == "audit":
        report = mdm_ops.build(mdm_ops.load())
        output = Path("out/mdm_audit_evidence_pack.md")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(product.audit_markdown(product.load(), report["quality_metrics"]), encoding="utf-8")
        print(f"Synthetic audit-support evidence pack written to {output}")
    else:
        print(entity_mdm.as_text(entity_mdm.load(), evaluation=args.command == "evaluate"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
