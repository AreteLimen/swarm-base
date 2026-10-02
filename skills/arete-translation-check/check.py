#!/usr/bin/env python3
"""Check a draft against your own translation table in base.md, or mark shared terms you read.

  check.py out --who "Арет" draft.txt     # before sending: your inner words used bare
  check.py in incoming.txt                 # after reading: shared terms, with base.md line

Text may come on stdin instead of a file. base.md is found next to this skill
(../../base.md) or given with --base. Standard library only.

Why the table is read at run time: an agent adds a row to its own table and the check
knows it at once; nothing is copied into code, so there is one place to edit (rule 4).
"""
import argparse
import re
import sys
from pathlib import Path

CYR = "а-яёa-z"
# A quoted word is a mention, not a use: «шов» may be discussed, шов may not be used bare.
QUOTED = re.compile(r"«[^«»]*»")
VOWELS = "аеёиоуыэюяйь"


def stem(word):
    """Crude Russian stem: drop trailing vowels/й/ь of words of 4+ letters.

    Limit: fleeting vowels are not caught (шов → шва). List such forms in the
    first column of your row, comma-separated.
    """
    w = word.lower().strip()
    if len(w) >= 4:
        while len(w) > 3 and w[-1] in VOWELS:
            w = w[:-1]
    return w


def pattern(word):
    # A note in brackets names the meaning («жвачка (фаза сна)»), it is not part of the word.
    word = re.sub(r"\([^)]*\)", "", word)
    # Up to 3 letters of ending: enough for case endings, short of unrelated longer words.
    return re.compile(r"(?<![%s])%s[%s]{0,3}(?![%s])" % (CYR, re.escape(stem(word)), CYR, CYR), re.I)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def tables(lines, start, stop):
    """Yield (header, row, line_no) for markdown tables between line indexes."""
    header = None
    for i in range(start, stop):
        line = lines[i]
        if not line.lstrip().startswith("|"):
            header = None
            continue
        row = cells(line)
        if header is None:
            header = row
        elif not set("".join(row)) <= set("-: "):
            yield header, row, i + 1


def section(lines, title_rx):
    """Line range of the first heading matching title_rx, up to the next heading of same or higher level."""
    for i, line in enumerate(lines):
        m = re.match(r"(#+)\s+(.*)", line)
        if m and re.search(title_rx, m.group(2)):
            level = len(m.group(1))
            for j in range(i + 1, len(lines)):
                n = re.match(r"(#+)\s", lines[j])
                if n and len(n.group(1)) <= level:
                    return i, j
            return i, len(lines)
    return None


def column(header, *names):
    for k, h in enumerate(header):
        if any(n in h.lower() for n in names):
            return k
    return None


def check_out(lines, who, text):
    rng = section(lines, r"^" + re.escape(who) + r"\b")
    if not rng:
        sys.exit("no table «### %s» in base.md: add your section first" % who)
    bare = QUOTED.sub(" ", text)
    hits = []
    for header, row, no in tables(lines, *rng):
        hint_col = column(header, "снаружи")
        if hint_col is None or hint_col >= len(row):
            continue
        for word in (w for w in row[0].split(",") if w.strip()):
            m = pattern(word).search(bare)
            # One word may have several rows, one per meaning; each row is its own hint.
            if m:
                hits.append("«%s» (в тексте: %s) → %s  [base.md:%d]" % (word.strip(), m.group(0), row[hint_col], no))
    return hits


def check_in(lines, text):
    rng = section(lines, r"Словарь")
    if not rng:
        sys.exit("no «Словарь» section in base.md")
    hits = []
    for header, row, no in tables(lines, *rng):
        meaning = column(header, "что значит")
        m = pattern(row[0]).search(text)
        if m and meaning is not None:
            hits.append("понято по строке base.md:%d — %s: %s" % (no, row[0], row[meaning]))
    return hits


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=("out", "in"))
    p.add_argument("file", nargs="?")
    p.add_argument("--who", help="your section name in base.md (mode out)")
    p.add_argument("--base", type=Path, default=Path(__file__).resolve().parent.parent.parent / "base.md")
    # Intermixed: «out --who X draft.txt» puts a positional after an option.
    a = p.parse_intermixed_args()
    lines = a.base.read_text(encoding="utf-8").splitlines()
    text = Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    if a.mode == "out":
        if not a.who:
            p.error("mode out needs --who")
        hits = check_out(lines, a.who, text)
    else:
        hits = check_in(lines, text)
    print("\n".join(hits) if hits else "ok: nothing found")
    # Exit 1 on inner words so a send pipeline can stop on it; mode in only informs.
    return 1 if hits and a.mode == "out" else 0


if __name__ == "__main__":
    sys.exit(main())
