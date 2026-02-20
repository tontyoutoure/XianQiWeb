#!/usr/bin/env python3
"""Two-step term replacement helper.

Workflow:
1) extract: collect each term match with small context into JSONL.
2) apply: read edited JSONL and apply replacements back to source files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class MatchEntry:
    entry_id: str
    path: str
    line: int
    col: int
    match: str
    context_before: str
    context_after: str
    source_snippet: str
    replacement: str
    action: str
    anchor_hash: str


@dataclass
class ReplaceOp:
    entry_id: str
    path: Path
    start: int
    end: int
    replacement: str
    line: int
    col: int
    source_snippet: str


def compute_anchor_hash(path: str, line: int, col: int, snippet: str) -> str:
    payload = f"{path}|{line}|{col}|{snippet}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def index_to_line_col(text: str, index: int) -> Tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index)
    if line_start == -1:
        col = index + 1
    else:
        col = index - line_start
    return line, col


def line_col_to_index(text: str, line: int, col: int) -> int:
    if line < 1 or col < 1:
        raise ValueError("line/col must be 1-based positive integers")
    current_line = 1
    start = 0
    while current_line < line:
        next_break = text.find("\n", start)
        if next_break == -1:
            raise ValueError(f"line {line} out of range")
        start = next_break + 1
        current_line += 1
    index = start + (col - 1)
    if index > len(text):
        raise ValueError(f"col {col} out of range for line {line}")
    return index


def extract_matches(
    source_path: Path,
    term: str,
    context_chars: int,
    output_path: Path,
    default_replacement: str,
) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"source file not found: {source_path}")
    if not term:
        raise ValueError("term must not be empty")

    text = source_path.read_text(encoding="utf-8")
    idx = 0
    entries: List[Dict[str, object]] = []
    serial = 1

    while True:
        hit = text.find(term, idx)
        if hit == -1:
            break

        line, col = index_to_line_col(text, hit)
        left = max(0, hit - context_chars)
        right = min(len(text), hit + len(term) + context_chars)
        context_before = text[left:hit]
        context_after = text[hit + len(term) : right]
        snippet = text[left:right]
        rel_path = source_path.as_posix()
        entry_id = f"XQR-{serial:04d}"

        entries.append(
            {
                "id": entry_id,
                "path": rel_path,
                "line": line,
                "col": col,
                "match": term,
                "context_before": context_before,
                "context_after": context_after,
                "source_snippet": snippet,
                "replacement": default_replacement,
                "action": "replace",
                "anchor_hash": compute_anchor_hash(rel_path, line, col, snippet),
            }
        )
        serial += 1
        idx = hit + len(term)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"extract done: {len(entries)} entries -> {output_path}")


def load_entries(jsonl_path: Path) -> List[MatchEntry]:
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"jsonl file not found: {jsonl_path}")

    entries: List[MatchEntry] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            data = json.loads(raw)
            entries.append(
                MatchEntry(
                    entry_id=data["id"],
                    path=data["path"],
                    line=int(data["line"]),
                    col=int(data["col"]),
                    match=data["match"],
                    context_before=data["context_before"],
                    context_after=data["context_after"],
                    source_snippet=data["source_snippet"],
                    replacement=data.get("replacement", ""),
                    action=data.get("action", "replace"),
                    anchor_hash=data["anchor_hash"],
                )
            )
    return entries


def verify_anchor(entry: MatchEntry) -> bool:
    expected = compute_anchor_hash(entry.path, entry.line, entry.col, entry.source_snippet)
    return entry.anchor_hash == expected


def locate_entry(text: str, entry: MatchEntry) -> Tuple[int, int]:
    # Primary strategy: line/col exact location.
    index = line_col_to_index(text, entry.line, entry.col)
    end = index + len(entry.match)

    if text[index:end] == entry.match:
        left = max(0, index - len(entry.context_before))
        right = min(len(text), end + len(entry.context_after))
        if text[left:right] == entry.source_snippet:
            return index, end

    # Fallback: locate snippet and derive match location.
    snippet_indexes = []
    start = 0
    while True:
        hit = text.find(entry.source_snippet, start)
        if hit == -1:
            break
        snippet_indexes.append(hit)
        start = hit + 1

    if len(snippet_indexes) != 1:
        raise ValueError("snippet location is ambiguous or missing")

    snippet_start = snippet_indexes[0]
    index = snippet_start + len(entry.context_before)
    end = index + len(entry.match)
    if text[index:end] != entry.match:
        raise ValueError("match not found at derived snippet location")
    return index, end


def apply_entries(jsonl_path: Path, report_path: Path) -> None:
    entries = load_entries(jsonl_path)

    by_path: Dict[Path, List[MatchEntry]] = {}
    for entry in entries:
        by_path.setdefault(Path(entry.path), []).append(entry)

    total = len(entries)
    replaced = 0
    skipped = 0
    failures: List[str] = []

    for path, path_entries in by_path.items():
        if not path.is_file():
            failures.append(f"{path}: file missing")
            continue

        text = path.read_text(encoding="utf-8")
        ops: List[ReplaceOp] = []

        for entry in path_entries:
            if not verify_anchor(entry):
                failures.append(f"{entry.entry_id}: anchor hash mismatch")
                continue
            if entry.action != "replace":
                skipped += 1
                continue
            try:
                start, end = locate_entry(text, entry)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{entry.entry_id}: locate failed ({exc})")
                continue
            ops.append(
                ReplaceOp(
                    entry_id=entry.entry_id,
                    path=path,
                    start=start,
                    end=end,
                    replacement=entry.replacement,
                    line=entry.line,
                    col=entry.col,
                    source_snippet=entry.source_snippet,
                )
            )

        ops.sort(key=lambda item: item.start, reverse=True)
        for op in ops:
            text = text[: op.start] + op.replacement + text[op.end :]
            replaced += 1

        path.write_text(text, encoding="utf-8")

    failed = len(failures)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# 回写报告",
        "",
        f"- 总条目: {total}",
        f"- 已替换: {replaced}",
        f"- 已跳过: {skipped}",
        f"- 失败: {failed}",
        "",
    ]

    if failures:
        report_lines.append("## 失败明细")
        for item in failures:
            report_lines.append(f"- {item}")
    else:
        report_lines.append("## 失败明细")
        report_lines.append("- 无")

    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"apply done: replaced={replaced}, skipped={skipped}, failed={failed}")
    print(f"report -> {report_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Term extract/edit/apply helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="extract term contexts to JSONL")
    p_extract.add_argument("--path", required=True, help="target markdown file")
    p_extract.add_argument("--term", default="轮", help="term to find")
    p_extract.add_argument(
        "--context-chars", type=int, default=10, help="chars before/after match"
    )
    p_extract.add_argument(
        "--output",
        default="log/round_context_review.jsonl",
        help="output JSONL path",
    )
    p_extract.add_argument(
        "--default-replacement",
        default="回合",
        help="default replacement for each entry",
    )

    p_apply = sub.add_parser("apply", help="apply edited JSONL back to sources")
    p_apply.add_argument(
        "--input",
        default="log/round_context_review.jsonl",
        help="edited JSONL path",
    )
    p_apply.add_argument(
        "--report",
        default="log/round_context_apply_report.md",
        help="output report path",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "extract":
        extract_matches(
            source_path=Path(args.path),
            term=args.term,
            context_chars=args.context_chars,
            output_path=Path(args.output),
            default_replacement=args.default_replacement,
        )
        return

    if args.cmd == "apply":
        apply_entries(jsonl_path=Path(args.input), report_path=Path(args.report))
        return

    raise RuntimeError(f"unsupported cmd: {args.cmd}")


if __name__ == "__main__":
    main()
