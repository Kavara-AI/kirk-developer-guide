#!/usr/bin/env python3
"""Render the public exploration catalogue, or check it for drift. No engine calls."""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "catalogues/phenomena.json"
OUTPUT = ROOT / "docs/phenomena-catalogue.md"
# Keep these aligned with the fixed counts in the guide's orientation pages.
EXPECTED_DOMAINS = 32
EXPECTED_PROMPTS = 256


def validate(catalogue):
    if type(catalogue.get("schema_version")) is not int or catalogue["schema_version"] != 1:
        raise ValueError("Unsupported catalogue schema_version")
    if catalogue.get("claim_status") != "Hypothesis":
        raise ValueError("Exploration prompts must retain their Hypothesis label")
    shapes = catalogue.get("data_shapes")
    domains = catalogue.get("domains")
    if not isinstance(shapes, dict) or not shapes or not isinstance(domains, list) or not domains:
        raise ValueError("Nonempty data_shapes and domains are required")
    seen = set()

    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", value) or value in seen:
            raise ValueError(f"Invalid or duplicate id: {value!r}")
        seen.add(value)

    def text(value):
        if not isinstance(value, str) or not value.strip() or "\n" in value:
            raise ValueError("Expected nonempty, single-line text")

    text(catalogue.get("purpose"))
    for key, shape in shapes.items():
        identifier(key)
        text(shape.get("title"))
        text(shape.get("preparation"))
        questions = shape.get("questions")
        if not isinstance(questions, list) or not questions:
            raise ValueError(f"No preparation questions for {key}")
        for question in questions:
            text(question)
    for domain in domains:
        identifier(domain.get("id"))
        text(domain.get("title"))
        text(domain.get("example_observations"))
        refs = domain.get("data_shapes")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in shapes for ref in refs):
            raise ValueError(f"Invalid data-shape references for {domain['id']}")
        if len(refs) != len(set(refs)):
            raise ValueError(f"Duplicate data-shape references for {domain['id']}")
        phenomena = domain.get("phenomena")
        if not isinstance(phenomena, list) or not phenomena:
            raise ValueError(f"No exploration prompts for {domain['id']}")
        for phenomenon in phenomena:
            identifier(phenomenon.get("id"))
            text(phenomenon.get("description"))
    if len(domains) != EXPECTED_DOMAINS:
        raise ValueError(f"Expected exactly {EXPECTED_DOMAINS} domains; got {len(domains)}")
    count = sum(len(domain["phenomena"]) for domain in domains)
    if count != EXPECTED_PROMPTS:
        raise ValueError(f"Expected exactly {EXPECTED_PROMPTS} exploration prompts; got {count}")


def render(catalogue):
    validate(catalogue)
    domains = catalogue["domains"]
    shapes = catalogue["data_shapes"]
    count = sum(len(domain["phenomena"]) for domain in domains)
    lines = [
        "# What does your data look like?",
        "",
        "<!-- Generated from catalogues/phenomena.json. Edit that source, then run",
        "python3 scripts/render_phenomena_catalogue.py. -->",
        "",
        f"Explore **{count} candidate phenomena across {len(domains)} domains**. Find data that",
        "resembles yours, then follow its preparation questions. You do not need to know",
        "what you will discover or what you will do with it before exploring.",
        "",
        "**Hypothesis — applies to every example below.** These are exploration prompts,",
        "not demonstrated Kirk capabilities or a fixed taxonomy of phenomenon labels.",
        "The categories are navigation aids; choose several or none. Keep room for",
        "unclassified discoveries. Kirk's role is identifying phenomena; interpretation",
        "and action are separate. No example establishes diagnosis, prediction or causality.",
        "",
        "A domain match does not establish model fit. The actual representation must match",
        "the selected model's documented **data envelope** (input contract). This page",
        "does not expand the currently documented API to arbitrary files or data shapes.",
        "Read [capability fit](capability-fit.md) and the",
        "[proposed upload-and-data-fit handoff](tensor-generation.md#proposed-upload-and-data-fit-handoff).",
        "",
        "## Browse by domain",
        "",
    ]
    lines.extend(f"- [{domain['title']}](#{domain['id']})" for domain in domains)
    lines += ["", "## Recognize the structure of your data", "",
              "These profiles describe source data, not supported Kirk inputs or automatic",
              "transformations. Confirm their meaning with the data owner before preprocessing.", ""]
    for key, shape in shapes.items():
        lines += [f'<a id="{key}"></a>', f"### {shape['title']}", ""]
        lines.extend(f"- {question}" for question in shape["questions"])
        lines += ["", f"**Preparation:** {shape['preparation']}", ""]
    lines += ["## Exploration prompts", ""]
    for domain in domains:
        lines += [f'<a id="{domain["id"]}"></a>', f"### {domain['title']}", "",
                  f"**Example observations:** {domain['example_observations']}", "",
                  "**Preparation questions:** " + "; ".join(
                      f"[{shapes[key]['title']}](#{key})" for key in domain["data_shapes"]
                  ) + ".", "", "**Hypotheses to explore:**", ""]
        lines.extend(f"- {item['description']}" for item in domain["phenomena"])
        lines.append("")
    lines += ["## Continue with your data", "",
              "Use the [data-fit handoff](tensor-generation.md#proposed-upload-and-data-fit-handoff)",
              "to record what your observations mean and what remains unknown. Then build",
              "an [evidence-backed phenomena catalogue](phenomena-discovery.md#build-an-evidence-backed-catalogue)",
              "from actual results; this inspiration list is not that result catalogue.", "",
              "The machine-readable source is [catalogues/phenomena.json](../catalogues/phenomena.json).",
              "It supports reuse in a proposed intake/preprocessing suite. It contains no",
              "detectors, learned parameters, automatic fit decisions or upload service.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the generated page is missing or stale")
    args = parser.parse_args()
    try:
        catalogue = json.loads(SOURCE.read_text(encoding="utf-8"))
        rendered = render(catalogue)
        if args.check:
            if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
                parser.exit(1, "Catalogue page is missing or stale; run the renderer.\n")
        else:
            OUTPUT.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        parser.exit(1, f"Catalogue error: {error}\n")
    count = sum(len(domain["phenomena"]) for domain in catalogue["domains"])
    print(f"Catalogue {'checked' if args.check else 'rendered'}: {len(catalogue['domains'])} domains, {count} prompts.")


if __name__ == "__main__":
    main()
