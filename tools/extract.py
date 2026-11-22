#!/usr/bin/env python3
"""Extract the 2026 IPF Technical Rulebook PDF into structured JSON.

Principles (see docs/SPEC-DIGEST.md):
  * Wording is never edited. Whitespace is normalised (line wraps joined) and that is all.
  * Text struck through in the PDF is excluded from rule text but recorded in `struck`.
  * Text printed in red in the PDF is recorded as `changed_2026` (the PDF's own marking).
  * Every layout-driven special case lives in FIXUPS below so it can be reviewed.

Run:  python3 -I tools/extract.py
Needs: pdftotext (poppler) and pdfplumber.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "2026_IPF_Technical_Rulebook__effective_01_March_2026__v3.pdf"
OUT = ROOT / "content" / "en" / "2026"
EDITION = "2026"
PREFIX = "tr2026"
FIRST_BODY_PAGE = 4
RED = (0.82, 0.21, 0.2)
BULLET = "• "

report = {"layout_fixes": [], "warnings": [], "struck": [], "dedupe": []}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- PDF reading
def page_layout_text(n):
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(PDF), "-"],
        capture_output=True, text=True, check=False).stdout
    return out.split("\f")[0].split("\n")


def is_red(c):
    col = c.get("non_stroking_color")
    return bool(col) and len(col) == 3 and all(abs(a - b) < 0.02 for a, b in zip(col, RED))


STRIKE_COLOURS = [(0.0, 0.0, 0.0)]


def _close(col, ref, tol=0.12):
    return bool(col) and len(col) == 3 and all(abs(a - b) < tol for a, b in zip(col, ref))


def is_strike_rect(r):
    if not (r["height"] < 1.6 and 3 < r["width"] < 560):
        return False
    col = r.get("non_stroking_color")
    return _close(col, (0, 0, 0)) or _close(col, (0.85, 0.12, 0.14), 0.15)


S_ON, S_OFF = "\ue000", "\ue001"   # sentinels around red (inserted in 2026) runs


def clean_page_text(page):
    """Layout text for one page with struck-through chars removed, bullets restored as
    '• ' and red (inserted) runs wrapped in sentinels. Returns (text, struck_text)."""
    thin = [r for r in page.rects if is_strike_rect(r)]
    chars, struck = [], []
    for c in page.chars:
        h = c["bottom"] - c["top"]
        hit = False
        for r in thin:
            ry = (r["top"] + r["bottom"]) / 2
            ov = min(c["x1"], r["x1"]) - max(c["x0"], r["x0"])
            if ov > 0.5 * (c["x1"] - c["x0"]) and c["top"] + 0.3 * h < ry < c["bottom"] - 0.15 * h:
                hit = True
                break
        (struck if hit else chars).append(dict(c))
    chars.sort(key=lambda c: (round(c["top"]), c["x0"]))
    # red runs (visible chars only), wrapped in sentinels
    vis = [c for c in chars if c["text"].strip() != ""]
    for k, c in enumerate(vis):
        r = is_red(c)
        pr = k > 0 and is_red(vis[k - 1])
        nr = k + 1 < len(vis) and is_red(vis[k + 1])
        if r and not pr:
            c["text"] = S_ON + c["text"]
        if r and not nr:
            c["text"] = c["text"] + S_OFF
    # bullets
    for b in page.curves:
        if b["width"] < 4 and b["height"] < 4 and b.get("fill"):
            near = [c for c in chars if abs((c["top"] + c["bottom"]) / 2 - (b["top"] + b["bottom"]) / 2) < 4
                    and 0 <= c["x0"] - b["x1"] < 25]
            if near:
                ref = dict(min(near, key=lambda c: c["x0"]))
                ref.update(text="\u2022", x0=b["x0"], x1=b["x1"] + 3)
                chars.append(ref)
    from pdfplumber.utils import extract_text
    text = extract_text(chars, layout=True, layout_width=page.width, layout_height=page.height,
                        layout_bbox=page.bbox, x_density=5.0, y_density=13)
    struck.sort(key=lambda c: (round(c["top"]), c["x0"]))
    parts, prev = [], None
    for c in struck:
        if prev is not None:
            if abs(c["top"] - prev["top"]) > 3:
                parts.append(" ")
            elif c["x0"] - prev["x1"] > 12:
                parts.append(" … ")
            elif c["x0"] - prev["x1"] > 1.5:
                parts.append(" ")
        parts.append(c["text"])
        prev = c
    return text, "".join(parts).strip()


def load_lines():
    """[(page, text)] with running headers/footers removed."""
    pdf = pdfplumber.open(str(PDF))
    lines = []
    for n in range(FIRST_BODY_PAGE, len(pdf.pages) + 1):
        text, struck = clean_page_text(pdf.pages[n - 1])
        if struck:
            report["struck"].append({"page": n, "text": struck})
        for ln in text.split("\n"):
            cl = re.sub(r"\s+", " ", ln).strip()
            if cl == "T E C H N I C A L RULEBOOK":
                continue
            if re.match(r"^\d+ .+ 01\.03\.2026$", cl):
                continue
            lines.append((n, ln.rstrip().replace("\u2022", BULLET.strip() + "\u0000").replace("\u0000", " ")))
    return lines, {}


# --------------------------------------------------------------------------- tokens
HEAD_CH = re.compile(r"^(\d{1,2})\. ?([A-Z][A-Z ,&/’'()\-]+)$")
HEAD_SEC = re.compile(r"^(\d{1,2}\.\d{1,2})\. ?([A-Z][A-Z ,&/’'()\-.]+)$")
HEAD_SUB = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{1,2})\. ?([A-Z][A-Z ,&/’'()\-]+)$")
L_NUM = re.compile(r"^(\d{1,2})\) ?(.*)$")
L_ALPHA = re.compile(r"^\(([a-z])\) ?(.*)$")
L_SUB = re.compile(r"^([A-Z]|\d)\. (.*)$")
GROUP_HEADS = {"SUPPORTIVE", "SINGLET (NON-SUPPORTIVE)", "WRIST", "KNEE",
               "Materials and Construction:", "Dimensions:"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def collapse(t):
    return re.sub(r"\s+", " ", t).strip()


class Red:
    """Tracks red (inserted-in-2026) runs across lines and paragraphs."""
    def __init__(self):
        self.on = False

    def strip(self, text):
        """Return (clean_text, ranges) where ranges are [start, end) offsets in clean_text."""
        out, ranges, start = [], [], (0 if self.on else None)
        for ch in text:
            if ch == S_ON:
                self.on, start = True, len(out)
            elif ch == S_OFF:
                self.on = False
                if start is not None:
                    ranges.append([start, len(out)])
                start = None
            else:
                out.append(ch)
        if self.on and start is not None:
            ranges.append([start, len(out)])
        return "".join(out), ranges


def merge_ranges(rs):
    rs = sorted(rs)
    out = []
    for a, b in rs:
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def assemble(lines, red):
    """Join wrapped lines into one string, collapsing whitespace, tracking red ranges."""
    text, ranges = "", []
    for ln in lines:
        clean, rs = red.strip(ln)
        base = len(text) + (1 if text else 0)
        # collapse whitespace inside this line while keeping range offsets in sync
        piece, mapping = [], {}
        prev_space = True
        for i, ch in enumerate(clean):
            mapping[i] = len(piece)
            if ch.isspace():
                if not prev_space:
                    piece.append(" ")
                prev_space = True
            else:
                piece.append(ch)
                prev_space = False
        mapping[len(clean)] = len(piece)
        piece = "".join(piece).strip()
        lead = len(re.match(r"^\s*", clean).group(0))
        for a, b in rs:
            a2 = max(0, mapping.get(a, 0) - (1 if lead and mapping.get(a, 0) > 0 else 0))
            b2 = min(len(piece), mapping.get(b, len(piece)))
            if b2 > a2:
                ranges.append([base + a2, base + b2])
        if not piece:
            continue
        text = (text + " " + piece) if text else piece
    return text, merge_ranges(ranges)


# hand-structured regions: (page, start-regex, end-regex, builder name)
REGIONS = [
    (5, r"^MEN & WOMEN$", r"^MASTER 4 ", "age_table"),
    (5, r"^MEN WOMEN$", r"^120\.0\+ kg Class", "weight_table"),
    (8, r"^IPF RECOGNIZED POWERLIFTING BAR", r"^1320$", "knurling_figure"),
    (8, r"^Face Value in Kilos", r"^0\.25 0\.255 0\.245$", "disc_table"),
    (10, r"^SQUAT BENCH PRESS DEADLIFT$", r"^$NEVER", "failure_matrix_start"),
]


def sentinel_free(t):
    return t.replace(S_ON, "").replace(S_OFF, "")


# --------------------------------------------------------------------------- hand-structured regions
# Layout-driven constructs (tables, figures, side-by-side columns) cannot be recovered
# mechanically. Each is transcribed here from the PDF and verified by tools/coverage.py,
# which fails if any word in the PDF body is missing from, or added to, the extracted text.
def T(rows, header=None, caption=None, **kw):
    return {"type": "table", "caption": caption, "header": header, "rows": rows, **kw}


def FIG(caption, **kw):
    return {"type": "figure", "caption": caption, "status": "needs-redraw", **kw}


MATRIX = {
    "RED": {
        "SQUAT": ["Failure to bend the knees and lower the body until the top surface of the legs at the hip joint is lower than the top of the knees."],
        "BENCH PRESS": ["Bar is not lowered to chest or abdominal area i.e., not reaching the chest or abdominal area, or is touching the belt.",
                        "Failure to lower the underside of both elbow joints level with or below the top surface of each respective shoulder joint"],
        "DEADLIFT": ["Failure to lock the knees straight at the completion of the lift.",
                     "The front bundle of the deltoid muscle should be placed behind the imaginary projection of the bar",
                     "Failure to stand erect"],
    },
    "BLUE": {
        "SQUAT": ["Failure to assume an upright position with the knees locked at the commencement and at the completion of the lift.",
                  "Double bouncing or more than one recovery attempt at the bottom of the lift or any downward movement during the ascent."],
        "BENCH PRESS": ["Any downward movement of the whole of the bar in the course of being pressed out.",
                        "Failure to press the bar to straight arm’s length elbows locked at the completion of the lift.",
                        "Failure to lock the arms before the “START” command."],
        "DEADLIFT": ["Any downward movement of the bar before it reaches the final position. If the bar settles as the shoulders come back this shall not be a reason for disqualification.",
                     "Supporting the bar on the thighs during the performance of the lift. If the bar edges up the thighs but is not supported, this is not reason for disqualification."],
    },
    "YELLOW": {
        "SQUAT": ["Stepping backward or forward or moving the feet laterally. Rocking the feet between the ball and heel is permitted.",
                  "Failure to observe the Chief Referees signals at the commencement or completion of the lift.",
                  "Contact with bar or lifter by the spotters/loaders between the Chief Referees’ signals, in order to make the lift easier.",
                  "Contact of elbows or upper arms with the legs, which has supported and been of aid to the lifter. Slight contact that is of no aid may be ignored.",
                  "Any dropping or dumping of the bar after completion of the lift.",
                  "Failure to comply with any of the requirements contained in the general description of the lift, which precedes this list of disqualification.",
                  "Incomplete lift"],
        "BENCH PRESS": ["Sinking the bar after it has been motionless on the chest or abdominal area, in such a way as to aid the lifter.",
                        "Failure to observe the Chief Referees signals at the commencement, during or completion of the lift.",
                        "Utilizing upper body thrust to initiate upward movement of the bar from the chest.",
                        "Any change in the elected lifting position during the lift proper, i.e., any raising movement of the head, shoulders, or buttocks from their original points of contact with the bench, or lateral movement of the hands on the bar.",
                        "Contact with the bar or the lifter by the spotters/ loaders between the Chief Referees signals, in order to make the lift easier.",
                        "Any contact of the lifter’s feet with the bench or its supports. Deliberate contact between the bar and the bar rest supports during the lift in order to make the lift easier.",
                        "Failure to comply with any of the requirements contained in the general description of the lift, which precedes this list of disqualification.",
                        "Incomplete lift"],
        "DEADLIFT": ["Lowering the bar before receiving the Chief Referees signal.",
                     "Allowing the bar to return to the platform without maintaining control with both hands, i.e. releasing the bar from the palms of the hand.",
                     "Stepping backward or forward or moving the feet laterally. Rocking the feet between the ball and heel is permitted. Foot movement after the command “Down” will not be cause for failure.",
                     "Failure to comply with any of the requirements contained in the general description of the lift, which precedes this list of disqualification.",
                     "Incomplete lift"],
    },
}

AGE_ROWS = [
    ["OPEN", "from 1 January in the calendar year, he/she reaches 19 years and upwards"],
    ["SUB-JUNIORS", "from the day he/she reaches 14 years and throughout the full calendar year in which he/she reaches 18 years of age."],
    ["JUNIORS", "from 1 January in the calendar year, he/she reaches 19 years and throughout the full calendar year in which he/she reaches 23 years of age."],
    ["MASTER 1", "from 1 January in the calendar year, he/she reaches 40 years and throughout the full calendar year in which he/she reaches 49 years of age."],
    ["MASTER 2", "from 1 January in the calendar year, he/she reaches 50 years and throughout the full calendar year in which he/she reaches 59 years of age."],
    ["MASTER 3", "from 1 January in the calendar year, he/she reaches 60 years and throughout the full calendar year in which he/she reaches 69 years of age."],
    ["MASTER 4", "from 1 January in the calendar year, he/she reaches 70 years and upwards."],
]
WEIGHT_ROWS = [
    ["Sub-Junior & Junior only-up to 53.0 kg", "Sub-Junior & Junior only-up to 43.0 kg"],
    ["59.0 kg Class up to 59.0 kg", "47.0 kg Class up to 47.0 kg"],
    ["66.0 kg Class from 59.01 kg up to 66.0 kg", "52.0 kg Class from 47.01 kg up to 52.0 kg"],
    ["74.0 kg Class from 66.01 kg up to 74.0 kg", "57.0 kg Class from 52.01 kg up to 57.0 kg"],
    ["83.0 kg Class from 74.01 kg up to 83.0 kg", "63.0 kg Class from 57.01 kg up to 63.0 kg"],
    ["93.0 kg Class from 83.01 kg up to 93.0 kg", "69.0 kg Class from 63.01 kg up to 69.0 kg"],
    ["105.0 kg Class from 93.01 kg up to 105.0 kg", "76.0 kg Class from 69.01 kg up to 76.0 kg"],
    ["120.0 kg Class from 105.01 kg up to 120.0 kg", "84.0 kg Class from 76.01 kg up to 84.0 kg"],
    ["120.0+ kg Class from 120.01 kg up to unlimited", "84.0+ kg Class from 84.01 kg up to unlimited"],
]
DISC_ROWS = [["25", "25.0625", "24.9375"], ["20", "20.05", "19.95"], ["15", "15.0375", "14.9625"],
             ["10", "10.025", "9.975"], ["5", "5.0125", "4.9875"], ["2.5", "2.51", "2.49"],
             ["1.25", "1.26", "1.24"], ["1", "1.01", "0.99"], ["0.5", "0.51", "0.49"],
             ["0.25", "0.255", "0.245"]]
AMPUTEE_ROWS = [["For each below the ankle amputation", "1/54 of bodyweight"],
                ["For each below the knee amputation", "1/36 of bodyweight"],
                ["For each above the knee amputation", "1/18 of bodyweight"],
                ["For each hip disarticulation", "1/9 of bodyweight"]]
SIGNAL_ROWS = [
    ["SQUAT", "A visual signal consisting of a downward movement of the arm together with the audible command “squat”",
     "A visual signal consisting of a backward movement of the arm together with the audible command “rack”"],
    ["BENCH PRESS", "A visual signal consisting of a downward movement of the arm together with the audible command “start”. DURING: The audible command “Press” after motionless at the chest and the visible signal of an upward movement of the arm.",
     "A visual signal consisting of a backward movement of the arm together with the audible command “rack”"],
    ["DEADLIFT", "No signal required",
     "A visual signal consisting of a downward movement of the arm together with the audible command “down”"],
]

# (page, start regex, end regex, block factory). Start/end match collapsed lines.
REGIONS = [
    (5, r"^MEN & WOMEN$", r"^MASTER 4 ", lambda: [T(AGE_ROWS, header=["MEN & WOMEN", ""], caption="1.1. AGE CATEGORIES", kind="age-categories")]),
    (5, r"^MEN WOMEN$", r"^120\.0\+ kg Class", lambda: [T(WEIGHT_ROWS, header=["MEN", "WOMEN"], caption="1.2. BODYWEIGHT CATEGORIES", kind="weight-classes")]),
    (8, r"^IPF RECOGNIZED POWERLIFTING BAR", r"^1320$", lambda: [FIG("IPF RECOGNIZED POWERLIFTING BAR GUIDELINE OF KNURLING DISTANCES", kind="knurling", note="Measurements in mm (knurling distances inside the collar sleeves)", values=["120", "-", "240", "245", "160", "440", "810", "1320"], pdf_page=8)]),
    (8, r"^Face Value in Kilos", r"^0\.25 0\.255 0\.245$", lambda: [T(DISC_ROWS, header=["Face Value in Kilos", "Maximum", "Minimum"], kind="disc-tolerances")]),
    (10, r"^SQUAT BENCH PRESS DEADLIFT$", r"!^2\.10\. SCOREBOARD$", lambda: [{"type": "failure-matrix", "matrix": MATRIX, "labels": ["SQUAT", "BENCH PRESS", "DEADLIFT", "SQUAT", "BENCH PRESS", "DEADLIFT", "1.RED", "2.BLUE", "3.YELLOW"]}]),
    (26, r"^For each below the ankle", r"^For each hip disarticulation", lambda: [T(AMPUTEE_ROWS, kind="amputee-fractions")]),
    (36, r"^LIFT COMMENCEMENT COMPLETION$", r"!^When a lifter fails to complete", lambda: [T(SIGNAL_ROWS, header=["LIFT", "COMMENCEMENT", "COMPLETION"], kind="signals")]),
    (12, r"^CHAMPIONSHIPS SCOREBOARD$", r"!^3\. ?PERSONAL EQUIPMENT", lambda: [FIG("CHAMPIONSHIPS SCOREBOARD", kind="scoreboard-template", labels=["GROUP:", "SQUAT", "BENCH PRESS", "DEADLIFT", "LOT", "NAME", "NAT", "BD/ WT", "RD1", "RD2", "RD3", "RD1", "RD2", "RD3", "SUB TOT", "RD1", "RD2", "RD3", "TOT", "PLACE", "1", "2", "3", "..", "14"], pdf_page=12)]),
    (21, r"^The diagrams below indicate", r"^the squat\.$", lambda: [
        FIG("The diagrams below indicate the typical bar position but not obligatory and required depth in the squat:", kind="squat-depth", pdf_page=21),
        "7) Contact of the elbows or upper arms with the legs. Slight contact is permitted if there is no supporting that might aid the lifter.",
        "8) Any dropping or dumping of the bar after completion of the lift.",
        "9) Failure to comply with any of the items outlined under Rules of Performance for the squat."]),
    (25, r"^SCHEMATIC REPRESENTATION", r"^α – the deflection angle$", lambda: [
        FIG("SCHEMATIC REPRESENTATION OF THE CORRECT SHOULDER’S ABDUCTION IN THE FINAL POSITION OF THE DEADLIFT", kind="deltoid-angle", legend=["A - THE FRONT BUNDLE OF THE DELTOID MUSCLE", "B – THE BAR", "RED STRAIGHT LINE – IMAGINARY PROJECTION OF THE BAR", "α – the deflection angle"], pdf_page=25),
        FIG("THE DIAGRAM BELOW SHOWS THE SUPPORTING OF THE BAR ON THE THIGHS", kind="bar-on-thighs", pdf_page=25)]),
    (28, r"^SPEAKER’S CARD$", r"^• 3 – 2 Second changing 3rd attempt\.$", lambda: [
        FIG("SPEAKER’S CARD", kind="speaker-card", labels=["NAME, SURNAME:", "BIRTH DATE:", "NATION:", "BODYWEIGHT", "LOT NUMBER", "WEIGHT CLASS", "IPF FORMULA", "SIGNATURE: LIFTER/COACH", "DISCIPLINE", "1ST ATTEMPT", "2ND ATTEMPT", "3RD ATTEMPT", "BEST ATTEMPT", "SQUAT", "BENCH PRESS", "DEADLIFT", "SUBTOTAL", "SUBTOTAL", "DEADLIFT", "GROUPING 1,2,3", "IPF POINTS", "PLACING", "TOTAL"], pdf_page=28),
        FIG("ATTEMPT CARDS", kind="attempt-card", labels=["Insert the Surname, Name", "Insert the chosen discipline & lot number", "1,2,3 Insert your chosen weight here", "3 – 1 First changing 3rd attempt.", "3 – 2 Second changing 3rd attempt."], pdf_page=28)]),
]


# --------------------------------------------------------------------------- tree builder
TERMINAL = tuple(".:;?!)”\"")
FIG_LINES = re.compile(r"^(GOOD LIFT|NO LIFT|PICTURE A - .*)$")
COACH_LINE = re.compile(r"^\d Athletes?\b")
FAIL_LINE = re.compile(r"^Failure no\. \d = ")
RAW_YESNO_TAIL = re.compile(r"\s{6,}(YES|NO)(\s{3,}(YES|NO))?\s*$")
RAW_YESNO_HEAD = re.compile(r"^\s*(YES|NO)(\s{3,}(YES|NO))?(\s{6,}|\s*$)")


def clean(t):
    return t.replace(S_ON, "").replace(S_OFF, "")


def read_toc():
    """Titles from the contents pages (2-3), keyed by number."""
    txt = subprocess.run(["pdftotext", "-layout", "-f", "2", "-l", "3", str(PDF), "-"],
                         capture_output=True, text=True).stdout
    toc = {}
    for ln in txt.split("\n"):
        t = collapse(ln)
        m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.? ?([A-Za-z].*?)\s*\.{3,}\s*\d+$", t) or \
            re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.? ?([A-Za-z].*?)\s*\.{3,}\s*$", t)
        if m:
            toc[m.group(1)] = m.group(2).strip()
    # 4.2.2 title wraps over two lines in the contents
    toc["4.2.2"] = "Rules for the Disabled athletes Competing in IPF Single Lift Bench press Championships"
    return toc


class Tree:
    def __init__(self, toc):
        self.toc = toc
        self.chapters = []
        self.ids = set()
        self.red = Red()
        self.ch = self.sec = self.group = None
        self.stack = []
        self.para = None   # dict(kind, lines, page)
        self.counters = {}
        self.last_label = {}   # (container id, kind) -> last label value
        self.page = FIRST_BODY_PAGE

    # ---- containers
    def scope(self):
        if self.sec is not None:
            return self.sec["number"]
        return self.ch["number"]

    def base(self):
        return self.group or self.sec or self.ch

    def target(self):
        return self.stack[-1] if self.stack else self.base()

    def uid(self, base):
        cand, n = base, 1
        while cand in self.ids:
            n += 1
            cand = f"{base}-{n}"
        if n > 1:
            report["dedupe"].append({"id": cand, "base": base})
        self.ids.add(cand)
        return cand

    def next_id(self, kind):
        k = (self.scope(), kind)
        self.counters[k] = self.counters.get(k, 0) + 1
        return self.uid(f"{PREFIX}.{self.scope()}.{kind}{self.counters[k]}")

    # ---- nodes
    def add_node(self, node):
        self.target()["content"].append(node)

    CLAUSE_LEVEL = {"knurling", "yes-no", "disc-tolerances", "amputee-fractions"}

    def add_block(self, blk):
        blk = dict(blk)
        kind = {"table": "table", "figure": "fig", "failure-matrix": "matrix"}[blk["type"]]
        blk.setdefault("status", None) if blk["type"] != "figure" else None
        blk["id"] = self.next_id(kind)
        blk["page"] = self.page
        blk["sha256"] = sha(json.dumps({k: v for k, v in blk.items() if k not in ("id", "page", "sha256")}, ensure_ascii=False, sort_keys=True))
        if blk["type"] == "figure" and blk.get("kind") not in self.CLAUSE_LEVEL:
            self.base()["content"].append(blk)
        else:
            self.add_node(blk)

    def flush(self):
        pr = self.para
        if not pr:
            return
        self.para = None
        text, ranges = assemble(pr["lines"], self.red)
        if not text:
            return
        node = {"type": pr["kind"], "text": text, "page": pr["page"]}
        if ranges:
            node["changed"] = ranges
        if pr["kind"] in ("p", "line") and not self.stack:
            node["id"] = self.next_id("p")
        self.add_node(node)

    def open_chapter(self, number, title, page, from_toc=False):
        self.flush()
        self.stack = []
        self.group = self.sec = None
        toc_title = self.toc.get(number)
        self.ch = {"type": "chapter", "id": self.uid(f"{PREFIX}.{number}"), "number": number,
                   "title": title, "toc_title": toc_title, "title_source": "contents" if from_toc else "body",
                   "page": page, "content": []}
        self.chapters.append(self.ch)

    def open_section(self, number, title, page):
        self.flush()
        self.stack = []
        self.group = None
        sec = {"type": "section", "id": self.uid(f"{PREFIX}.{number}"), "number": number, "title": title,
               "toc_title": self.toc.get(number), "page": page, "content": []}
        depth = number.count(".")
        if depth >= 2 and self.sec is not None and self.sec["number"].count(".") == 1:
            parent = self.sec
        elif depth >= 2 and self.sec is not None and self.sec["number"].count(".") == 2:
            parent = self.parent_sec
        else:
            parent = self.ch
        if depth == 1:
            parent = self.ch
        self.parent_sec = parent if depth == 1 else getattr(self, "parent_sec", self.ch)
        if depth == 1:
            self.parent_sec = self.ch
            self.sec_l1 = sec
        elif depth == 2:
            parent = self.sec_l1
        parent["content"].append(sec)
        self.sec = sec

    def open_group(self, title, lead=None, page=None):
        self.flush()
        self.stack = []
        g = {"type": "group", "id": self.uid(f"{PREFIX}.{self.scope()}.{slug(title or 'officials')}"),
             "title": title, "page": page or self.page, "content": []}
        if lead:
            g["lead"] = lead
        (self.sec or self.ch)["content"].append(g)
        self.group = g

    def label_ok(self, kind, label):
        key = (id(self.base()), id(self.stack[-1]) if self.stack and kind != "num" and False else 0, kind)
        return True

    def start_clause(self, kind, label, rest, page, raw_first):
        self.flush()
        # sequence sanity (alpha/num)
        top_kinds = [c["label_kind"] for c in self.stack]
        if kind in top_kinds:
            idx = top_kinds.index(kind)
            prev = self.stack[idx]["label"]
            self.stack = self.stack[:idx]
        else:
            prev = None
        parent = self.target()
        raw_key = label.strip("().")
        key = {"num": f"item-{raw_key}", "alpha": raw_key, "sub": f"pt-{raw_key.lower()}"}[kind]
        base = f"{parent['id']}.{key}"
        cid = self.uid(base)
        node = {"type": "clause", "id": cid, "label": label, "label_kind": kind, "page": page, "content": []}
        if cid != base:
            node["label_as_printed"] = label
        parent["content"].append(node)
        self.stack.append(node)
        self.para = {"kind": "p", "lines": [raw_first], "page": page}

    def label_sequence_ok(self, kind, label):
        """True if this label plausibly continues a list in the current context."""
        top = {c["label_kind"]: c for c in self.stack}
        prev = top.get(kind)
        if kind == "alpha":
            v = label[1]
            if prev is None:
                return v == "a" or True
            pv = prev["label"][1]
            return ord(v) in (ord(pv), ord(pv) + 1) or v == "a"
        if kind == "num":
            n = int(label[:-1])
            if prev is None:
                # first numbered clause in a container, or continuing a chapter-level list
                last = self.last_num.get(self.ch["number"] if self.sec is None else self.sec["number"])
                return n == 1 or last is None or n in (last, last + 1)
            pn = int(prev["label"][:-1])
            return n in (pn, pn + 1)
        return True

    last_num = {}


def normalise_lines(lines):
    """Apply per-page raw-line transforms; return list of items."""
    items = []
    yesno_pages = set()
    for pg, raw in lines:
        flag = None
        if pg in (15, 16, 20):
            n = RAW_YESNO_TAIL.sub("", raw)
            if n != raw:
                raw, flag = n, "yesno"
            n = RAW_YESNO_HEAD.sub("", raw)
            if n != raw:
                raw, flag = n, "yesno"
        if flag and pg not in yesno_pages:
            yesno_pages.add(pg)
            items.append(("block", pg, FIG(None, kind="yes-no", pdf_page=pg, alt="Yes / No example photographs", labels=["YES", "NO"] * (2 if pg == 20 else 1))))
        if not raw.strip():
            items.append(("blank", pg))
        else:
            ind = len(raw) - len(raw.lstrip())
            items.append(("line", pg, ind, collapse(raw)))
    return items


def apply_regions(items):
    out, i = [], 0
    while i < len(items):
        it = items[i]
        hit = False
        if it[0] == "line":
            for pg, start, end, fac in REGIONS:
                if it[1] == pg and re.search(start, clean(it[3])):
                    excl = end.startswith("!")
                    endre = end[1:] if excl else end
                    j = i
                    while j < len(items):
                        if items[j][0] == "line" and re.search(endre, clean(items[j][3])):
                            break
                        j += 1
                    if j >= len(items):
                        report["warnings"].append(f"region {start} on p{pg}: end not found")
                        break
                    last = j - 1 if excl else j
                    report["layout_fixes"].append({"page": pg, "start": start, "lines": last - i + 1})
                    for b in fac():
                        if isinstance(b, str):
                            out.append(("line", pg, 4, b))
                        else:
                            out.append(("block", pg, b))
                    i = last + 1
                    hit = True
                    break
        if not hit:
            out.append(it)
            i += 1
    return out


def build(lines):
    toc = read_toc()
    t = Tree(toc)
    items = apply_regions(normalise_lines(lines))
    t.open_chapter("1", toc.get("1", "GENERAL RULES OF POWERLIFTING").upper(), FIRST_BODY_PAGE, from_toc=True)
    prev_blank = True
    last_text = ""
    for it in items:
        if it[0] == "blank":
            prev_blank = True
            continue
        if it[0] == "block":
            t.flush()
            t.page = it[1]
            t.add_block(it[2])
            continue
        _, pg, ind, raw = it
        t.page = pg
        txt = clean(raw).strip()
        if not txt:
            continue
        # headings
        m = HEAD_SUB.match(txt)
        if m and ind < 14:
            title = m.group(2)
            t.open_section(m.group(1), title, pg)
            t.pending_title_join = True
            prev_blank = False
            continue
        if getattr(t, "pending_title_join", False):
            t.pending_title_join = False
            if re.match(r"^[A-Z][A-Z ,&/’'()\-]+$", txt) and len(txt) > 8 and t.sec["number"] == "4.2.2":
                t.sec["title"] += " " + txt
                continue
        m = HEAD_SEC.match(txt)
        if m and ind < 16 and txt == txt.upper():
            t.open_section(m.group(1), m.group(2).strip(), pg)
            prev_blank = False
            continue
        m = HEAD_CH.match(txt)
        if m and txt == txt.upper() and int(m.group(1)) <= 10 and int(m.group(1)) >= 2 and not t.stack_is_sub():
            t.open_chapter(m.group(1), m.group(2).strip(), pg)
            prev_blank = False
            continue
        if FIG_LINES.match(txt):
            t.flush()
            t.add_block(FIG(txt, kind="photo", pdf_page=pg))
            prev_blank = False
            continue
        if txt in GROUP_HEADS and t.scope() in ("3.1", "3.6", "3.9") and prev_blank:
            t.open_group(txt, page=pg)
            prev_blank = False
            continue
        if t.scope() == "6.1" and txt.startswith("The Technical Committee with the co-operation"):
            t.flush()
            t.open_group(None, page=pg)
            t.group["lead"] = txt
            # continue: the lead continues on following lines
            t.para = {"kind": "lead", "lines": [raw], "page": pg}
            prev_blank = False
            continue
        if t.para and t.para["kind"] == "lead":
            if not L_ALPHA.match(txt):
                t.para["lines"].append(raw)
                continue
            text, ranges = assemble(t.para["lines"], t.red)
            t.group["lead"] = text
            t.para = None
        # labels
        kind = label = rest = None
        if txt.startswith(BULLET):
            kind, rest = "bullet", txt[len(BULLET):]
        else:
            m = L_NUM.match(txt) or None
            if m:
                kind, label, rest = "num", m.group(1) + ")", m.group(2)
            else:
                m = L_ALPHA.match(txt)
                if m:
                    kind, label, rest = "alpha", f"({m.group(1)})", m.group(2)
                else:
                    m = re.match(r"^(\d{1,2})\. (.*)$", txt)
                    if m and t.stack and any(c["label_kind"] == "num" for c in t.stack) is False and False:
                        pass
                    m2 = re.match(r"^([A-Z]|\d)\.(?=\s|[A-Z])\s*(.*)$", txt)
                    if m2 and (t.stack or (t.group and t.group.get("title") == "Dimensions:")):
                        kind, label, rest = "sub", m2.group(1) + ".", m2.group(2)
                    elif re.match(r"^16\. The Jury", txt):
                        kind, label, rest = "num", "16.", txt[4:]
        if kind in ("num", "alpha") and not t.label_sequence_ok(kind, label):
            report["warnings"].append(f"p{pg}: label {label} out of sequence, kept as text: {txt[:50]}")
            kind = None
        if kind == "num" and t.ch["number"] == "1" and t.sec is not None:
            t.flush(); t.sec = None; t.group = None
        if kind == "bullet":
            t.flush()
            t.para = {"kind": "li", "lines": [rest if sentinel_free(raw) == txt else raw.replace(BULLET, "", 1)], "page": pg}
        elif kind in ("num", "alpha", "sub"):
            # keep sentinels: re-create the raw line without its label
            body = re.sub(r"^(" + S_ON + r")?" + re.escape(label.rstrip(".)")) + r"[.)]?\s*", lambda m: (m.group(1) or ""), raw, count=1) \
                if kind in ("num", "sub") else re.sub(r"^(" + S_ON + r")?\([a-z]\)\s*", lambda m: (m.group(1) or ""), raw, count=1)
            t.start_clause(kind, label, rest, pg, body)
            if kind == "num" and t.sec is None:
                t.last_num[t.ch["number"]] = int(label[:-1])
            elif kind == "num":
                t.last_num[t.sec["number"]] = int(label[:-1])
        else:
            # continuation or new paragraph
            if COACH_LINE.match(txt) or FAIL_LINE.match(txt):
                t.flush()
                t.para = {"kind": "line", "lines": [raw], "page": pg}
            elif t.para is None or t.para["kind"] == "line":
                t.flush()
                t.para = {"kind": "p", "lines": [raw], "page": pg}
            else:
                join = not prev_blank
                if prev_blank:
                    pt = clean(t.para["lines"][-1]).rstrip()
                    join = (not pt.endswith(TERMINAL)) or txt[:1].islower()
                if join:
                    t.para["lines"].append(raw)
                else:
                    t.flush()
                    t.para = {"kind": "p", "lines": [raw], "page": pg}
        prev_blank = False
    t.flush()
    return t


def stack_is_sub(self):
    return False


Tree.stack_is_sub = stack_is_sub


# --------------------------------------------------------------------------- finalise
def finalise(node, parent_changed=None):
    """Compute clause text + hash recursively, count changed."""
    if node["type"] in ("clause", "group", "section", "chapter"):
        texts = [c["text"] for c in node["content"] if c["type"] in ("p", "li", "line")]
        node["text"] = "\n".join(texts)
        if node["type"] == "clause":
            node["sha256"] = sha(node["text"])
        changed = any(c.get("changed") for c in node["content"] if c["type"] in ("p", "li", "line"))
        if changed:
            node["changed_2026"] = True
        for c in node["content"]:
            if c["type"] in ("clause", "group", "section", "chapter"):
                finalise(c)
        if node["type"] in ("group",):
            node["sha256"] = sha(node["text"] + (node.get("title") or "") + (node.get("lead") or ""))
        if node["type"] in ("section", "chapter"):
            node["sha256"] = sha(node.get("title", "") + node["text"])
    for c in node.get("content", []):
        if c["type"] in ("p", "li", "line") and "sha256" not in c:
            c["sha256"] = sha(c["text"])


def collect_hashes(node, acc):
    if node.get("sha256") and node["type"] in ("clause", "p", "li", "line", "table", "figure", "failure-matrix", "group", "section", "chapter"):
        acc[node["id"] if "id" in node else None] = node["sha256"]
    for c in node.get("content", []):
        collect_hashes(c, acc)


def freeze(chapters):
    """Write the hash lock once. After that it only changes through a logged correction
    or a new edition (see tools/verify.mjs); pass --refreeze to rebuild it deliberately."""
    lock = ROOT / "content" / "en" / "2026.hashes.lock.json"
    acc = {}
    for ch in chapters:
        collect_hashes(ch, acc)
    acc.pop(None, None)
    if lock.exists() and "--refreeze" not in sys.argv:
        old = json.loads(lock.read_text(encoding="utf-8"))
        if old != acc:
            diff = sorted(k for k in set(old) | set(acc) if old.get(k) != acc.get(k))
            print(f"ERROR: extraction differs from {lock.name} for {len(diff)} ids, e.g. {diff[:5]}. "
                  "If intended (new edition / logged correction) rerun with --refreeze.")
            sys.exit(2)
        return
    lock.write_text(json.dumps(acc, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    print(f"froze {len(acc)} hashes to {lock.name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines, _ = load_lines()
    t = build(lines)
    for ch in t.chapters:
        finalise(ch)
    for old in OUT.glob("*.json"):
        old.unlink()
    index = {"edition": EDITION, "effective": "2026-03-01", "source": PDF.name, "chapters": []}
    for ch in t.chapters:
        fn = f"ch-{int(ch['number']):02d}.json"
        (OUT / fn).write_text(json.dumps(ch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        index["chapters"].append({"number": ch["number"], "id": ch["id"], "title": ch["title"], "toc_title": ch["toc_title"], "file": fn, "page": ch["page"]})
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    freeze(t.chapters)
    (OUT.parent / "2026.struck.json").write_text(json.dumps(report["struck"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (ROOT / "content" / "en" / "extraction-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(t.chapters)} chapters; warnings: {len(report['warnings'])}; dedupes: {len(report['dedupe'])}; layout fixes: {len(report['layout_fixes'])}")
    for w in report["warnings"]:
        print("WARN", w)


if __name__ == "__main__":
    main()
