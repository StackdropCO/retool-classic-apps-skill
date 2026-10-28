#!/usr/bin/env python3
"""Tests for the multi-page layout (the default) across the skill's scripts.

Stdlib-only (unittest). Run from the repo root:

    python3 -m unittest discover -s scripts/tests

Each test scaffolds or hand-writes a small app in a temp dir. Layout facts the checks
encode come from real Retool exports (expert-directory, an empty multi-page export).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import scaffold_app  # noqa: E402
import validate_app  # noqa: E402


def run(script, *args, check=True):
    """Run a script CLI; return CompletedProcess (stdout+stderr as text)."""
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, script), *args],
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f'{script} {args} failed:\n{proc.stdout}\n{proc.stderr}')
    return proc


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text if isinstance(text, str) else json.dumps(text, indent=2))


def screen(screen_id, order, slug, body, uuid=None):
    return (f'<Screen id="{screen_id}" _order={{{order}}} urlSlug="{slug}" '
            f'uuid="{uuid or screen_id + "-uuid"}">\n{body}\n</Screen>\n')


class MultiPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='multipage-test-')
        self.app = os.path.join(self.tmp, 'app')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def results(self, app=None):
        return validate_app.validate_app(app or self.app)[1].results

    def status(self, phrase, app=None):
        return next(s for s, m in self.results(app) if phrase in m.lower())

    def fails(self, app=None):
        return [m for s, m in self.results(app) if s == 'FAIL']

    def two_pages(self, page2_body='', page2_positions=None):
        """main.rsx -> src/page1.rsx + src/page2.rsx, one Text per page."""
        write(os.path.join(self.app, 'metadata.json'), {'appTemplate': {'rootScreen': 'page1'}})
        write(os.path.join(self.app, 'main.rsx'),
              '<App>\n  <Include src="./src/page1.rsx" />\n  <Include src="./src/page2.rsx" />\n</App>\n')
        write(os.path.join(self.app, 'src', 'page1.rsx'), screen('page1', 0, '',
              '  <Frame id="$main" type="main">\n    <Text id="t1" value="one" />\n  </Frame>'))
        write(os.path.join(self.app, 'src', 'page2.rsx'), screen('page2', 1, 'page2',
              '  <Frame id="$main2" type="main">\n    <Text id="t2" value="two" />\n'
              f'{page2_body}  </Frame>'))
        write(os.path.join(self.app, '.positions', '.page1.positions.json'), {'t1': {'height': 0.6, 'width': 12}})
        write(os.path.join(self.app, '.positions', '.page2.positions.json'),
              {'t2': {'height': 0.6, 'width': 12}} if page2_positions is None else page2_positions)

    # --- validator ---------------------------------------------------------

    def test_two_page_app_passes(self):
        self.two_pages()
        self.assertEqual(self.fails(), [])
        self.assertEqual(self.status("rootscreen 'page1'"), 'PASS')

    def test_tag_text_inside_attribute_is_not_a_tag(self):
        # value="<h4> ..." is real exported RSX; the parser once read <h4> as a tag
        self.two_pages(page2_body='    <Text id="t3" value="<h4> Add a new expert" _comment="see <Screen>" />\n',
                       page2_positions={'t2': {'height': 0.6, 'width': 12}, 't3': {'row': 0.6, 'height': 0.6, 'width': 12}})
        self.assertEqual(self.status('parse correctly'), 'PASS')
        self.assertEqual(self.fails(), [])

    def test_id_in_two_positions_files_fails(self):
        self.two_pages(page2_positions={'t2': {'height': 0.6, 'width': 12}, 't1': {'height': 1, 'width': 12}})
        self.assertEqual(self.status('more than one positions file'), 'FAIL')

    def test_entry_in_another_pages_file_fails(self):
        self.two_pages(page2_positions={})
        write(os.path.join(self.app, '.positions', '.page1.positions.json'),
              {'t1': {'height': 0.6, 'width': 12}, 't2': {'height': 0.6, 'width': 12}})
        self.assertEqual(self.status('wrong page file'), 'FAIL')

    def test_root_screen_must_name_a_screen(self):
        self.two_pages()
        write(os.path.join(self.app, 'metadata.json'), {'appTemplate': {'rootScreen': 'home'}})
        self.assertEqual(self.status("rootscreen 'home'"), 'FAIL')

    def test_duplicate_screen_attrs_and_frame_ids_fail(self):
        self.two_pages()
        write(os.path.join(self.app, 'src', 'page2.rsx'), screen('page2', 0, 'page2',
              '  <Frame id="$main" type="main">\n    <Text id="t2" value="two" />\n  </Frame>',
              uuid='page1-uuid'))
        msg = next(m for s, m in self.results() if 'screen attributes' in m.lower())
        self.assertIn('uuid=page1-uuid', msg)
        self.assertIn('_order=0', msg)
        self.assertIn('$main (2x', next(m for s, m in self.results() if m.startswith('Duplicate IDs')))

    def test_cross_page_reference_warns(self):
        self.two_pages(page2_body='    <Text id="t3" value="{{ t1.value + \'t2\' }}" />\n',
                       page2_positions={'t2': {'height': 0.6, 'width': 12}, 't3': {'row': 0.6, 'height': 0.6, 'width': 12}})
        msg = next(m for s, m in self.results() if s == 'WARN' and 'cross-page' in m.lower())
        self.assertIn('page2 uses t1 (page page1)', msg)
        self.assertNotIn('uses t2', msg)  # inside a string literal, and on its own page anyway

    def test_empty_page_needs_no_positions_file(self):
        # Retool's own export of an empty page has no positions file
        self.two_pages()
        write(os.path.join(self.app, 'src', 'page2.rsx'),
              screen('page2', 1, 'page2', '  <Frame id="$main2" type="main">\n  </Frame>'))
        os.remove(os.path.join(self.app, '.positions', '.page2.positions.json'))
        self.assertEqual(self.fails(), [])

    def test_shapes_retool_exports_are_accepted(self):
        self.two_pages(
            page2_body=('    <Navigation id="nav1">\n      <Option id="0000" />\n'
                        '      <Event id="mockEventHandlerId1" event="click" method="openPage" />\n'
                        '    </Navigation>\n    <Form id="form1">\n      <Header>\n'
                        '        <Text id="formTitle1" value="#### Form title" />\n      </Header>\n    </Form>\n'),
            page2_positions={'t2': {'height': 0.6, 'width': 12}, 'nav1': {'row': 0.6, 'height': 1, 'width': 12},
                             'form1': {'row': 1.6, 'height': 1, 'width': 12},
                             'formTitle1': {'container': 'form1', 'rowGroup': 'header', 'height': 0.6, 'width': 12}})
        self.assertEqual(self.fails(), [])
        self.assertEqual(self.status('form structure'), 'WARN')

    # --- scaffold ----------------------------------------------------------

    def test_every_template_scaffolds_valid_in_both_layouts(self):
        for template in scaffold_app.TEMPLATE_MAP:
            for flag in ([], ['--single-page']):
                with self.subTest(template=template, flag=flag):
                    out = os.path.join(self.tmp, template + ''.join(flag))
                    run('scaffold_app.py', 'Probe', '-t', template, '-o', out, *flag)
                    app = os.path.join(out, 'Probe')
                    self.assertEqual(self.fails(app), [])
                    multipage = not flag
                    self.assertEqual(os.path.isfile(os.path.join(app, 'functions.rsx')), not multipage)
                    self.assertEqual(os.path.isfile(os.path.join(app, '.positions', '.page1.positions.json')),
                                     multipage)
                    self.assertEqual(validate_app.is_multipage(app), multipage)

    def scaffold(self, template='minimal'):
        run('scaffold_app.py', 'app', '-t', template, '-o', self.tmp)
        return self.app

    # --- add_page / add_component / add_query --------------------------------

    def test_add_page_then_add_component_on_each_page(self):
        app = self.scaffold()
        run('add_page.py', app, '--id', 'settings', '--title', 'Settings')
        run('add_component.py', app, '--type', 'TextInput', '--id', 'searchInput',
            '--after', 'pageTitle', '--width', '6')
        run('add_component.py', app, '--type', 'Button', '--id', 'saveBtn', '--screen', 'settings',
            '--after', 'settingsTitle', '--attrs', 'text="Save"', '--width', '2')
        run('add_component.py', app, '--type', 'Text', '--id', 'note', '--screen', 'settings')

        with open(os.path.join(app, 'src', 'settings.rsx'), encoding='utf-8') as f:
            settings = f.read()
        self.assertIn('id="$main2"', settings)
        self.assertIn('_order={1}', settings)
        self.assertIn('id="saveBtn"', settings)
        self.assertIn('    <Text\n      id="note"', settings)  # indented under the frame
        _, source, _ = validate_app.load_positions(app)
        self.assertEqual(source['searchInput'], '.page1.positions.json')
        self.assertEqual(source['saveBtn'], '.settings.positions.json')
        self.assertEqual(source['note'], '.settings.positions.json')
        self.assertEqual(self.fails(app), [])

        wrong = run('add_component.py', app, '--type', 'Text', '--id', 'x', '--screen', 'settings',
                    '--after', 'pageTitle', check=False)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("on page1, not page 'settings'", wrong.stderr)

    def test_add_query_goes_into_the_screen(self):
        app = self.scaffold()
        run('add_query.py', app, '--type', 'SELECT', '--id', 'selectItems', '--table', 'items', '--sql-file')
        with open(os.path.join(app, 'src', 'page1.rsx'), encoding='utf-8') as f:
            page = f.read()
        self.assertLess(page.index('id="selectItems"'), page.index('</Screen>'))
        self.assertIn('include("../lib/selectItems.sql"', page)
        self.assertEqual(self.fails(app), [])

        run('add_page.py', app, '--id', 'page2')
        ambiguous = run('add_query.py', app, '--type', 'javascript', '--id', 'q2', check=False)
        self.assertIn('--screen', ambiguous.stderr)
        run('add_query.py', app, '--type', 'javascript', '--id', 'q2', '--js-file', '--screen', 'page2')
        self.assertEqual(self.fails(app), [])

    # --- fix_positions -------------------------------------------------------

    def test_fix_positions_fixes_each_page_file_on_its_own(self):
        self.two_pages(page2_body='    <Text id="t3" value="three" />\n',
                       page2_positions={'t2': {'height': 0.6, 'width': 12},
                                        't3': {'row': 0.3, 'height': 0.6, 'width': 12}})
        page1 = os.path.join(self.app, '.positions', '.page1.positions.json')
        page2 = os.path.join(self.app, '.positions', '.page2.positions.json')
        with open(page1, encoding='utf-8') as f:
            before = f.read()

        dry = run('fix_positions.py', self.app, '--screen', 'page1', '--apply')
        self.assertIn('No changes needed', dry.stdout)
        run('fix_positions.py', self.app, '--apply')
        with open(page2, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['t3'].get('row'), 0.6)  # stacked under t2
        with open(page1, encoding='utf-8') as f:
            self.assertEqual(f.read(), before)  # t1 sits at row 0 on its own page: untouched

    # --- extract_component / list_components ---------------------------------

    def test_extract_component_from_a_page(self):
        app = self.scaffold()
        run('extract_component.py', app, '--component', 'setupGuideModal')
        with open(os.path.join(app, 'src', 'page1.rsx'), encoding='utf-8') as f:
            self.assertIn('<Include src="./setupGuideModal.rsx" />', f.read())
        self.assertEqual(self.fails(app), [])

    def test_list_components_shows_pages_and_nested_includes(self):
        self.two_pages()
        write(os.path.join(self.app, 'src', 'drawer.rsx'), '<DrawerFrame id="drawer1">\n</DrawerFrame>\n')
        with open(os.path.join(self.app, 'src', 'page2.rsx'), encoding='utf-8') as f:
            page2 = f.read().replace('</Screen>', '  <Include src="./drawer.rsx" />\n</Screen>')
        write(os.path.join(self.app, 'src', 'page2.rsx'), page2)
        tree = run('list_components.py', self.app).stdout
        self.assertIn('Screen page2 /page2', tree)
        self.assertIn('DrawerFrame drawer1  (src/drawer.rsx)', tree)


if __name__ == '__main__':
    unittest.main()
