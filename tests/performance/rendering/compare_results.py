"""Compare saved pre and post rendering benchmark reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ENVIRONMENT_KEYS = (
    "environment",
    "gl_vendor",
    "gl_renderer",
    "gl_version",
    "glsl_version",
    "direct_rendering",
    "viewport_size",
    "coin_version",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre", required=True, type=Path)
    parser.add_argument("--post", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    pre = _load(args.pre)
    post = _load(args.post)
    pre_raw = _raw_results(pre)
    post_raw = _raw_results(post)
    fixture_names = sorted(set(pre["aggregates"]) | set(post["aggregates"]))
    comparisons = {}
    environment_checks = []
    for fixture in fixture_names:
        pre_stats = _phase_stats(pre, fixture, "pre")
        post_stats = _phase_stats(post, fixture, "post")
        pre_items = pre_raw.get(fixture, [])
        post_items = post_raw.get(fixture, [])
        hashes = {
            item.get("fixture_sha256")
            for item in pre_items + post_items
            if item.get("fixture_sha256")
        }
        environment_match = _environment_match(pre_items, post_items)
        environment_checks.append(
            {
                "fixture": fixture,
                "fixture_hashes": sorted(hashes),
                "same_fixture_hash": len(hashes) == 1,
                "same_render_environment": environment_match,
            }
        )
        comparisons[fixture] = {
            "pre": pre_stats,
            "post": post_stats,
            "post_pre_ratio": (
                post_stats["median_frame_time_ms"] / pre_stats["median_frame_time_ms"]
                if pre_stats and post_stats
                else None
            ),
            "improvement_percent": (
                (1.0 - post_stats["median_frame_time_ms"] / pre_stats["median_frame_time_ms"])
                * 100.0
                if pre_stats and post_stats
                else None
            ),
        }

    report = {
        "pre_report": str(args.pre.expanduser().resolve()),
        "post_report": str(args.post.expanduser().resolve()),
        "environment_checks": environment_checks,
        "comparisons": comparisons,
        "passed": bool(environment_checks)
        and all(
            check["same_fixture_hash"] and check["same_render_environment"]
            for check in environment_checks
        )
        and all(value["pre"] and value["post"] for value in comparisons.values()),
    }
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "comparison.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "passed": report["passed"]}, indent=2))
    return 0 if report["passed"] else 1


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _phase_stats(report: dict[str, Any], fixture: str, phase: str) -> dict[str, Any] | None:
    values = report.get("aggregates", {}).get(fixture, {})
    if phase in values:
        return values[phase]
    if len(values) == 1:
        return next(iter(values.values()))
    return None


def _raw_results(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {}
    for path_value in report.get("raw_results", []):
        path = Path(path_value)
        value = json.loads(path.read_text(encoding="utf-8"))
        results.setdefault(path.parent.parent.name, []).append(value)
    return results


def _environment_match(
    pre: list[dict[str, Any]], post: list[dict[str, Any]]
) -> bool:
    if not pre or not post:
        return False
    pre_values = tuple(pre[0].get(key) for key in ENVIRONMENT_KEYS)
    post_values = tuple(post[0].get(key) for key in ENVIRONMENT_KEYS)
    return pre_values == post_values


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Pre/post rendering comparison",
        "",
        f"Environment and fixture checks passed: `{report['passed']}`",
        "",
        "| Fixture | Pre median (ms) | Post median (ms) | Post/Pre | Improvement |",
        "|---|---:|---:|---:|---:|",
    ]
    for fixture, values in report["comparisons"].items():
        pre = values["pre"]
        post = values["post"]
        if pre and post:
            lines.append(
                f"| {fixture} | {pre['median_frame_time_ms']:.3f} | "
                f"{post['median_frame_time_ms']:.3f} | "
                f"{values['post_pre_ratio']:.3f} | "
                f"{values['improvement_percent']:.2f}% |"
            )
        else:
            lines.append(f"| {fixture} | — | — | — | — |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
