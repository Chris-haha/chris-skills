# -*- coding: utf-8 -*-
"""Behavioral checks for a query planner; no network or real company data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_research.py'

class PlannerTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_public_names_round_trip_without_duplicate_aliases(self):
        name = '测试 & 合作（某城）有限公司'
        result = self.invoke('--name', name, '--former-name', name, '--former-name', '测试旧名有限公司', '--engines', '360,bing')
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan['subject']['names'], [name, '测试旧名有限公司'])
        for route in plan['routes']:
            query = parse_qs(urlsplit(route['url']).query)['q'][0]
            self.assertEqual(query, route['query'])
            self.assertEqual(route['status'], 'planned')
            self.assertNotIn('results', route)
        families = {route['backend_family'] for route in plan['routes']}
        self.assertEqual(families, {'360', 'bing'})
        self.assertEqual(len({r['url'] for r in plan['routes']}), len(plan['routes']))

    def test_queries_include_identity_adverse_and_counterevidence(self):
        result = self.invoke('--name', '虚构公司', '--city', '某市', '--credit-code', 'MOCK-CODE', '--engines', 'baidu')
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual({q['purpose'] for q in plan['queries']}, {'identity', 'refund', 'official-records', 'follow-up'})
        self.assertTrue(any('MOCK-CODE' in q['query'] for q in plan['queries']))
        self.assertTrue(any('已退' in q['query'] or '整改' in q['query'] for q in plan['queries']))
        self.assertFalse(plan['collection_performed'])

    def test_existing_evidence_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'evidence.json'
            target.write_text('existing evidence')
            result = self.invoke('--name', '虚构公司', '--output', str(target))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(), 'existing evidence')

    def test_bad_engine_and_empty_name_are_rejected(self):
        for args in [('--name', '虚构公司', '--engines', 'unknown'), ('--name', '  ')]:
            self.assertNotEqual(self.invoke(*args).returncode, 0)

if __name__ == '__main__':
    unittest.main()
