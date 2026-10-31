"""CLI compatibility audit for one or more RanobeLib titles."""
import argparse
import json
import os
import sys
from pathlib import Path

from core.auth.storage import KeyringTokenStorage
from core.compatibility_audit import audit_title
from providers.libsocial.client import LibSocialClient


def configure_parser(parser):
    parser.add_argument("references", nargs="+", help="Title IDs, slugs, or URLs")
    parser.add_argument("--mode", choices=("metadata", "sample", "full"), default="sample",
                        help="metadata=index only, sample=selected chapters, full=all selected chapters")
    parser.add_argument("--check-images", action="store_true", help="Download and validate referenced images (slower)")
    parser.add_argument("--resume", action="store_true", help="Resume from existing --json report")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint every N chapters (default: 10)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI status colors")
    parser.add_argument("--sample", type=int, default=10, help="Chapters sampled per title")
    parser.add_argument("--branch", type=int, help="Specific translation branch")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Inspect metadata and chapter index without fetching chapter text")
    parser.add_argument("--json", type=Path, metavar="PATH", help="Write JSON report")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between chapter requests (default: 1)")
    parser.add_argument("--retries", type=int, default=3)


def execute(args):
    if args.delay < 0:
        raise SystemExit('--delay must be non-negative')
    if args.sample < 1 or args.retries < 1:
        raise SystemExit("--sample and --retries must be positive")
    if args.save_every < 1:
        raise SystemExit("--save-every must be positive")
    if args.resume and not args.json:
        raise SystemExit("--resume requires --json PATH")
    reports = []
    saved_reports = []
    if args.resume and args.json.is_file():
        saved_reports = json.loads(args.json.read_text(encoding="utf-8"))
        if not isinstance(saved_reports, list):
            raise SystemExit("Invalid audit report format")

    def save_reports():
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            pending = args.json.with_name(args.json.name + ".tmp")
            pending.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(pending, args.json)

    colors = {'COMPATIBLE': '\x1b[32m', 'INCOMPATIBLE': '\x1b[31m',
              'ERROR': '\x1b[31m', 'INCONCLUSIVE': '\x1b[33m',
              'NOT_TESTED': '\x1b[36m'}
    use_color = sys.stdout.isatty() and not args.no_color and not bool(__import__('os').environ.get('NO_COLOR'))
    with LibSocialClient(KeyringTokenStorage().load()) as client:
        for reference in args.references:
            previous = next((r for r in saved_reports
                             if r.get("reference") == reference), None)

            active = None

            def on_progress(state, current, total):
                nonlocal active
                active = state
                state["reference"] = reference
                if not any(r is state for r in reports):
                    reports.append(state)
                elapsed = state["elapsed_seconds"]
                remaining = total - current
                eta = (elapsed / current * remaining) if current else 0
                print(f"[{current}/{total}] {current / total:.1%} "
                      f"passed={state['passed']} failed={state['failed']} "
                      f"unverified={state['unverified']} "
                      f"elapsed={elapsed / 60:.1f}m ETA={eta / 60:.1f}m", flush=True)
                if current % args.save_every == 0 or current == total:
                    save_reports()

            try:
                report = audit_title(
                    client, reference, sample=args.sample, branch_id=args.branch,
                    metadata_only=args.metadata_only, retries=args.retries,
                    mode='metadata' if args.metadata_only else args.mode,
                    delay=args.delay, progress=on_progress,
                    resume_state=previous if args.resume else None,
                    check_images=args.check_images,
                )
            except Exception as exc:
                if active is not None:
                    active["status"] = "ERROR"
                    active["issues"].append(f"Audit interrupted: {type(exc).__name__}: {exc}")
                    report = active
                else:
                    report = {"reference": reference, "status": "ERROR", "issues": [
                        f"{type(exc).__name__}: {exc}"]}
            report["reference"] = reference
            if not any(r is report for r in reports):
                reports.append(report)
            save_reports()
            label = report["status"]
            if use_color:
                label = colors.get(label, "") + label + "\x1b[0m"
            print(f"{report.get('title', reference)}: {label}")
            if "chapters_total" in report:
                print(f"  Chapters: {report['chapters_total']}, sampled: {report['sampled']}, "
                      f"passed: {report['passed']}, failed: {report['failed']}, "
                      f"unverified: {report.get('unverified', 0)}")
                print(f"  Branches: {report['available_branches']}")
                print(f"  Nodes: {report['node_types']}")
                print(f"  Formats: {report.get('content_formats', {})}, HTML images: {report.get('html_images', 0)}")
            for issue in report["issues"]:
                print(f"  - {issue}")
    if args.json:
        save_reports()
        print(f"Report saved: {args.json}")
    if any(r["status"] != "COMPATIBLE" for r in reports):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Audit RanobeLib EPUB compatibility")
    configure_parser(parser)
    execute(parser.parse_args())


if __name__ == "__main__":
    main()
