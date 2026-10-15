"""Immutable example copies and structured table storage, independent of rendering."""

import base64
import copy
import hashlib
import json

import pytest

from oppencouncil.assets import freeze_images, read_asset, validate_image, validate_tables
from oppencouncil.project import MARKER, metadata_block
from oppencouncil.store import FreezeError, FreezeStore

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8S8AAAAASUVORK5CYII="
)
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
    b'<rect width="10" height="10" fill="blue"/></svg>'
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "project.md").write_text(
        MARKER + "\n" + metadata_block({"governance_version": 5, "project_type": "research"}) + "\n"
    )
    (tmp_path / "Explore").mkdir()
    (tmp_path / "Freeze").mkdir()
    (tmp_path / "Explore/sample.png").write_bytes(PNG)
    (tmp_path / "Explore/sample.svg").write_bytes(SVG)
    return tmp_path


def table():
    return {
        "schema_version": 1,
        "id": "baseline",
        "title": "Synthetic example",
        "simulated": True,
        "columns": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "headers": [
            {
                "id": "arms",
                "label": "Treatment",
                "children": [
                    {"id": "ha", "label": "A", "column_id": "a"},
                    {"id": "hb", "label": "B", "column_id": "b"},
                ],
            }
        ],
        "rows": [
            {"id": "age", "label": "Age", "cells": {}},
            {"id": "mean", "parent_id": "age", "label": "Mean", "cells": {"a": "62", "b": "63"}},
        ],
        "footnotes": [
            {"id": "note", "text": "Simulated values", "refs": [{"row_id": "mean", "column_id": "a"}]}
        ],
    }


def block(value):
    return "Before\n\n```table\n" + json.dumps(value) + "\n```\n\nAfter"


def test_saved_image_is_a_content_addressed_copy_surviving_rebuild_and_archive(project):
    name = hashlib.sha256(PNG).hexdigest() + ".png"
    saved = freeze_images(project, "![模拟数据](Explore/sample.png)")
    assert saved == f"![模拟数据](Freeze/assets/{name})"
    assert read_asset(project, name) == (PNG, "image/png")
    (project / "Explore/sample.png").write_bytes(b"New experiment output")
    (project / "Explore").rename(project / "Explore-archived")
    assert freeze_images(project, saved) == saved
    assert read_asset(project, name)[0] == PNG


def test_copy_is_deduplicated_and_changed_saved_bytes_are_rejected(project):
    text = freeze_images(project, "![模拟数据](Explore/sample.svg)")
    name = hashlib.sha256(SVG).hexdigest() + ".svg"
    path = project / "Freeze/assets" / name
    before = path.stat().st_mtime_ns
    assert freeze_images(project, text) == text
    assert path.stat().st_mtime_ns == before
    path.write_bytes(SVG.replace(b"blue", b"red"))
    with pytest.raises(FreezeError, match="changed"):
        read_asset(project, name)


@pytest.mark.parametrize(
    "target",
    [
        "Data/private.png",
        "Explore/../project.md",
        "/etc/passwd",
        "https://example.org/image.png",
        "Explore\\sample.png",
    ],
)
def test_candidate_images_cannot_read_other_areas(project, target):
    with pytest.raises(FreezeError):
        freeze_images(project, f"![example]({target})")


def test_linked_source_and_linked_asset_directory_are_rejected(project):
    try:
        (project / "Explore/link.png").symlink_to(project / "Explore/sample.png")
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(FreezeError, match="symlink"):
        freeze_images(project, "![example](Explore/link.png)")
    (project / "Freeze/assets").symlink_to(project / "Explore", target_is_directory=True)
    with pytest.raises(FreezeError, match="linked"):
        freeze_images(project, "![example](Explore/sample.png)")


@pytest.mark.parametrize(
    "inner",
    [
        "<script>alert(1)</script>",
        '<image href="https://example.org/leak"/>',
        '<use href="file:///etc/passwd"/>',
        '<rect onload="alert(1)"/>',
        '<rect fill="url(https://example.org/leak)"/>',
        "<foreignObject><p>HTML</p></foreignObject>",
    ],
)
def test_svg_executable_or_external_resources_are_rejected(inner):
    with pytest.raises(FreezeError):
        validate_image(('<svg xmlns="http://www.w3.org/2000/svg">' + inner + "</svg>").encode(), ".svg")


def test_svg_local_references_and_literal_markdown_code_are_allowed(project):
    validate_image(
        b'<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="p" d="M0 0"/></defs><use href="#p"/></svg>',
        ".svg",
    )
    text = "```markdown\n![literal](Data/private.png)\n```\n"
    assert freeze_images(project, text) == text


