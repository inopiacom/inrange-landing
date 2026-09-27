#!/usr/bin/env python3
"""Bevis att drift-grinden faktiskt fäller.

En grind som aldrig fällt är dekoration: den kan vara grön för att trädet
stämmer, eller för att den mäter fel sak. Varje test här skadar en kopia av
trädet på ett bestämt sätt och kräver att `check-translations.py` går ut med
exit 1 OCH pekar på rätt sida och rätt krav. Sista testet kräver att det
orörda trädet är grönt, så att ingen av skadorna kan ha varit gratis.

    python3 tools/legal/test-check-translations.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(__file__).resolve().parent / "check-translations.py"
PAGES = sorted(ROOT.glob("privacy*.html")) + sorted(ROOT.glob("terms*.html")) + [ROOT / "sitemap.xml"]


def sandbox() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="legal-gate-"))
    for p in PAGES:
        shutil.copy2(p, tmp / p.name)
    return tmp


def run(root: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(CHECKER), "--root", str(root)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def edit(root: Path, name: str, fn) -> None:
    p = root / name
    before = p.read_text(encoding="utf-8")
    after = fn(before)
    assert after != before, f"mutationen ändrade ingenting i {name} — testet mäter inget"
    p.write_text(after, encoding="utf-8")


def drop_nth(pattern: str, n: int):
    """Ta bort den n:te förekomsten av ett mönster (1-indexerat)."""
    def apply(text: str) -> str:
        hits = list(re.finditer(pattern, text, re.S))
        assert len(hits) >= n, f"färre än {n} träffar för {pattern!r}"
        m = hits[n - 1]
        return text[: m.start()] + text[m.end() :]
    return apply


def drop_last_sentence_of_clause(text: str) -> str:
    m = re.search(r'(<p id="language-clause"[^>]*>)(.*?)(</p>)', text, re.S)
    assert m, 'ingen <p id="language-clause"> att skada'
    parts = [s for s in re.split(r"(?<=\.)\s+", m.group(2).strip()) if s]
    assert len(parts) >= 2, "klausulen har inte flera meningar"
    return text[: m.start(2)] + "\n      " + " ".join(parts[:-1]) + "\n    " + text[m.end(2) :]


CASES = [
    # (namn, mutation, sida som ska pekas ut, krav som ska brista)
    (
        "engelskan bumpas utan att översättningarna följer med",
        lambda r: edit(r, "terms.html", lambda t: t.replace("2026-09-26", "2026-10-01")),
        "terms-sv.html", "version",
    ),
    (
        "ett stycke tappas i en översättning",
        lambda r: edit(r, "privacy-tr.html", drop_nth(r"<p>.*?</p>", 3)),
        "privacy-tr.html", "innehållsprofil",
    ),
    (
        "ett extra stycke smygs in i ett språk",
        lambda r: edit(r, "privacy-fr.html", lambda t: t.replace("</section>", "<p>Une clause qui n’existe pas en anglais.</p>\n    </section>")),
        "privacy-fr.html", "innehållsprofil",
    ),
    (
        "en listpost faller bort",
        lambda r: edit(r, "privacy-de.html", drop_nth(r"<li>.*?</li>", 1)),
        "privacy-de.html", "innehållsprofil",
    ),
    (
        "ett avsnitt (h2) tappas",
        lambda r: edit(r, "privacy-es.html", drop_nth(r"<h2[^>]*>.*?</h2>", 5)),
        "privacy-es.html", "innehållsprofil",
    ),
    (
        "språkväljaren tappar ett språk",
        lambda r: edit(r, "privacy-de.html", drop_nth(r' · <a href="privacy-tr\.html" hreflang="tr".*?</a>', 1)),
        "privacy-de.html", "språkväljare",
    ),
    (
        "hreflang tappas ur head",
        lambda r: edit(r, "terms-sv.html", drop_nth(r'\s*<link rel="alternate" hreflang="tr"[^>]*>', 1)),
        "terms-sv.html", "hreflang",
    ),
    (
        "källnoten saknas på en översättning",
        lambda r: edit(r, "terms-es.html", drop_nth(r'<p style="color:var\(--fg-2\);margin-bottom:40px;padding:14px 16px.*?</p>', 1)),
        "terms-es.html", "källnot",
    ),
    (
        "engelskan bär en källnot den inte ska ha",
        lambda r: edit(r, "terms.html", lambda t: t.replace(
            "    <p style=\"color:var(--fg-1);margin-bottom:24px\">",
            '    <p>This page is a translation of the English terms, version <strong>2026-09-26</strong>. <a href="terms.html">Read the English original</a>.</p>\n'
            "    <p style=\"color:var(--fg-1);margin-bottom:24px\">", 1)),
        "terms.html", "källnot",
    ),
    (
        "språkklausulen försvinner ur villkoren",
        lambda r: edit(r, "terms-tr.html", lambda t: t.replace(' id="language-clause"', "")),
        "terms-tr.html", "språkklausul",
    ),
    (
        "klausulens bärande slutmening tappas",
        lambda r: edit(r, "terms-de.html", drop_last_sentence_of_clause),
        "terms-de.html", "språkklausul",
    ),
    (
        "html lang är fel",
        lambda r: edit(r, "privacy-fr.html", lambda t: t.replace('<html lang="fr">', '<html lang="en">', 1)),
        "privacy-fr.html", "html lang",
    ),
    (
        "en sida ligger inte i sitemap",
        lambda r: edit(r, "sitemap.xml", drop_nth(r'\s*<url><loc>https://getinrange\.ai/terms-tr\.html</loc>.*?</url>', 1)),
        "sitemap.xml", "sitemap",
    ),
    (
        "en språkversion finns inte på disk",
        lambda r: (r / "terms-fr.html").unlink(),
        "terms-fr.html", "sidan finns",
    ),
    (
        "datumraden i sidhuvudet avviker från engelskans",
        lambda r: edit(r, "privacy-sv.html", lambda t: t.replace("Gäller från: 2026-09-22", "Gäller från: 2026-09-15", 1)),
        "privacy-sv.html", "version",
    ),
]


def main() -> int:
    failed = 0

    for label, mutate, page, requirement in CASES:
        root = sandbox()
        try:
            mutate(root)
            code, out = run(root)
            hit = any(page in line and f"[{requirement}]" in line for line in out.splitlines())
            if code != 0 and hit:
                print(f"PASS  {label}")
            else:
                failed += 1
                print(f"FAIL  {label}\n      exit={code}, väntade en rad med {page} + [{requirement}]\n{out}")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    root = sandbox()
    try:
        code, out = run(root)
        if code == 0:
            print("PASS  orört träd är grönt")
        else:
            failed += 1
            print(f"FAIL  orört träd är inte grönt\n{out}")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    total = len(CASES) + 1
    print(f"\n{total - failed}/{total} bevis höll." if failed else f"\n{total}/{total} bevis höll.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
