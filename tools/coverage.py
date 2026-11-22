#!/usr/bin/env python3
"""Word-level coverage check: every word in the PDF body (after removing struck-through
text and running headers) must appear in the extracted JSON, and vice versa.
Exits non-zero on any difference."""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract  # noqa: E402

OUT = extract.OUT


def tokens(text):
    text = extract.clean(text).replace("•", " ")
    text = re.sub(r"(?<![\w.])(\d{1,2})\.(?=[A-Za-z])", r"\1. ", text)
    text = re.sub(r"\bx{3,}\b", " ", text)
    return [w for w in re.split(r"\s+", text) if w]


def walk(node, bag):
    t = node.get("type")
    if t in ("chapter", "section") and node.get("title_source") != "contents":
        bag.update(tokens(f"{node['number']}. {node['title']}"))
    if t == "group":
        bag.update(tokens(node.get("title") or ""))
        bag.update(tokens(node.get("lead") or ""))
    if t == "clause":
        bag.update(tokens(node["label"]))
    if t in ("p", "li", "line"):
        bag.update(tokens(node["text"]))
    if t == "table":
        for row in ([node["header"]] if node.get("header") else []) + node["rows"]:
            for cell in row:
                bag.update(tokens(cell))
    if t == "figure":
        bag.update(tokens(node.get("caption") or ""))
        bag.update(tokens(node.get("note") or ""))
        for v in node.get("values", []) + node.get("legend", []):
            bag.update(tokens(v))
    if t in ("figure", "failure-matrix"):
        for v in node.get("labels", []):
            bag.update(tokens(v))
    if t == "failure-matrix":
        for colour, cols in node["matrix"].items():
            for lift, reasons in cols.items():
                for r in reasons:
                    bag.update(tokens(r))
    for c in node.get("content", []):
        walk(c, bag)


def main():
    lines, _ = extract.load_lines()
    pdf_bag = collections.Counter()
    for _, ln in lines:
        pdf_bag.update(tokens(ln))
    json_bag = collections.Counter()
    for f in sorted(OUT.glob("ch-*.json")):
        walk(json.loads(f.read_text(encoding="utf-8")), json_bag)
    missing = pdf_bag - json_bag
    extra = json_bag - pdf_bag
    print("missing from JSON:", sum(missing.values()), dict(missing.most_common(60)))
    print("extra in JSON:", sum(extra.values()), dict(extra.most_common(60)))
    return 1 if (missing or extra) else 0


if __name__ == "__main__":
    sys.exit(main())
