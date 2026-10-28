#!/usr/bin/env python3
"""Add a page (<Screen>) to a multi-page Retool ToolScript app.

Usage:
    python add_page.py <app-dir> --id settings [--title "Settings"] [--url-slug settings]

Writes src/<id>.rsx (a Screen with its own main Frame and a title Text), its positions
file .positions/.<id>.positions.json, and the <Include> in main.rsx. The Screen and
Frame attributes copy Retool's own multi-page exports: the frame id is the next free
$main / $main2 / ..., because frame ids are unique across the whole app.
"""

import argparse
import itertools
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_app  # noqa: E402


def screen_xml(screen_id, title, order, url_slug, body):
    """A <Screen> element in Retool's export attribute order. `body` is its children,
    already indented by two spaces. An empty urlSlug is what Retool exports for the
    first page of a new app."""
    title = title.replace('"', "'")  # a raw " ends the attribute (silent import killer)
    return (
        '<Screen\n'
        f'  id="{screen_id}"\n'
        '  _customShortcuts={[]}\n'
        '  _hashParams={[]}\n'
        f'  _order={{{order}}}\n'
        '  _searchParams={[]}\n'
        f'  browserTitle="{title}"\n'
        f'  title="{title}"\n'
        f'  urlSlug="{url_slug}"\n'
        f'  uuid="{uuid.uuid4()}"\n'
        '>\n'
        f'{body.rstrip()}\n'
        '</Screen>\n'
    )


def fail(message):
    print(f'Error: {message}', file=sys.stderr)
    sys.exit(1)


def add_page(app_dir, page_id, title=None, url_slug=None):
    app_dir = os.path.abspath(app_dir)
    title = (title or page_id).replace('"', "'")
    url_slug = page_id if url_slug is None else url_slug
    if not validate_app.is_multipage(app_dir):
        fail('single-page app (no appTemplate.rootScreen, no <Screen>): pages need the '
             'multi-page layout. scaffold_app.py creates it by default.')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', page_id):
        fail(f"page id '{page_id}' must be a letter or _ followed by letters, digits or _")

    records = validate_app.walk_app(app_dir)
    ids = {r['id'] for r in records if r['id']}
    title_id = f'{page_id}Title'
    for taken in (page_id, title_id):
        if taken in ids:
            fail(f"id '{taken}' is already used in this app")
    screens = [r for r in records if r['tag'] == 'Screen']
    slugs = {validate_app.get_attr_value(s['attrs'], 'urlSlug') for s in screens}
    if url_slug and url_slug in slugs:
        fail(f"urlSlug '{url_slug}' is already used by another page")

    rsx_path = os.path.join(app_dir, 'src', f'{page_id}.rsx')
    positions_path = validate_app.page_positions_path(app_dir, page_id)
    for path in (rsx_path, positions_path):
        if os.path.exists(path):
            fail(f'{path} already exists')

    orders = [validate_app.get_attr_value(s['attrs'], '_order') for s in screens]
    order = max((int(o) for o in orders if o and o.lstrip('-').isdigit()), default=-1) + 1
    frame_id = next(f for f in itertools.chain(['$main'], (f'$main{n}' for n in itertools.count(2)))
                    if f not in ids)

    body = (
        '  <Frame\n'
        f'    id="{frame_id}"\n'
        '    enableFullBleed={false}\n'
        '    isHiddenOnDesktop={false}\n'
        '    isHiddenOnMobile={false}\n'
        '    padding="8px 12px"\n'
        '    type="main"\n'
        '  >\n'
        '    <Text\n'
        f'      id="{title_id}"\n'
        '      marginType="normal"\n'
        f'      value="### {title}"\n'
        '      verticalAlign="center"\n'
        '    />\n'
        '  </Frame>\n'
    )

    main_path = os.path.join(app_dir, 'main.rsx')
    with open(main_path, encoding='utf-8') as f:
        main = f.read()
    close = main.rfind('</App>')
    if close < 0:
        fail(f'</App> not found in {main_path}')

    os.makedirs(os.path.dirname(rsx_path), exist_ok=True)
    with open(rsx_path, 'w', encoding='utf-8') as f:
        f.write(screen_xml(page_id, title, order, url_slug, body))
    os.makedirs(os.path.dirname(positions_path), exist_ok=True)
    with open(positions_path, 'w', encoding='utf-8') as f:
        json.dump({title_id: {'height': 0.6, 'width': 12}}, f, indent=2)
        f.write('\n')
    with open(main_path, 'w', encoding='utf-8') as f:
        f.write(main[:close] + f'  <Include src="./src/{page_id}.rsx" />\n' + main[close:])

    print(f'Added page {page_id} (_order={order}, frame {frame_id}, urlSlug "{url_slug}")')
    print(f'  {os.path.relpath(rsx_path, app_dir)}')
    print(f'  {os.path.relpath(positions_path, app_dir)}')
    print(f'  main.rsx: <Include src="./src/{page_id}.rsx" />')
    return rsx_path, frame_id


def main(argv=None):
    parser = argparse.ArgumentParser(description='Add a page (<Screen>) to a multi-page Retool app')
    parser.add_argument('app_dir', help='Path to the app directory')
    parser.add_argument('--id', required=True, help='Page (Screen) id, e.g. settings')
    parser.add_argument('--title', help='Page title (default: the id)')
    parser.add_argument('--url-slug', help='URL slug (default: the id; must be unique)')
    args = parser.parse_args(argv)
    add_page(args.app_dir, args.id, args.title, args.url_slug)


if __name__ == '__main__':
    main()