def test_multilevel_table_and_row_groups_survive_candidate_save(project):
    value = table()
    value["columns"][0].update(unit="years", format="mean (SD)", align="right")
    definition = block(value)
    validate_tables(definition)
    store = FreezeStore(project)
    qid = store.add_questions(
        [{"title": "Output specification", "why": "Formal table"}], request_id="create"
    )["ids"][0]
    saved = store.change(
        qid, "definition_draft", definition, expected_revision=1, request_id="table", actor="user"
    )
    assert saved["definition"]["draft"]["text"] == definition
    assert saved["definition"]["current_version"] is None
    assert saved["human_pending"]
    assert saved["definition"]["draft"]["edits"][-1]["by"] == "user"


@pytest.mark.parametrize(
    "case", ["columns", "headers", "parent", "cell", "footnote", "unit", "format", "align", "simulation"]
)
def test_inconsistent_structured_tables_are_rejected(case):
    value = copy.deepcopy(table())
    if case == "columns":
        value["columns"][1]["id"] = "a"
    elif case == "headers":
        value["headers"][0]["children"].reverse()
    elif case == "parent":
        value["rows"][0]["parent_id"] = "mean"
    elif case == "cell":
        value["rows"][1]["cells"]["missing"] = "42"
    elif case == "footnote":
        value["footnotes"][0]["refs"][0]["row_id"] = "missing"
    elif case in ("unit", "format"):
        value["columns"][0][case] = 2
    elif case == "align":
        value["columns"][0]["align"] = "right;background:red"
    else:
        value.pop("simulated")
    with pytest.raises(FreezeError):
        validate_tables(block(value))


@pytest.mark.parametrize("refs", [["mean"], "mean", [None], [{}], [{"row_id": None}], [{"other": "mean"}]])
def test_footnote_reference_shape_has_actionable_error(refs):
    value = table()
    value["footnotes"][0]["refs"] = refs
    with pytest.raises(FreezeError, match="row_id/column_id objects"):
        validate_tables(block(value))


def test_plotting_library_svg_metadata_styles_and_standard_declaration_are_static():
    svg = b"""<?xml version="1.0" encoding="utf-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<metadata><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:cc="http://creativecommons.org/ns#">
<cc:Work><dc:type rdf:resource="http://purl.org/dc/dcmitype/StillImage"/>
<dc:creator><cc:Agent><dc:title>Matplotlib</dc:title></cc:Agent></dc:creator></cc:Work>
</rdf:RDF></metadata>
<style type="text/css"><![CDATA[*{stroke-linejoin: round; stroke-linecap: butt}]]></style>
<defs><path id="sample" d="M 0 0 L 10 10"/></defs>
<use xlink:href="#sample" style="fill: #ffffff; stroke-width: 1.5; font: 10px 'DejaVu Sans'"/>
</svg>"""
    validate_image(svg, ".svg")


@pytest.mark.parametrize(
    "inner",
    [
        "<style>path {fill: url(https://example.org/secret)}</style>",
        '<style>@import "https://example.org/secret";</style>',
        '<path style="fill: u/**/rl(https://example.org/secret)"/>',
        '<path style="fill: u\\72l(https://example.org/secret)"/>',
        "<metadata><script>alert(1)</script></metadata>",
    ],
)
def test_svg_styles_and_metadata_do_not_reintroduce_executable_content(inner):
    with pytest.raises(FreezeError):
        validate_image(('<svg xmlns="http://www.w3.org/2000/svg">' + inner + "</svg>").encode(), ".svg")


def test_svg_custom_entity_and_stylesheet_processing_instruction_are_rejected():
    for value in [
        '<!DOCTYPE svg [<!ENTITY x "text">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
        '<?xml-stylesheet href="https://example.org/secret"?><svg xmlns="http://www.w3.org/2000/svg"/>',
    ]:
        with pytest.raises(FreezeError):
            validate_image(value.encode(), ".svg")


def test_table_fences_respect_outer_examples_and_reject_incomplete_json():
    validate_tables("````markdown\n```table\nnot JSON\n```\n````\n")
    validate_tables("~~~table\n" + json.dumps(table()) + "\n~~~")
    for value in [
        "```table\n" + json.dumps(table()),
        "```table extra\n{}\n```",
        '```table\n{"schema_version": 1, "schema_version": 2}\n```',
    ]:
        with pytest.raises(FreezeError):
            validate_tables(value)


def test_image_literals_in_tilde_and_nested_fences_are_never_copied(project):
    text = "~~~~markdown\n```\n![literal](Data/private.png)\n```\n~~~~\n"
    assert freeze_images(project, text) == text
