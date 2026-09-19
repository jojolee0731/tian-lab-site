#!/usr/bin/env python3
"""Check the generated Tian Lab site without third-party dependencies.

Run from any directory: python3 scripts/check_site.py
The preserved data/site.json is the content baseline, not a runtime dependency.
Checks cover the generated HTML, local link graph, and preservation of the
previously published people/publications. External availability and visual
quality require separate checks.

Optional decision files permit only explicit content deltas: chosenDOIs in
data/publication-selection.json, and removedPeople/addedPeople in data/content-decisions.json.
Without these decisions, the original catalog-preservation rules still apply.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


PAGES = ("index", "research", "publications", "people", "join", "collaborate", "news")
LANGUAGES = {"": "en", "zh": "zh-CN", "es": "es"}
SITE_URL = "https://jojolee0731.github.io/tian-lab-site/"
SITE_PATH = "/tian-lab-site/"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

# Corrections already identified against the formal publication records.
DOI_CORRECTIONS = {"10.1016/j.arr.2026.102952": "10.1016/j.arr.2025.102952"}
BBE_LEGACY_TITLE = "Molecular Mechanism of TERRA-Mediated Telomeric t-loop Formation and Its Structural Reduction in Aging Models Revealed by a Cyclometalated Iridium(III) Complex through Super-Resolution Imaging"
BBE_DOI = "10.1016/j.bios.2026.118655"


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    children: list = field(default_factory=list)

    def text(self) -> str:
        if self.tag == "img":
            return self.attrs.get("alt", "")
        return " ".join(child.text() if isinstance(child, Node) else child for child in self.children).strip()


class Document(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.nodes: list[Node] = []
        self.stack: list[Node] = []
        self.feed(path.read_text(encoding="utf-8"))
        self.close()
        self.ids = {n.attrs["id"]: n for n in self.nodes if n.attrs.get("id")}

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.getpos()[0])
        self.nodes.append(node)
        if self.stack:
            self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].children.append(data)

    def by_tag(self, tag):
        return [n for n in self.nodes if n.tag == tag]

    def accessible_name(self, node):
        if node.attrs.get("aria-label", "").strip():
            return node.attrs["aria-label"].strip()
        label_ids = node.attrs.get("aria-labelledby", "").split()
        if label_ids:
            return " ".join(self.ids[k].text() for k in label_ids if k in self.ids).strip()
        return node.text() or node.attrs.get("title", "").strip()


def normalized_title(value):
    return re.sub(r"\W+", "", str(value).casefold())


def doi_from(record):
    value = str(record.get("doi") or "").strip()
    if not value:
        value = str(record.get("url") or "").strip()
    match = re.search(r"10\.\d{4,9}/[^\s?#]+", unquote(value), flags=re.I)
    if not match:
        return None
    doi = match.group(0).lower().rstrip(".,;")
    return DOI_CORRECTIONS.get(doi, doi)


def paper_identity(record):
    doi = doi_from(record)
    if doi:
        return doi
    if normalized_title(record.get("title", "")) == normalized_title(BBE_LEGACY_TITLE):
        return BBE_DOI
    return "title:" + normalized_title(record.get("title", ""))


def records_from(data, category):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", category):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Expected an array or an object containing items/{category}")


def person_name(record):
    name = record.get("name", record.get("nameZh", ""))
    if isinstance(name, dict):
        name = name.get("zh", name.get("en", ""))
    return str(name).strip()


def person_identity(record):
    # An unchanged public email permits correction of a person's name spelling.
    email = str(record.get("email") or "").strip().casefold()
    return "email:" + email if email else "name:" + person_name(record)


def baseline_person_id(record, index):
    """Legacy site.json had no IDs; migration assigned stable source-order IDs."""
    return str(record.get("id") or f"member-{index + 1:02d}")


def approved_additions(selection, original_ids, fail):
    """Parse an exact allowlist, not a blanket permission to add publications."""
    path = "data/publication-selection.json"
    if not selection:
        return set()
    if not isinstance(selection, dict):
        fail(f"{path}: expected an object containing chosenDOIs")
        return set()
    values = selection.get("chosenDOIs", [])
    if not isinstance(values, list):
        fail(f"{path}: chosenDOIs must be a list of DOI strings")
        return set()
    chosen = set()
    for value in values:
        if not isinstance(value, str) or not re.fullmatch(r"10\.\d{4,9}/[^\s?#]+", value.strip(), re.I):
            fail(f"{path}: invalid chosen DOI: {value!r}")
            continue
        identity = doi_from({"doi": value})
        if identity in chosen:
            fail(f"{path}: duplicate chosen DOI: {identity}")
        elif identity in original_ids:
            fail(f"{path}: chosenDOIs must identify additions, not an existing work: {identity}")
        chosen.add(identity)
    return chosen


def approved_removals(decisions, original_people, fail):
    """Resolve each authorized removal against both original member ID and name."""
    path = "data/content-decisions.json"
    if not decisions:
        return set()
    if not isinstance(decisions, dict):
        fail(f"{path}: expected an object containing removedPeople")
        return set()
    values = decisions.get("removedPeople", [])
    if not isinstance(values, list):
        fail(f"{path}: removedPeople must be a list")
        return set()
    original = {baseline_person_id(record, i): record for i, record in enumerate(original_people)}
    removed = set()
    seen = set()
    for decision in values:
        if not isinstance(decision, dict):
            fail(f"{path}: each removedPeople entry must contain id, name, and reason")
            continue
        identity = decision.get("id")
        name = decision.get("name")
        reason = decision.get("reason")
        if not all(isinstance(value, str) and value.strip() for value in (identity, name, reason)):
            fail(f"{path}: removal requires nonempty id, name, and reason: {decision!r}")
            continue
        if identity in seen:
            fail(f"{path}: duplicate member removal: {identity}")
            continue
        seen.add(identity)
        if identity not in original:
            fail(f"{path}: removal ID does not occur in the baseline: {identity}")
            continue
        if name.strip() != person_name(original[identity]):
            fail(f"{path}: removal name does not match baseline member {identity}: {name!r}")
            continue
        removed.add(identity)
    return removed


def approved_people_additions(decisions, original_people, fail):
    """Accept only explicitly named new IDs; a removed ID may never be reused."""
    path = "data/content-decisions.json"
    if not decisions or not isinstance(decisions, dict):
        return {}
    values = decisions.get("addedPeople", [])
    if not isinstance(values, list):
        fail(f"{path}: addedPeople must be a list")
        return {}
    original_ids = {baseline_person_id(record, i) for i, record in enumerate(original_people)}
    original_names = {person_name(record) for record in original_people}
    added = {}
    for decision in values:
        if not isinstance(decision, dict) or not all(isinstance(decision.get(key), str) and decision[key].strip() for key in ("id", "name", "reason")):
            fail(f"{path}: addition requires nonempty id, name, and reason")
            continue
        identity, name = decision['id'], decision['name'].strip()
        if not re.fullmatch(r"member-\d{2,}", identity) or identity in original_ids or name in original_names:
            fail(f"{path}: addition must use a new stable ID and a new member name: {identity}")
            continue
        if identity in added or name in added.values():
            fail(f"{path}: duplicate member addition: {identity}")
            continue
        added[identity] = name
    return added


def check_preservation(baseline, datasets, decisions, selection, fail):
    """Require baseline content minus named removals plus the exact DOI allowlist."""
    old_papers = baseline.get("publications", []) + baseline.get("recentPublications", [])
    original_paper_ids = {paper_identity(p) for p in old_papers}
    added_ids = approved_additions(selection, original_paper_ids, fail)
    original_people = baseline.get("people", [])
    removed_ids = approved_removals(decisions, original_people, fail)
    added_people = approved_people_additions(decisions, original_people, fail)
    expected_people = [p for i, p in enumerate(original_people) if baseline_person_id(p, i) not in removed_ids]

    if "publications" in datasets:
        new_papers = datasets["publications"]
        new_ids = {paper_identity(p) for p in new_papers}
        if len(new_ids) != len(new_papers):
            fail("data/publications.json: duplicate publication identity/DOI")
        for identity in sorted(original_paper_ids - new_ids):
            fail(f"data/publications.json: previously published work missing: {identity}")
        actual_additions = new_ids - original_paper_ids
        for identity in sorted(actual_additions - added_ids):
            fail(f"data/publications.json: unselected/new work added to catalog: {identity}")
        for identity in sorted(added_ids - actual_additions):
            fail(f"data/publications.json: approved new work not added to catalog: {identity}")

    if "people" in datasets:
        new_people = datasets["people"]
        expected_count = len(expected_people) + len(added_people)
        if expected_count != len(new_people):
            fail(f"data/people.json: expected {expected_count} current members after {len(removed_ids)} approved removal(s) and {len(added_people)} approved addition(s), found {len(new_people)}")
        expected_identities = Counter(person_identity(p) for p in expected_people)
        new_identities = Counter(person_identity(p) for p in new_people if p.get('id') not in added_people)
        for person in new_people:
            if person.get('id') in added_people and person_name(person) != added_people[person['id']]:
                fail(f"data/people.json: added member name does not match authorized ID: {person['id']}")
        for identity in sorted((expected_identities - new_identities).elements()):
            fail(f"data/people.json: existing member identity not preserved: {identity}")
        for identity in sorted((new_identities - expected_identities).elements()):
            fail(f"data/people.json: unexpected or explicitly removed member identity: {identity}")
        expected_ids = ({baseline_person_id(p, i) for i, p in enumerate(original_people)} - removed_ids) | set(added_people)
        actual_ids = {str(p.get("id", "")) for p in new_people}
        for identity in sorted(expected_ids - actual_ids):
            fail(f"data/people.json: stable member ID not preserved: {identity}")
        for identity in sorted(actual_ids - expected_ids):
            fail(f"data/people.json: unexpected or explicitly removed member ID: {identity}")

    return len(original_paper_ids), len(added_ids), len(removed_ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, help="Preserved original site.json; defaults to <root>/data/site.json")
    args = parser.parse_args()
    root = args.root.resolve()
    baseline_path = (args.baseline or root / "data/site.json").resolve()
    errors = []
    documents = {}
    local_reference_count = 0

    def fail(message):
        errors.append(message)

    def relative(path):
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)

    def read_json(path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fail(f"{relative(path)}: cannot read JSON: {exc}")
            return None

    def read_optional_decisions(path):
        if not path.exists():
            return {}
        try:
            content = path.read_text(encoding="utf-8").strip()
            return json.loads(content) if content else {}
        except (OSError, ValueError) as exc:
            fail(f"{relative(path)}: cannot read decision JSON: {exc}")
            return {}

    def get_document(path):
        if path not in documents:
            try:
                documents[path] = Document(path)
            except (OSError, UnicodeError) as exc:
                fail(f"{relative(path)}: cannot parse HTML: {exc}")
                return None
        return documents[path]

    # Member pages follow stable current-roster IDs, not a fixed page-count limit.
    roster_data = read_json(root / "data/people.json")
    member_pages = []
    if roster_data is not None:
        try:
            for person in records_from(roster_data, "people"):
                identity = person.get("id", "")
                if not isinstance(identity, str) or not re.fullmatch(r"member-\d{2,}", identity):
                    fail("data/people.json: unsafe or missing member ID for a public page")
                else:
                    member_pages.append("person-" + identity)
        except ValueError as exc:
            fail(f"data/people.json: {exc}")
    expected_documents = {}
    for prefix, language in LANGUAGES.items():
        for page in (*PAGES, *member_pages):
            path = (root / prefix / f"{page}.html").resolve()
            if not path.is_file():
                fail(f"{relative(path)}: required generated page missing")
                continue
            document = get_document(path)
            if document is None:
                continue
            expected_documents[(prefix, page)] = document
            html = document.by_tag("html")
            if len(html) != 1 or html[0].attrs.get("lang") != language:
                fail(f"{relative(path)}: expected one html element with lang={language!r}")
            h1 = document.by_tag("h1")
            if len(h1) != 1 or not h1[0].text():
                fail(f"{relative(path)}: expected one nonempty h1; found {len(h1)}")
            mains = document.by_tag("main")
            if len(mains) != 1 or mains[0].attrs.get("id") != "main":
                fail(f"{relative(path)}: expected one main element with id=main")
            ids = Counter(n.attrs["id"] for n in document.nodes if n.attrs.get("id"))
            for identity, count in ids.items():
                if count != 1:
                    fail(f"{relative(path)}: duplicate id {identity!r} ({count} uses)")
            for button in document.by_tag("button"):
                if not document.accessible_name(button):
                    fail(f"{relative(path)}:{button.line}: button has no accessible name")
            for image in document.by_tag("img"):
                if "alt" not in image.attrs:
                    fail(f"{relative(path)}:{image.line}: image is missing alt (empty is allowed for decorative images)")
            if not any(n.attrs.get("name") == "viewport" for n in document.by_tag("meta")):
                fail(f"{relative(path)}: responsive viewport metadata missing")
            canonicals = [n.attrs.get("href", "") for n in document.by_tag("link") if "canonical" in n.attrs.get("rel", "").split()]
            expected_url = SITE_URL + (prefix + "/" if prefix else "") + ("" if page == "index" else page + ".html")
            accepted_urls = {expected_url, expected_url + "index.html"} if page == "index" else {expected_url}
            if len(canonicals) != 1 or canonicals[0] not in accepted_urls:
                fail(f"{relative(path)}: canonical must identify this published page ({expected_url})")

    def resolve_local(source, value):
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return None
        raw_path = unquote(parsed.path)
        if not raw_path:
            target = source
        elif raw_path.startswith(SITE_PATH):
            target = root / raw_path[len(SITE_PATH):]
        elif raw_path.startswith("/"):
            target = root / raw_path.lstrip("/")
        else:
            target = source.parent / raw_path
        target = target.resolve()
        if target.is_dir():
            target = target / "index.html"
        return target, unquote(parsed.fragment)

    # Validate source references throughout core and current member pages.
    for document in list(expected_documents.values()):
        for node in document.nodes:
            refs = [(attr, node.attrs[attr]) for attr in ("href", "src", "poster") if attr in node.attrs]
            if node.attrs.get("srcset") and not node.attrs["srcset"].lstrip().startswith("data:"):
                refs.extend(("srcset", part.strip().split()[0]) for part in node.attrs["srcset"].split(",") if part.strip())
            for attr, value in refs:
                if not value.strip():
                    fail(f"{relative(document.path)}:{node.line}: empty {attr} on {node.tag}")
                    continue
                if value.lower().startswith("javascript:"):
                    fail(f"{relative(document.path)}:{node.line}: javascript URL should be a semantic button/action")
                    continue
                resolved = resolve_local(document.path, value)
                if resolved is None:
                    continue
                local_reference_count += 1
                target, fragment = resolved
                if not target.is_relative_to(root):
                    fail(f"{relative(document.path)}:{node.line}: local reference escapes site root: {value}")
                    continue
                if not target.is_file():
                    fail(f"{relative(document.path)}:{node.line}: local {attr} target missing: {value}")
                    continue
                if fragment and target.suffix.lower() in (".html", ".htm"):
                    target_doc = get_document(target)
                    if target_doc is not None and fragment not in target_doc.ids:
                        fail(f"{relative(document.path)}:{node.line}: fragment target missing: {value}")
                # ARIA control relations must reference elements in the same page.
            for attr in ("aria-controls", "aria-labelledby", "aria-describedby"):
                for identity in node.attrs.get(attr, "").split():
                    if identity not in document.ids:
                        fail(f"{relative(document.path)}:{node.line}: {attr} references absent id {identity!r}")

    baseline = read_json(baseline_path)
    datasets = {}
    for category in ("publications", "people"):
        path = root / "data" / f"{category}.json"
        data = read_json(path)
        if data is None:
            continue
        try:
            datasets[category] = records_from(data, category)
        except ValueError as exc:
            fail(f"{relative(path)}: {exc}")
            continue
        records = datasets[category]
        identifiers = [str(record.get("id", "")).strip() for record in records]
        if any(not identity for identity in identifiers):
            fail(f"{relative(path)}: every record needs a nonempty id")
        for identity, count in Counter(identifiers).items():
            if identity and count > 1:
                fail(f"{relative(path)}: duplicate record id {identity!r}")
        anchor_prefix = "paper-" if category == "publications" else "person-"
        for prefix in LANGUAGES:
            document = expected_documents.get((prefix, category))
            if document is None:
                continue
            expected = {anchor_prefix + identity for identity in identifiers if identity}
            actual = {identity for identity in document.ids if identity.startswith(anchor_prefix)}
            for missing in sorted(expected - actual):
                fail(f"{relative(document.path)}: record not available in generated HTML: {missing}")
            for extra in sorted(actual - expected):
                fail(f"{relative(document.path)}: displayed record absent from catalog: {extra}")

    preserved_papers = approved_papers = removed_people = 0
    if isinstance(baseline, dict):
        decisions = read_optional_decisions(root / "data/content-decisions.json")
        selection = read_optional_decisions(root / "data/publication-selection.json")
        preserved_papers, approved_papers, removed_people = check_preservation(baseline, datasets, decisions, selection, fail)

    if errors:
        print(f"FAIL: {len(errors)} structural/content issue(s)")
        for error in errors:
            print(f"  - {error}")
        return 1
    paper_count = len(datasets.get("publications", []))
    member_count = len(datasets.get("people", []))
    print(f"PASS: {len(expected_documents)} pages, {local_reference_count} local references, {paper_count} publications ({preserved_papers} preserved + {approved_papers} approved additions), {member_count} current members ({removed_people} approved removals) across three languages.")
    print("Checked: local files/fragments, record anchors, unique IDs, page language, h1/main, button labels, image alt, ARIA references, viewport and canonical URLs.")
    print("Not covered: visual layout, keyboard behavior, external HTTP availability, scientific claim verification, or whether an image depicts an authentic event.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
