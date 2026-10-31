"""CLI compatibility audit for one or more RanobeLib titles."""
import argparse
import json
from pathlib import Path

from core.auth.storage import KeyringTokenStorage
from core.compatibility_audit import audit_title
from providers.libsocial.client import LibSocialClient


def configure_parser(parser):
    parser.add_argument("references", nargs="+", help="Title IDs, slugs, or URLs")
    parser.add_argument("--sample", type=int, default=10, help="Chapters sampled per title")
    parser.add_argument("--branch", type=int, help="Specific translation branch")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Inspect metadata and chapter index without fetching chapter text")
    parser.add_argument("--json", type=Path, metavar="PATH", help="Write JSON report")
    parser.add_argument("--retries", type=int, default=3)


def execute(args):
    if args.sample < 1 or args.retries < 1:
        raise SystemExit("--sample and --retries must be positive")
    reports = []
    with LibSocialClient(KeyringTokenStorage().load()) as client:
        for reference in args.references:
            try:
                report = audit_title(
                    client, reference, sample=args.sample, branch_id=args.branch,
                    metadata_only=args.metadata_only, retries=args.retries,
                )
            except Exception as exc:
                report = {"reference": reference, "status": "ERROR", "issues": [
                    f"{type(exc).__name__}: {exc}"]}
            reports.append(report)
            print(f"{report.get('title', reference)}: {report['status']}")
            if "chapters_total" in report:
                print(f"  Chapters: {report['chapters_total']}, sampled: {report['sampled']}, "
                      f"passed: {report['passed']}, failed: {report['failed']}")
                print(f"  Branches: {report['available_branches']}")
                print(f"  Nodes: {report['node_types']}")
            for issue in report["issues"]:
                print(f"  - {issue}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report saved: {args.json}")
    if any(r["status"] in ("INCOMPATIBLE", "ERROR") for r in reports):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Audit RanobeLib EPUB compatibility")
    configure_parser(parser)
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
