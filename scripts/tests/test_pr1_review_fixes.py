#!/usr/bin/env python3
"""Regression tests for the review findings on PR #1."""

import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import add_query  # noqa: E402
import validate_app  # noqa: E402


class Pr1ReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.app_dir = tempfile.mkdtemp(prefix="pr1-review-test-")
        for name, content in {
            "main.rsx": '<App><Include src="./src/pane.rsx" /></App>\n',
            "functions.rsx": "<GlobalFunctions>\n</GlobalFunctions>\n",
            "metadata.json": '{}\n',
            ".positions.json": '{}\n',
        }.items():
            with open(os.path.join(self.app_dir, name), "w", encoding="utf-8") as f:
                f.write(content)

    def tearDown(self):
        shutil.rmtree(self.app_dir, ignore_errors=True)

    def _result(self, phrase):
        _name, result = validate_app.validate_app(self.app_dir)
        return next((status, message) for status, message in result.results if phrase in message.lower())

    def test_nested_relative_includes_resolve_from_containing_file(self):
        src_dir = os.path.join(self.app_dir, "src")
        lib_dir = os.path.join(self.app_dir, "lib")
        os.makedirs(src_dir)
        os.makedirs(lib_dir)
        with open(os.path.join(src_dir, "pane.rsx"), "w", encoding="utf-8") as f:
            f.write('<Text id="copy" value={include("../lib/copy.txt", "string")} />\n')
        with open(os.path.join(lib_dir, "copy.txt"), "w", encoding="utf-8") as f:
            f.write("hello\n")

        status, _message = self._result("include")
        self.assertEqual(status, "PASS")

    def test_nested_dangling_parent_include_fails(self):
        src_dir = os.path.join(self.app_dir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "pane.rsx"), "w", encoding="utf-8") as f:
            f.write('<Text id="copy" value={include("../lib/missing.txt", "string")} />\n')

        status, message = self._result("include")
        self.assertEqual(status, "FAIL")
        self.assertIn("../lib/missing.txt", message)

    def test_resource_display_name_does_not_replace_uuid_placeholder(self):
        args = argparse.Namespace(
            id="users", type="SELECT", table="users", sql_file=False,
            sql=None, bulk_primary_key=None, form=None, confirm=None,
            filter_key=None, filter_ref=None, records_ref=None,
            resource_name="your-database", on_success=None,
        )
        query = add_query.build_sql_query(args)
        self.assertIn('resourceDisplayName="your-database"', query)
        self.assertIn('resourceName="REPLACE_WITH_RESOURCE_UUID"', query)

    def test_shared_decimal_grid_edge_is_not_an_overlap(self):
        with open(os.path.join(self.app_dir, "main.rsx"), "w", encoding="utf-8") as f:
            f.write('<App><Text id="a" /><Text id="b" /></App>\n')
        with open(os.path.join(self.app_dir, ".positions.json"), "w", encoding="utf-8") as f:
            json.dump({
                "a": {"row": 18.8, "height": 0.6, "col": 0, "width": 12},
                "b": {"row": 19.4, "height": 0.6, "col": 0, "width": 12},
            }, f)

        status, _message = self._result("grid overlap")
        self.assertEqual(status, "PASS")


if __name__ == "__main__":
    unittest.main()
