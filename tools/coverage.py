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


EXPECT_MISSING = collections.Counter()
EXPECT_EXTRA = collections.Counter()


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
    for k in node.get("corrections", []):
        # extend the edit to whole whitespace-delimited words so punctuation attached to it is compared too
        for c in node["content"]:
            if c["type"] not in ("p", "li", "line"):
                continue
            t, start, seen = c["text"], 0, 0
            while seen < k["occurrences"]:
                i = t.find(k["corrected"], start)
                if i < 0:
                    break
                a = t.rfind(" ", 0, i) + 1
                e = t.find(" ", i + len(k["corrected"]))
                e = len(t) if e < 0 else e
                left, right = t[a:i], t[i + len(k["corrected"]):e]
                EXPECT_EXTRA.update(tokens(left + k["corrected"] + right))
                EXPECT_MISSING.update(tokens(left + k["printed"] + right))
                start = i + len(k["corrected"])
                seen += 1
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
    # logged corrections are the only permitted differences from the PDF text
    expected = collections.Counter(pdf_bag)
    expected.subtract(EXPECT_MISSING)
    expected.update(EXPECT_EXTRA)
    keys = set(expected) | set(json_bag)
    missing = collections.Counter({k: expected[k] - json_bag[k] for k in keys if expected[k] > json_bag[k]})
    extra = collections.Counter({k: json_bag[k] - expected[k] for k in keys if json_bag[k] > expected[k]})
    print("missing from JSON:", sum(missing.values()), dict(missing.most_common(60)))
    print("extra in JSON:", sum(extra.values()), dict(extra.most_common(60)))
    return 1 if (missing or extra) else 0


if __name__ == "__main__":
    sys.exit(main())
