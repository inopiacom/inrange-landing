#!/usr/bin/env python3
"""Drift-grind för de juridiska texterna på getinrange.ai.

Engelskan är källa (Jonas 2026-09-26): `privacy.html` och `terms.html` är
kanoniska, de fem andra språken är översättningar som alltid ska följa med när
engelskan ändras. Den här grinden fäller när en översättning halkat efter.

Den letar efter STRUKTUR, aldrig efter ord. Handkontrollen 2026-09-27 grepade
efter "yemek" i turkiskan medan texten skriver "öğün" och rapporterade ett hål
som inte fanns — ett ordsvep mäter översättarens ordval, inte om stycket finns.
Blockprofilen nedan mäter i stället sekvensen av element i sidans innehåll, så
den ser både ett tappat stycke och ett extra, på alla sex språken lika.

Kör utan argument från repo-roten:

    python3 tools/legal/check-translations.py

Exit 0 = alla dokument stämmer. Exit 1 = minst ett krav brustet; varje brustet
krav skrivs ut med sida, krav och mätning.
"""

from __future__ import annotations

import argparse
import html.parser
import re
import sys
from pathlib import Path

LANGS = ["en", "sv", "es", "de", "fr", "tr"]
ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
SITE = "https://getinrange.ai/"

# Element som bär innehåll. Blockprofilen räknar dessa och stiger inte ned i dem.
BLOCK_TAGS = {"p", "ul", "ol", "h2", "h3", "h4", "h5", "h6", "blockquote", "table", "pre", "figure"}
# Element som bara håller andra element. Profilen går igenom dem.
CONTAINER_TAGS = {"main", "section", "article", "div"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


# --------------------------------------------------------------------------- #
# Minimal DOM. Ingen bs4 — grinden ska gå att köra på en naken Python 3.
# --------------------------------------------------------------------------- #

class Node:
    def __init__(self, tag: str, attrs: dict | None = None, text: str = ""):
        self.tag = tag
        self.attrs = attrs or {}
        self.text_value = text
        self.children: list[Node] = []
        self.parent: Node | None = None

    def add(self, child: "Node") -> "Node":
        child.parent = self
        self.children.append(child)
        return child

    def text(self) -> str:
        if self.tag == "#text":
            return self.text_value
        return "".join(c.text() for c in self.children)

    def flat_text(self) -> str:
        return re.sub(r"\s+", " ", self.text()).strip()

    def descendants(self):
        for c in self.children:
            yield c
            yield from c.descendants()

    def find_all(self, tag: str) -> list["Node"]:
        return [n for n in self.descendants() if n.tag == tag]

    def find(self, tag: str) -> "Node | None":
        return next((n for n in self.descendants() if n.tag == tag), None)

    def elements(self) -> list["Node"]:
        return [c for c in self.children if c.tag != "#text"]


class _Builder(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = self.stack[-1].add(Node(tag, dict(attrs)))
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].add(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].add(Node("#text", text=data))


def parse(path: Path) -> Node:
    b = _Builder()
    b.feed(path.read_text(encoding="utf-8"))
    return b.root


# --------------------------------------------------------------------------- #
# Dokumentmodell
# --------------------------------------------------------------------------- #

class Document:
    """Ett juridiskt dokument i sina sex språkversioner."""

    def __init__(self, key: str, stem: str, *, needs_language_clause: bool):
        self.key = key
        self.stem = stem
        self.needs_language_clause = needs_language_clause

    def filename(self, lang: str) -> str:
        return f"{self.stem}.html" if lang == "en" else f"{self.stem}-{lang}.html"

    @property
    def english_file(self) -> str:
        return self.filename("en")


DOCUMENTS = [
    # Villkoren bär språkklausul på alla sex språk — den är sakinnehåll i
    # avtalet, inte en översättningsnotis, och engelskan ska ha den också.
    Document("terms", "terms", needs_language_clause=True),
    # Policyn bär ingen språkklausul. Informationsplikt enligt GDPR art. 12 går
    # inte att friskriva sig från; den bär källnot i stället, som alla
    # översättningar gör.
    Document("privacy", "privacy", needs_language_clause=False),
]


class Failure:
    def __init__(self, page: str, requirement: str, detail: str):
        self.page, self.requirement, self.detail = page, requirement, detail

    def __str__(self) -> str:
        return f"FAIL  {self.page:<20} [{self.requirement}]  {self.detail}"


# --------------------------------------------------------------------------- #
# Klassificerare — allt strukturellt, inget ordsvep
# --------------------------------------------------------------------------- #

def is_source_note(node: Node, doc: Document) -> bool:
    """Källnoten: stycket som länkar till engelskan OCH bär ett versionsdatum.

    Formen är kravet, inte lydelsen: en översättning måste peka ut vilken
    engelsk version den bygger på och länka dit. Samma test används för att
    slå fast att engelskan INTE bär en källnot — den har ingen källa att peka
    tillbaka på.
    """
    if node.tag != "p":
        return False
    links_home = any(a.attrs.get("href") == doc.english_file for a in node.find_all("a"))
    return links_home and bool(ISO_DATE.search(node.flat_text()))


def is_header_date(node: Node) -> bool:
    """Datumrad i sidhuvudet: en etikett och ett datum, inget annat.

    Träffar "Last updated: 2026-09-22", "Dernière mise à jour : 2026-09-22",
    "Son güncelleme: 2026-09-22" utan att veta vad orden betyder.
    """
    return node.tag == "p" and bool(re.fullmatch(r"[^.:]{0,60}[:：]\s*\d{4}-\d{2}-\d{2}", node.flat_text()))


def content_blocks(main: Node, doc: Document) -> list[Node]:
    """Innehållsblocken i dokumentordning, utan sidhuvudets apparat.

    Språkväljaren, källnoten, h1 och datumraderna hör till sidan, inte till
    avtalet — de finns i olika antal på engelskan och på en översättning och
    skulle annars göra varje jämförelse falskt röd.
    """
    out: list[Node] = []

    def walk(node: Node) -> None:
        for child in node.elements():
            if child.tag in ("nav", "h1"):
                continue
            if child.tag in BLOCK_TAGS:
                if is_source_note(child, doc) or is_header_date(child):
                    continue
                out.append(child)
                continue
            if child.tag in CONTAINER_TAGS:
                walk(child)

    walk(main)
    return out


def block_profile(main: Node, doc: Document) -> list[str]:
    """Blockprofil: elementsekvensen, med postantal på listor.

    Det här är grindens kärna. Två språkversioner av samma dokument ska ha
    identisk profil. Skiljer de sig har någon tappat eller lagt till ett
    stycke, en lista eller en rubrik — och profilen säger vilket, i båda
    riktningarna, utan att jämföra ett enda ord.
    """
    profile = []
    for b in content_blocks(main, doc):
        if b.tag in ("ul", "ol"):
            profile.append(f"{b.tag}[{len([c for c in b.elements() if c.tag == 'li'])}]")
        else:
            profile.append(b.tag)
    return profile


def sentence_count(text: str) -> int:
    """Antal meningar. Grov men riktningsstabil över de sex språken."""
    return len([s for s in re.split(r"(?<=[.!?])\s+(?=[^a-zçğıöşü])", text.strip()) if s])


# --------------------------------------------------------------------------- #
# Kraven
# --------------------------------------------------------------------------- #

def check_document(root: Path, doc: Document, failures: list[Failure], verbose: bool) -> None:
    pages: dict[str, Node] = {}
    mains: dict[str, Node] = {}

    for lang in LANGS:
        path = root / doc.filename(lang)
        if not path.exists():
            failures.append(Failure(doc.filename(lang), "sidan finns", f"saknas på disk: {path}"))
            continue
        pages[lang] = parse(path)
        main = pages[lang].find("main")
        if main is None:
            failures.append(Failure(doc.filename(lang), "struktur", "inget <main> i dokumentet"))
            continue
        mains[lang] = main

    if "en" not in mains:
        failures.append(Failure(doc.english_file, "källa", "engelskan är källa och måste finnas och gå att läsa"))
        return

    en_main = mains["en"]
    en_profile = block_profile(en_main, doc)
    en_dates = ISO_DATE.findall(" ".join(b.flat_text() for b in header_paragraphs(en_main, doc)))
    en_version = en_dates[0] if en_dates else None
    en_h2 = len([b for b in content_blocks(en_main, doc) if b.tag == "h2"])

    if en_version is None:
        failures.append(Failure(doc.english_file, "version", "ingen datumrad i sidhuvudet; källans version går inte att läsa av"))

    if verbose:
        print(f"  {doc.english_file:<20} version={en_version}  h2={en_h2}  block={len(en_profile)}")

    for lang in LANGS:
        if lang not in mains:
            continue
        name = doc.filename(lang)
        page, main = pages[lang], mains[lang]
        is_translation = lang != "en"

        # --- html lang ------------------------------------------------------
        html_el = page.find("html")
        if html_el is None or html_el.attrs.get("lang") != lang:
            got = None if html_el is None else html_el.attrs.get("lang")
            failures.append(Failure(name, "html lang", f"väntade lang=\"{lang}\", fick {got!r}"))

        # --- hreflang -------------------------------------------------------
        alts = {
            l.attrs["hreflang"]: l.attrs.get("href", "")
            for l in page.find_all("link")
            if l.attrs.get("rel") == "alternate" and "hreflang" in l.attrs
        }
        expected = {l: SITE + doc.filename(l) for l in LANGS}
        expected["x-default"] = SITE + doc.english_file
        missing = sorted(set(expected) - set(alts))
        if missing:
            failures.append(Failure(name, "hreflang", f"saknar alternate för {', '.join(missing)}"))
        for code, href in sorted(alts.items()):
            if code in expected and href != expected[code]:
                failures.append(Failure(name, "hreflang", f"{code} pekar på {href!r}, väntade {expected[code]!r}"))
            elif code not in expected:
                failures.append(Failure(name, "hreflang", f"okänd språkkod {code!r} i alternate-listan"))

        # --- språkväljare ---------------------------------------------------
        navs = [n for n in main.find_all("nav")]
        if not navs:
            failures.append(Failure(name, "språkväljare", "ingen <nav> i <main>"))
        else:
            nav = navs[0]
            reachable = {a.attrs.get("hreflang"): a.attrs.get("href", "") for a in nav.find_all("a") if a.attrs.get("hreflang")}
            for other in LANGS:
                if other == lang:
                    if other in reachable:
                        failures.append(Failure(name, "språkväljare", f"sidan länkar till sig själv ({other}); det aktiva språket ska inte vara en länk"))
                    continue
                if other not in reachable:
                    failures.append(Failure(name, "språkväljare", f"når inte {other}"))
                elif reachable[other] != doc.filename(other):
                    failures.append(Failure(name, "språkväljare", f"{other} pekar på {reachable[other]!r}, väntade {doc.filename(other)!r}"))
            for code in reachable:
                if code not in LANGS:
                    failures.append(Failure(name, "språkväljare", f"okänd språkkod {code!r}"))

        # --- källnot --------------------------------------------------------
        notes = [b for b in all_paragraphs(main) if is_source_note(b, doc)]
        if is_translation:
            if not notes:
                failures.append(Failure(name, "källnot", f"saknas; en översättning ska peka ut vilken version av {doc.english_file} den bygger på och länka dit"))
            elif len(notes) > 1:
                failures.append(Failure(name, "källnot", f"{len(notes)} stycken ser ut som källnot; det ska vara exakt ett"))
            else:
                marker = ISO_DATE.search(notes[0].flat_text()).group(1)
                if en_version and marker != en_version:
                    failures.append(Failure(name, "version", f"källnoten säger {marker}, men {doc.english_file} bär {en_version} — översättningen har halkat efter"))
        elif notes:
            failures.append(Failure(name, "källnot", "engelskan bär en källnot; den är källa och har ingen version att peka tillbaka på"))

        # --- egen datumrad mot källans ---------------------------------------
        own_dates = ISO_DATE.findall(" ".join(b.flat_text() for b in header_paragraphs(main, doc)))
        if own_dates != en_dates:
            failures.append(Failure(name, "version", f"datumraderna i sidhuvudet är {own_dates or '[]'}, engelskan har {en_dates or '[]'}"))

        # --- språkklausul ----------------------------------------------------
        clauses = [n for n in main.descendants() if n.attrs.get("id") == "language-clause"]
        if doc.needs_language_clause:
            if not clauses:
                failures.append(Failure(name, "språkklausul", 'saknas: inget element med id="language-clause" i <main>'))
            elif len(clauses) > 1:
                failures.append(Failure(name, "språkklausul", f'{len(clauses)} element bär id="language-clause"; id ska vara unikt'))
            elif is_translation and clauses:
                # Sista meningen i klausulen är juridiskt bärande: utan den kan
                # klausulen själv vara ett oskäligt villkor (dir. 93/13/EEG).
                # Mät antalet meningar mot engelskan i stället för att leta
                # efter en fras, så håller kontrollen även när engelskan skrivs om.
                en_clause = next((n for n in en_main.descendants() if n.attrs.get("id") == "language-clause"), None)
                if en_clause is not None:
                    want, got = sentence_count(en_clause.flat_text()), sentence_count(clauses[0].flat_text())
                    if got != want:
                        failures.append(Failure(name, "språkklausul", f"{got} meningar mot engelskans {want} — kontrollera att den avslutande meningen om tvingande konsumenträttigheter finns kvar"))
        elif clauses:
            failures.append(Failure(name, "språkklausul", f"{doc.key} ska inte bära en språkklausul; policyn bär källnot i stället"))

        # --- blockprofil, båda riktningarna ---------------------------------
        if is_translation:
            profile = block_profile(main, doc)
            if profile != en_profile:
                failures.append(Failure(name, "innehållsprofil", describe_profile_diff(en_profile, profile)))
            else:
                h2 = len([b for b in content_blocks(main, doc) if b.tag == "h2"])
                if h2 != en_h2:
                    failures.append(Failure(name, "avsnitt", f"{h2} <h2> mot engelskans {en_h2}"))

        if verbose and is_translation:
            print(f"  {name:<20} version={(ISO_DATE.search(notes[0].flat_text()).group(1) if notes else '?')}  h2={len([b for b in content_blocks(main, doc) if b.tag == 'h2'])}  block={len(block_profile(main, doc))}")


def all_paragraphs(main: Node) -> list[Node]:
    return [n for n in main.descendants() if n.tag == "p"]


def header_paragraphs(main: Node, doc: Document) -> list[Node]:
    """Datumraderna i sidhuvudet, källnoten undantagen."""
    return [p for p in all_paragraphs(main) if is_header_date(p)]


def describe_profile_diff(want: list[str], got: list[str]) -> str:
    for i, (a, b) in enumerate(zip(want, got)):
        if a != b:
            ctx = " ".join(want[max(0, i - 2):i]) or "början"
            return f"block {i + 1} är <{b}>, engelskan har <{a}> (efter: {ctx}) — ett stycke är tappat, tillagt eller omflyttat"
    if len(got) > len(want):
        return f"{len(got) - len(want)} block för många: {' '.join(got[len(want):])} finns inte i engelskan"
    return f"{len(want) - len(got)} block saknas mot engelskan: {' '.join(want[len(got):])}"


def check_sitemap(root: Path, failures: list[Failure]) -> None:
    """Varje språkversion ska ligga i sitemap.xml.

    Turkiskan var onåbar delvis för att den saknades här. En sida som inte
    står i sitemap är osynlig men ser publicerad ut.
    """
    path = root / "sitemap.xml"
    if not path.exists():
        failures.append(Failure("sitemap.xml", "sitemap", "saknas"))
        return
    body = path.read_text(encoding="utf-8")
    for doc in DOCUMENTS:
        for lang in LANGS:
            loc = f"<loc>{SITE}{doc.filename(lang)}</loc>"
            if loc not in body:
                failures.append(Failure("sitemap.xml", "sitemap", f"{doc.filename(lang)} saknas"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Fäller när en juridisk översättning halkat efter engelskan.")
    ap.add_argument("--root", default=Path(__file__).resolve().parents[2], type=Path, help="repo-roten (default: två nivåer upp från skriptet)")
    ap.add_argument("-v", "--verbose", action="store_true", help="skriv ut mätningen per sida även när allt stämmer")
    args = ap.parse_args()

    failures: list[Failure] = []
    for doc in DOCUMENTS:
        if args.verbose:
            print(f"{doc.key}:")
        check_document(args.root, doc, failures, args.verbose)
    check_sitemap(args.root, failures)

    if failures:
        for f in failures:
            print(f)
        print(f"\n{len(failures)} krav brustet." if len(failures) == 1 else f"\n{len(failures)} krav brustna.")
        return 1

    pages = len(DOCUMENTS) * len(LANGS)
    print(f"OK  {len(DOCUMENTS)} dokument × {len(LANGS)} språk = {pages} sidor stämmer med engelskan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
