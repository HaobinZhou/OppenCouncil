"""Definition table blocks and immutable local example images (OPP-22/23)."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from .store import FreezeError, atomic_write, ordinary_file

ASSET_NAME = re.compile(r"[0-9a-f]{64}\.(png|svg)\Z")
IMAGE = re.compile(r"!\[([^\]\n]*)\]\((?:<([^>\n]+)>|([^\s)]+))\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)\r?$")
MAX_IMAGE = 10 * 1024 * 1024
SVG_TAGS = {
    "svg",
    "g",
    "defs",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "title",
    "desc",
    "clipPath",
    "linearGradient",
    "radialGradient",
    "stop",
    "pattern",
    "marker",
    "symbol",
    "use",
    "style",
    "metadata",
}
SVG_NS = "http://www.w3.org/2000/svg"
METADATA_NS = {
    SVG_NS,
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://purl.org/dc/elements/1.1/",
    "http://creativecommons.org/ns#",
}
METADATA_TAGS = {
    "metadata",
    "RDF",
    "Description",
    "Bag",
    "Seq",
    "li",
    "format",
    "type",
    "title",
    "date",
    "creator",
    "description",
    "source",
    "identifier",
    "subject",
    "publisher",
    "language",
    "rights",
    "Work",
    "Agent",
    "license",
    "permits",
    "requires",
    "prohibits",
}
CSS_PROPERTIES = {
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-opacity",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "stroke-dasharray",
    "stroke-dashoffset",
    "opacity",
    "color",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "font-stretch",
    "font-variant",
    "text-anchor",
    "text-decoration",
    "letter-spacing",
    "word-spacing",
    "dominant-baseline",
    "alignment-baseline",
    "clip-path",
    "clip-rule",
    "display",
    "visibility",
    "white-space",
    "vector-effect",
    "paint-order",
    "shape-rendering",
    "text-rendering",
}


def static_css(value, *, sheet=False):
    value = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
    if re.search(r"[\\@<>]|expression\s*\(", value, re.I):
        raise FreezeError("SVG contains non-static CSS")
    if sheet:
        rules = list(re.finditer(r"([^{}]+)\{([^{}]*)\}", value))
        if re.sub(r"[^{}]+\{[^{}]*\}", "", value).strip():
            raise FreezeError("SVG contains unsupported CSS rules")
        for rule in rules:
            # Ordinary element, class, ID and descendant selectors suffice for plots.
            if not re.fullmatch(r"[\w.#*,\s:>+\-]+", rule[1]):
                raise FreezeError("SVG contains unsupported CSS selectors")
            static_css(rule[2])
        return
    for declaration in value.split(";"):
        if not declaration.strip():
            continue
        key, sep, content = declaration.partition(":")
        if not sep or key.strip().lower() not in CSS_PROPERTIES or not content.strip():
            raise FreezeError("SVG contains unsupported CSS properties")
        # References can only address another element in this immutable image.
        content = re.sub(r"url\(\s*(['\"]?)#[A-Za-z_][\w.-]*\1\s*\)", "", content, flags=re.I)
        if "url" in content.lower():
            raise FreezeError("SVG cannot request external resources")


def svg_element(node, *, metadata=False):
    namespace, _, tag = node.tag.removeprefix("{").rpartition("}")
    tag = tag or node.tag
    if metadata:
        if namespace not in METADATA_NS or tag not in METADATA_TAGS:
            raise FreezeError("SVG contains unsupported metadata")
    elif namespace not in {"", SVG_NS} or tag not in SVG_TAGS:
        raise FreezeError("SVG contains executable or unsupported content")
    for name, value in node.attrib.items():
        key, content = name.split("}")[-1].lower(), value.strip()
        if key.startswith("on") or key == "base":
            raise FreezeError("SVG event handlers are not allowed")
        if key == "style":
            static_css(content)
        elif key in {"href", "src"} and not re.fullmatch(r"#[A-Za-z_][\w.-]*", content):
            raise FreezeError("SVG cannot request external resources")
        elif (
            "url" in content.lower()
            and not metadata
            and not re.fullmatch(r"url\(#[A-Za-z_][\w.-]*\)", content)
        ):
            raise FreezeError("SVG cannot request external resources")
    if tag == "style":
        if len(node):
            raise FreezeError("SVG CSS must be text")
        static_css(node.text or "", sheet=True)
    for child in node:
        svg_element(child, metadata=metadata or tag == "metadata")


def validate_image(raw, suffix):
    if suffix == ".png":
        if len(raw) < 24 or raw[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
            raise FreezeError("Invalid PNG image")
        width, height = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        if not width or not height or width * height > 100_000_000:
            raise FreezeError("PNG dimensions exceed supported example size")
        return
    if suffix != ".svg":
        raise FreezeError("Only static PNG/SVG examples are supported")
    # Common plotting libraries emit this external declaration. ElementTree does
    # not load it; permit this exact standard declaration, never an internal DTD.
    parsed = re.sub(
        rb'<!DOCTYPE svg\s+PUBLIC\s+[\'"]-//W3C//DTD SVG 1\.1//EN[\'"]\s+'
        rb'[\'"]https?://www\.w3\.org/Graphics/SVG/1\.1/DTD/svg11\.dtd[\'"]\s*>',
        b"",
        raw,
    )
    parsed = re.sub(rb"<!--.*?-->", b"", parsed, flags=re.S)
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", parsed, re.I):
        raise FreezeError("SVG custom DTDs and entities are not allowed")
    declaration = (
        rb"^\s*<\?xml\s+version=['\"]1\.0['\"](?:\s+encoding=['\"]UTF-8['\"])?"
        rb"(?:\s+standalone=['\"](?:yes|no)['\"])?\s*\?>"
    )
    if b"<?" in re.sub(declaration, b"", parsed, flags=re.I):
        raise FreezeError("SVG processing instructions are not allowed")
    try:
        root = ET.fromstring(parsed)
    except ET.ParseError as error:
        raise FreezeError("Invalid SVG image") from error
    if root.tag.split("}")[-1] != "svg":
        raise FreezeError("Expected an SVG root")
    svg_element(root)


def safe_path(project, relative, allowed_root):
    parts = PurePosixPath(relative).parts
    if not parts or parts[0] != allowed_root or any(p in {"..", "."} for p in parts) or "\\" in relative:
        raise FreezeError("Image path is outside the allowed project area")
    root = Path(project).resolve(strict=True)
    current = root
    for part in parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as error:
            raise FreezeError("Example image is missing") from error
        if stat.S_ISLNK(info.st_mode):
            raise FreezeError("Image symlinks are not allowed")
    if not current.is_file() or not current.resolve().is_relative_to(root / allowed_root):
        raise FreezeError("Example must be an ordinary file inside its project area")
    return current


def read_asset(project, name):
    if not ASSET_NAME.fullmatch(name):
        raise FreezeError("Invalid immutable asset name")
    path = safe_path(project, "Freeze/assets/" + name, "Freeze")
    raw = ordinary_file(path, MAX_IMAGE)
    if raw is None or hashlib.sha256(raw).hexdigest() != name.split(".")[0]:
        raise FreezeError("Example asset is missing or changed")
    validate_image(raw, path.suffix)
    return raw, "image/png" if path.suffix == ".png" else "image/svg+xml"


def freeze_images(project, text):
    """Copy examples before publishing references; an interrupted save may leave an unused immutable asset."""
    if not isinstance(text, str):
        raise FreezeError("Definition text must be a string")
    root = Path(project)

    def replace(match):
        target = match[2] or match[3]
        if target.startswith("Freeze/assets/"):
            read_asset(root, target.removeprefix("Freeze/assets/"))
            return match[0]
        source = safe_path(root, target, "Explore")
        raw = ordinary_file(source, MAX_IMAGE)
        if raw is None:
            raise FreezeError("Example image is missing")
        suffix = source.suffix.lower()
        validate_image(raw, suffix)
        name = hashlib.sha256(raw).hexdigest() + suffix
        directory = root / "Freeze" / "assets"
        if directory.is_symlink():
            raise FreezeError("Assets directory must not be linked")
        directory.mkdir(exist_ok=True)
        destination = directory / name
        prior = ordinary_file(destination, MAX_IMAGE)
        if prior is not None and prior != raw:
            raise FreezeError("Immutable asset collision")
        if prior is None:
            atomic_write(destination, raw)
        return f"![{match[1]}](Freeze/assets/{name})"

    # Markdown code examples are literal text, never image requests.
    pieces, fence = [], None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip("\r\n"))
        if fence is None and match:
            fence = match[1]
            pieces.append(line)
        elif fence is not None:
            pieces.append(line)
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
        else:
            pieces.append(IMAGE.sub(replace, line))
    return "".join(pieces)


def validate_table(table):
    if not isinstance(table, dict) or table.get("schema_version") != 1:
        raise FreezeError("Unsupported table schema")
    for field in ("id", "title"):
        if not isinstance(table.get(field), str) or not table[field].strip():
            raise FreezeError(f"Table requires {field}")
    if type(table.get("simulated")) is not bool:
        raise FreezeError("Table must explicitly label simulated data")
    columns, rows = table.get("columns"), table.get("rows")
    if not isinstance(columns, list) or not columns or not isinstance(rows, list) or not rows:
        raise FreezeError("Table requires columns and rows")
    try:
        column_ids, row_ids = [c["id"] for c in columns], [r["id"] for r in rows]
        if any(not isinstance(i, str) or not i for i in column_ids + row_ids):
            raise ValueError("invalid IDs")
        if len(set(column_ids)) != len(column_ids) or len(set(row_ids)) != len(row_ids):
            raise ValueError("duplicate IDs")
        for column in columns:
            if any(key in column and not isinstance(column[key], str) for key in ("label", "format", "unit")):
                raise ValueError("column label, format and unit must be text")
            if "align" in column and column["align"] not in ("left", "center", "right"):
                raise ValueError("invalid column alignment")
        leaves, header_ids = [], set()

        def header(nodes, depth=0):
            if depth > 8 or not isinstance(nodes, list):
                raise ValueError("invalid header tree")
            for node in nodes:
                if node["id"] in header_ids or not isinstance(node.get("label"), str):
                    raise ValueError("duplicate header ID or missing label")
                header_ids.add(node["id"])
                if "children" in node:
                    if not node["children"] or "column_id" in node:
                        raise ValueError("ambiguous header")
                    header(node["children"], depth + 1)
                else:
                    leaves.append(node["column_id"])

        header(table["headers"])
        if leaves != column_ids:
            raise ValueError("header leaves must match column order")
        seen = set()
        for row in rows:
            if row.get("parent_id") is not None and row["parent_id"] not in seen:
                raise ValueError("parent rows must precede their children")
            if not isinstance(row.get("label"), str) or not isinstance(row.get("cells"), dict):
                raise ValueError("row labels and cells are required")
            if not set(row["cells"]) <= set(column_ids) or any(
                not isinstance(v, str) for v in row["cells"].values()
            ):
                raise ValueError("invalid table cells")
            seen.add(row["id"])
        notes = table.get("footnotes", [])
        if len({n["id"] for n in notes}) != len(notes):
            raise ValueError("duplicate footnote")
        for note in notes:
            if not isinstance(note.get("text"), str):
                raise ValueError("footnote text required")
            refs = note.get("refs", [])
            if not isinstance(refs, list):
                raise ValueError("footnote refs must be an array of row_id/column_id objects")
            for ref in refs:
                if (
                    not isinstance(ref, dict)
                    or not ref
                    or set(ref) - {"row_id", "column_id"}
                    or any(not isinstance(value, str) or not value for value in ref.values())
                ):
                    raise ValueError("footnote refs must contain row_id/column_id objects")
                if ref.get("row_id") is not None and ref["row_id"] not in row_ids:
                    raise ValueError("unknown footnote row")
                if ref.get("column_id") is not None and ref["column_id"] not in column_ids:
                    raise ValueError("unknown footnote column")
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as error:
        raise FreezeError(f"Invalid table block: {error}") from error


def validate_tables(text):
    if not isinstance(text, str):
        raise FreezeError("Definition text must be a string")
    for block in table_blocks(text):
        try:
            from .project import unique_object

            table = json.loads(block, object_pairs_hook=unique_object)
        except (ValueError, RecursionError) as error:
            raise FreezeError("Invalid JSON in table block") from error
        validate_table(table)


def table_blocks(text):
    """Respect outer Markdown fences and reject a malformed/unclosed table fence."""
    fence, kind, body = None, None, []
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None:
            if match:
                fence, kind, body = match[1], match[2].strip(), []
                if kind.startswith("table "):
                    raise FreezeError("A table fence takes no extra arguments")
        elif match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
            if kind == "table":
                yield "\n".join(body)
            fence, kind = None, None
        else:
            body.append(line)
    if kind == "table":
        raise FreezeError("Unclosed table block")
