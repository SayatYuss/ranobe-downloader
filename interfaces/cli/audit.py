"""CLI compatibility audit for one or more RanobeLib titles."""
import argparse
import json
import os
import sys
import re
from pathlib import Path

from core.auth.storage import KeyringTokenStorage
from core.compatibility_audit import audit_title
from core.download.plan import make_translations
from core.download.retry import with_retries
from providers.libsocial.titles import TitleProvider
from providers.libsocial.chapters import ChapterProvider
from providers.libsocial.client import LibSocialClient


def configure_parser(parser):
    parser.add_argument("references", nargs="+", help="Title IDs, slugs, or URLs")
    parser.add_argument("--mode", choices=("metadata", "sample", "full"), default="sample",
                        help="metadata=index only, sample=selected chapters, full=all selected chapters")
    parser.add_argument("--check-images", action="store_true", help="Download and validate referenced images (slower)")
    parser.add_argument("--resume", action="store_true", help="Resume from saved per-branch reports")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint every N chapters (default: 10)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI status colors")
    parser.add_argument("--sample", type=int, default=10, help="Chapters sampled per title")
    branch_group = parser.add_mutually_exclusive_group()
    branch_group.add_argument("--branch", type=int, help="Specific translation branch")
    branch_group.add_argument("--all-branches", action="store_true", help="Audit every translation separately")
    parser.add_argument("--metadata-only", action="store_true",
                        help="Inspect metadata and chapter index without fetching chapter text")
    parser.add_argument("--output-dir", type=Path, default=Path("output/audit"),
                        help="Directory for individual slug_branch.json reports")
    parser.add_argument("--json", type=Path, metavar="PATH", help="Optional combined JSON report")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between chapter requests (default: 1)")
    parser.add_argument("--retries", type=int, default=3)


def execute(args):
    if args.delay < 0:
        raise SystemExit('--delay must be non-negative')
    if args.sample < 1 or args.retries < 1:
        raise SystemExit("--sample and --retries must be positive")
    if args.save_every < 1:
        raise SystemExit("--save-every must be positive")
    reports = []
    saved_reports = []
    if args.resume and args.json is not None and args.json.is_file():
        saved_reports = json.loads(args.json.read_text(encoding="utf-8"))
        if not isinstance(saved_reports, list):
            raise SystemExit("Invalid audit report format")

    def report_path(reference, branch_id, slug=None):
        name = (slug or reference).rstrip("/").rsplit("/", 1)[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Unsafe audit slug")
        return args.output_dir / f"{name}_{branch_id if branch_id is not None else 'default'}.json"

    def save_branch(state, reference, branch_id, slug=None):
        target = report_path(reference, branch_id, slug or state.get("slug_url"))
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = target.with_name(target.name + ".tmp")
        pending.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(pending, target)
        return target

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
            prepared = None
            try:
                title = with_retries(
                        lambda: TitleProvider(client).get_title(reference),
                        attempts=args.retries)
                chapters = with_retries(
                        lambda: ChapterProvider(client).get_chapters(title.slug_url),
                        attempts=args.retries)
                available = [t.branch_id for t in make_translations(tuple(chapters))]
                branches = (available or [None]) if args.all_branches else [args.branch]
                prepared = (title, chapters)
            except Exception as exc:
                error_report = {"reference": reference, "selected_branch": None,
                                    "status": "ERROR", "issues": [f"{type(exc).__name__}: {exc}"]}
                reports.append(error_report)
                save_reports()
                print(f"{reference}: ERROR - {error_report['issues'][0]}")
                continue

            print(f"{reference}: checking {len(branches)} translation(s)", flush=True)
            for branch_id in branches:
                title_slug = prepared[0].slug_url if prepared is not None else None
                effective_branch = branch_id if branch_id is not None else (branches[0] if len(branches) == 1 else None)
                if effective_branch is None and not args.all_branches and len(available) == 1:
                    effective_branch = available[0]
                previous = None
                if args.resume:
                    source = report_path(reference, effective_branch, title_slug)
                    if source.is_file():
                        previous = json.loads(source.read_text(encoding="utf-8"))
                    else:
                        previous = next((r for r in saved_reports
                                         if r.get("reference") == reference
                                         and r.get("selected_branch") == branch_id), None)
                active = None
                branch_label = f"branch {branch_id}" if branch_id is not None else "unbranched"

                def on_progress(state, current, total):
                    nonlocal active
                    active = state
                    state["reference"] = reference
                    if not any(r is state for r in reports):
                        reports.append(state)
                    elapsed = state["elapsed_seconds"]
                    eta = elapsed / current * (total - current) if current else 0
                    print(f"{branch_label} [{current}/{total}] {current / total:.1%} "
                          f"passed={state['passed']} failed={state['failed']} "
                          f"unverified={state['unverified']} "
                          f"elapsed={elapsed / 60:.1f}m ETA={eta / 60:.1f}m", flush=True)
                    if current % args.save_every == 0 or current == total:
                        save_branch(state, reference, state.get("selected_branch", effective_branch), title_slug)
                        save_reports()

                try:
                    report = audit_title(
                        client, reference, sample=args.sample, branch_id=branch_id,
                        metadata_only=args.metadata_only, retries=args.retries,
                        mode='metadata' if args.metadata_only else args.mode,
                        delay=args.delay, progress=on_progress,
                        resume_state=previous if args.resume else None,
                        check_images=args.check_images, prepared=prepared)
                except Exception as exc:
                    if active is not None:
                        active["status"] = "ERROR"
                        active["issues"].append(f"Audit interrupted: {type(exc).__name__}: {exc}")
                        report = active
                    else:
                        report = {"reference": reference, "selected_branch": branch_id,
                                  "status": "ERROR", "issues": [f"{type(exc).__name__}: {exc}"]}
                report["reference"] = reference
                if not any(r is report for r in reports):
                    reports.append(report)
                saved_at = save_branch(report, reference, report.get("selected_branch", effective_branch), title_slug)
                save_reports()
                print(f"Report saved: {saved_at}")
                label = report["status"]
                if use_color:
                    label = colors.get(label, "") + label + "\x1b[0m"
                print(f"{report.get('title', reference)} ({branch_label}): {label}")
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
