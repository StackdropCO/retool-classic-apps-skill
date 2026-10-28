#!/usr/bin/env python3
"""Add a component to an existing Retool ToolScript app.

Updates both the .rsx file and the positions file atomically: .positions.json for a
single-page app; for a multi-page app the page's .positions/.<screenId>.positions.json
(or .global_positions.json outside every page), where the page is the one the
--after/--before/--parent-frame component lives on, or --screen.
Uses regex-based parsing (RSX is NOT valid XML).
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_app  # noqa: E402


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)

# Default heights by component type
DEFAULT_HEIGHTS = {
    "Text": 0.6,
    "TextInput": 1.0,
    "Select": 1.0,
    "Multiselect": 1.0,
    "DateRange": 1.0,
    "Date": 1.0,
    "Button": 1.0,
    "Switch": 1.0,
    "Checkbox": 1.0,
    "TextArea": 1.0,
    "Table": 13.2,
    "Chat": 17.4,
    "Form": 0.2,
    "Container": 0.2,
    "Divider": 0.2,
}

# Structural components that should NOT get marginType="normal"
STRUCTURAL_TYPES = {
    "Frame", "Form", "Container", "Header", "Body", "Footer", "View",
}


def parse_attrs(attrs_str):
    """Parse RSX attribute string into list of (key, raw_value) tuples.

    Handles:
      label=""              -> ("label", '""')
      placeholder="Search"  -> ("placeholder", '"Search..."')
      showClear={true}      -> ("showClear", '{true}')
      iconBefore="bold/x"   -> ("iconBefore", '"bold/x"')
    """
    if not attrs_str or not attrs_str.strip():
        return []

    attrs = []
    s = attrs_str.strip()
    i = 0
    while i < len(s):
        # skip whitespace
        while i < len(s) and s[i] in (" ", "\t", "\n"):
            i += 1
        if i >= len(s):
            break

        # read key
        key_start = i
        while i < len(s) and s[i] not in ("=", " ", "\t"):
            i += 1
        key = s[key_start:i]
        if not key:
            break

        # skip '='
        if i < len(s) and s[i] == "=":
            i += 1
        else:
            # boolean shorthand: just the key name means {true}
            attrs.append((key, "{true}"))
            continue

        # read value
        if i >= len(s):
            break

        if s[i] == '"':
            # quoted string value
            j = i + 1
            while j < len(s) and s[j] != '"':
                if s[j] == "\\":
                    j += 1
                j += 1
            val = s[i : j + 1]
            i = j + 1
        elif s[i] == "{":
            # JSX expression - find matching closing brace
            depth = 0
            j = i
            while j < len(s):
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                elif s[j] == '"':
                    j += 1
                    while j < len(s) and s[j] != '"':
                        if s[j] == "\\":
                            j += 1
                        j += 1
                elif s[j] == "'":
                    j += 1
                    while j < len(s) and s[j] != "'":
                        if s[j] == "\\":
                            j += 1
                        j += 1
                j += 1
            val = s[i : j + 1]
            i = j + 1
        else:
            # unquoted value (shouldn't normally happen in RSX)
            j = i
            while j < len(s) and s[j] not in (" ", "\t"):
                j += 1
            val = s[i:j]
            i = j

        attrs.append((key, val))

    return attrs


def build_component_xml(comp_type, comp_id, attrs, children, indent="    "):
    """Build RSX component string."""
    lines = []
    lines.append(f"{indent}<{comp_type}")
    lines.append(f'{indent}  id="{comp_id}"')

    # Add parsed attributes in alphabetical order
    parsed = parse_attrs(attrs) if attrs else []
    # Check if marginType is already specified
    has_margin = any(k == "marginType" for k, _ in parsed)
    # Add marginType if not structural and not already specified
    if not has_margin and comp_type not in STRUCTURAL_TYPES:
        parsed.append(("marginType", '"normal"'))
    # Sort attributes alphabetically (id already placed first)
    parsed.sort(key=lambda x: x[0])
    for key, val in parsed:
        lines.append(f"{indent}  {key}={val}")

    if children:
        lines.append(f"{indent}>")
        # indent children
        for child_line in children.strip().split("\n"):
            lines.append(f"{indent}  {child_line}")
        lines.append(f"{indent}</{comp_type}>")
    else:
        lines.append(f"{indent}/>")

    return "\n".join(lines)


def find_component_end(rsx_content, component_id):
    """Find the end position of a component block by its id.

    Returns the index right after the component's closing tag or self-closing />.
    """
    # Find the opening tag that contains id="component_id"
    # Pattern: <TagName ... id="component_id" ... /> or <TagName ... id="component_id" ...>...</TagName>
    id_pattern = re.compile(
        r'<(\w+)\s[^>]*?id="' + re.escape(component_id) + r'"',
        re.DOTALL,
    )
    match = id_pattern.search(rsx_content)
    if not match:
        return None, None

    tag_name = match.group(1)
    start_pos = match.start()

    # Now find if this is self-closing or has children
    # Scan forward from match to find either /> or >
    pos = match.end()
    while pos < len(rsx_content):
        if rsx_content[pos : pos + 2] == "/>":
            return start_pos, pos + 2
        elif rsx_content[pos] == ">":
            # Has children - find matching closing tag
            # Need to handle nested tags of same name
            depth = 1
            pos += 1
            open_pat = re.compile(r"<" + re.escape(tag_name) + r"[\s/>]")
            close_pat = re.compile(r"</" + re.escape(tag_name) + r"\s*>")
            while pos < len(rsx_content) and depth > 0:
                next_open = open_pat.search(rsx_content, pos)
                next_close = close_pat.search(rsx_content, pos)
                if next_close is None:
                    break
                if next_open and next_open.start() < next_close.start():
                    # Check if it's self-closing
                    tag_end = rsx_content.find(">", next_open.end())
                    if tag_end >= 0 and rsx_content[tag_end - 1] == "/":
                        # Self-closing, don't change depth
                        pos = tag_end + 1
                    else:
                        depth += 1
                        pos = next_open.end()
                else:
                    depth -= 1
                    if depth == 0:
                        return start_pos, next_close.end()
                    pos = next_close.end()
            return start_pos, pos
        pos += 1

    return start_pos, None


def find_component_before(rsx_content, component_id):
    """Find the start position of a component block by its id."""
    id_pattern = re.compile(
        r'<(\w+)\s[^>]*?id="' + re.escape(component_id) + r'"',
        re.DOTALL,
    )
    match = id_pattern.search(rsx_content)
    if not match:
        return None
    return match.start()


def main():
    parser = argparse.ArgumentParser(
        description="Add a component to a Retool ToolScript app"
    )
    parser.add_argument("app_dir", help="Path to app directory")
    parser.add_argument("--type", required=True, help="Component tag name")
    parser.add_argument("--id", required=True, help="Component ID")
    parser.add_argument(
        "--parent-frame",
        default=None,
        help="Parent frame/container ID (default: $main, or the --screen page's main frame)",
    )
    parser.add_argument(
        "--screen",
        help="Multi-page apps: the page (Screen id) to add to. Default: the page the "
        "--after/--before/--parent-frame component lives on",
    )
    parser.add_argument("--after", help="ID of sibling to insert after")
    parser.add_argument("--before", help="ID of sibling to insert before")
    parser.add_argument("--attrs", default="", help="RSX attributes string")
    parser.add_argument(
        "--width", type=int, default=12, help="Column width (1-12)"
    )
    parser.add_argument(
        "--height", type=float, default=None, help="Row height"
    )
    parser.add_argument("--col", type=int, default=None, help="Column offset")
    parser.add_argument(
        "--same-row",
        action="store_true",
        help="Place on same row as --after component",
    )
    parser.add_argument(
        "--container", help="Container ID for position entry"
    )
    parser.add_argument(
        "--subcontainer", help="Subcontainer ID for position entry"
    )
    parser.add_argument(
        "--row-group",
        choices=["header", "footer"],
        help="Row group for form header/footer",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Which .rsx file to modify (default: main.rsx; multi-page apps: the file "
        "the anchor component is in)",
    )
    parser.add_argument("--children", default="", help="Inline RSX children")

    args = parser.parse_args()

    app_dir = os.path.abspath(args.app_dir)
    multipage = validate_app.is_multipage(app_dir)
    if args.screen and not multipage:
        fail("--screen needs a multi-page app (this one is single-page)")

    if multipage:
        # Layout lives per page: find the page (and file) the anchor sits on.
        records = validate_app.walk_app(app_dir)
        if args.parent_frame is None and args.screen:
            args.parent_frame = next(
                (r["id"] for r in records
                 if r["tag"] == "Frame" and r["screen"] == args.screen
                 and validate_app.get_attr_value(r["attrs"], "type") == "main"),
                None,
            )
            if args.parent_frame is None:
                fail(f"no page '{args.screen}' with a type=\"main\" Frame")
        args.parent_frame = args.parent_frame or "$main"
        anchor = args.after or args.before or args.parent_frame
        rec = next((r for r in records if r["id"] == anchor), None)
        if rec is None:
            fail(f"component '{anchor}' not found in any file reachable from main.rsx")
        if args.screen and rec["screen"] != args.screen:
            fail(f"'{anchor}' is on {rec['screen'] or 'the global scope'}, not page '{args.screen}'")
        rsx_path = rec["file"]
        positions_path = validate_app.page_positions_path(app_dir, rec["screen"])
    else:
        args.parent_frame = args.parent_frame or "$main"
        positions_path = os.path.join(app_dir, ".positions.json")
        if not os.path.isfile(positions_path):
            fail(f"Positions file not found: {positions_path}")

    if args.file or not multipage:
        rsx_path = os.path.join(app_dir, args.file or "main.rsx")
        if not os.path.isfile(rsx_path):
            # Check in src/ subdirectory
            rsx_path_alt = os.path.join(app_dir, "src", args.file or "main.rsx")
            if os.path.isfile(rsx_path_alt):
                rsx_path = rsx_path_alt
            else:
                fail(f"RSX file not found: {rsx_path}")

    # Read files (an empty page has no positions file yet)
    with open(rsx_path, "r") as f:
        rsx_content = f.read()
    positions = {}
    if os.path.isfile(positions_path):
        with open(positions_path, "r") as f:
            positions = json.load(f)

    # Determine height
    comp_height = args.height
    if comp_height is None:
        comp_height = DEFAULT_HEIGHTS.get(args.type, 1.0)

    # Build component XML
    component_xml = build_component_xml(
        args.type, args.id, args.attrs, args.children
    )

    # Insert into RSX
    if args.after:
        _, end_pos = find_component_end(rsx_content, args.after)
        if end_pos is None:
            print(
                f'Error: Could not find component with id="{args.after}" in {rsx_path}',
                file=sys.stderr,
            )
            sys.exit(1)
        # Insert after the component, preserving newline
        rsx_content = (
            rsx_content[:end_pos] + "\n" + component_xml + rsx_content[end_pos:]
        )
    elif args.before:
        start_pos = find_component_before(rsx_content, args.before)
        if start_pos is None:
            print(
                f'Error: Could not find component with id="{args.before}" in {rsx_path}',
                file=sys.stderr,
            )
            sys.exit(1)
        # Insert before the component
        rsx_content = (
            rsx_content[:start_pos] + component_xml + "\n" + rsx_content[start_pos:]
        )
    else:
        # Insert before the closing tag of the parent frame
        parent_id = args.parent_frame
        # Find closing tag of parent
        _, parent_end = find_component_end(rsx_content, parent_id)
        if parent_end is None:
            # Try finding </Frame> as fallback
            close_match = re.search(r"</Frame>", rsx_content)
            if close_match:
                insert_pos = close_match.start()
            else:
                print(
                    f"Error: Could not find parent frame '{parent_id}'",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            # Find the closing tag within the parent
            close_tag = f"</Frame>"
            # We need to insert before the closing tag of the frame
            # Find </Frame> that ends at parent_end
            close_match = rsx_content.rfind(close_tag, 0, parent_end)
            if close_match >= 0:
                # Start of the </Frame> line, so the closing tag keeps its indent
                line_start = rsx_content.rfind("\n", 0, close_match) + 1
                indent_only = not rsx_content[line_start:close_match].strip()
                insert_pos = line_start if indent_only else close_match
            else:
                insert_pos = parent_end
        rsx_content = (
            rsx_content[:insert_pos]
            + component_xml
            + "\n"
            + rsx_content[insert_pos:]
        )

    # Calculate position entry
    pos_entry = {}

    if args.container:
        pos_entry["container"] = args.container
    if args.subcontainer:
        pos_entry["subcontainer"] = args.subcontainer
    if args.row_group:
        pos_entry["rowGroup"] = args.row_group

    # Calculate row position
    if args.after and args.after in positions:
        after_pos = positions[args.after]
        if args.same_row:
            # Same row as --after
            after_row = after_pos.get("row", 0)
            pos_entry["row"] = after_row
        else:
            after_row = after_pos.get("row", 0)
            after_height = after_pos.get("height", 1.0)
            pos_entry["row"] = after_row + after_height
    elif args.before and args.before in positions:
        before_pos = positions[args.before]
        before_row = before_pos.get("row", 0)
        # Place at the same row as --before (before component will shift down)
        pos_entry["row"] = before_row
    # If no after/before, row defaults to 0 (omitted from JSON for row=0 in
    # some examples, but we include it for clarity)

    if args.col is not None and args.col > 0:
        pos_entry["col"] = args.col

    pos_entry["height"] = comp_height
    pos_entry["width"] = args.width

    # Add to positions
    positions[args.id] = pos_entry

    # Write files atomically (write to temp then rename)
    # Write RSX
    tmp_rsx = rsx_path + ".tmp"
    with open(tmp_rsx, "w") as f:
        f.write(rsx_content)
    os.replace(tmp_rsx, rsx_path)

    # Write positions
    os.makedirs(os.path.dirname(positions_path), exist_ok=True)
    tmp_pos = positions_path + ".tmp"
    with open(tmp_pos, "w") as f:
        json.dump(positions, f, indent=2)
        f.write("\n")
    os.replace(tmp_pos, positions_path)

    print(f"Added <{args.type} id=\"{args.id}\" /> to {rsx_path}")
    print(f"Updated {positions_path}")


if __name__ == "__main__":
    main()
