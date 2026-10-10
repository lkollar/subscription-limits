import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('limits', Path(__file__).parents[1] / 'server.py')
limits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(limits)

NOW = 1577836800

def row(provider='codex'):
    return {'provider':provider, 'usage':{'updatedAt':'2020-01-01T00:00:00Z',
        'primary':{'windowMinutes':300,'usedPercent':25,'resetsAt':'2020-01-01T05:00:00Z'},
        'secondary':{'windowMinutes':10080,'usedPercent':50,'resetsAt':'2020-01-08T00:00:00Z'},
        'identity':{'access_token':'SECRET'}, 'accountEmail':'private@example.com'},
        'credits':{'otherSecret':'SECRET'}}

class Tests(unittest.TestCase):
    def test_allowlist_and_correct_windows(self):
        data = limits.normalize(row(),'codex',NOW)
        self.assertEqual(data['windows']['fiveHour']['usedPercent'],25)
        self.assertEqual(data['windows']['weekly']['usedPercent'],50)
        self.assertNotIn('SECRET',json.dumps(data))
        self.assertNotIn('private@example.com',json.dumps(data))

    def test_unknown_window_is_unavailable(self):
        data = row()
        data['usage']['secondary']['windowMinutes']=43200
        result=limits.normalize(data,'codex',NOW)
        self.assertIsNone(result['windows']['weekly'])

    def test_bad_percentage_never_becomes_zero(self):
        for value in [None,True,'13',float('nan'),101,-1]:
            data=row();data['usage']['primary']['usedPercent']=value
            result=limits.normalize(data,'codex',NOW)
            self.assertIsNone(result['windows']['fiveHour'])

    def test_missing_reset_retains_usage(self):
        data=row();data['usage']['primary']['resetsAt']='bad'
        self.assertIsNone(limits.normalize(data,'codex',NOW)['windows']['fiveHour']['resetsAt'])

    def test_invalid_time_and_future_rejected(self):
        for value in ['2020-01-01T00:00:00','bad','2099-01-01T00:00:00Z']:
            data=row();data['usage']['updatedAt']=value
            with self.assertRaises(ValueError):limits.normalize(data,'codex',NOW)

    def test_failure_preserves_success_and_marks_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=limits.Collector(Path(directory))
            self.assertEqual(collector.snapshot(NOW)['providers'][0]['status'],'unavailable')
            collector.good['codex']=limits.normalize(row(),'codex',NOW)
            self.assertEqual(collector.snapshot(NOW)['providers'][1]['status'],'fresh')
            collector.errors['codex']='auth'
            item=collector.snapshot(NOW)['providers'][1]
            self.assertEqual(item['status'],'stale')
            self.assertEqual(item['windows']['fiveHour']['usedPercent'],25)
            collector.errors.clear()
            self.assertEqual(collector.snapshot(NOW+901)['providers'][1]['status'],'stale')

    def test_reset_due_marks_recent_data_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=limits.Collector(Path(directory))
            data=row()
            data['usage']['primary']['resetsAt']='2020-01-01T00:00:30Z'
            collector.good['codex']=limits.normalize(data,'codex',NOW)
            self.assertEqual(collector.snapshot(NOW+31)['providers'][1]['status'],'stale')

    def test_restart_cache_remains_valid_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=limits.Collector(Path(directory))
            with patch.object(limits,'fetch',side_effect=lambda p:(limits.normalize(row(p),p,NOW),None)):
                collector.refresh()
            cache=Path(directory)/'last-good.json'
            self.assertEqual(cache.stat().st_mode & 0o777,0o600)
            self.assertNotIn('SECRET',cache.read_text())
            saved=limits.Collector(Path(directory))
            self.assertEqual(saved.snapshot(NOW)['providers'][0]['status'],'fresh')

    def test_manual_refresh_coalescing(self):
        with tempfile.TemporaryDirectory() as directory:
            collector=limits.Collector(Path(directory))
            collector.last_attempt=time.monotonic()
            self.assertFalse(collector.request_refresh())
            collector.last_attempt=0
            self.assertTrue(collector.request_refresh())
            collector.refreshing=True
            self.assertFalse(collector.request_refresh())

    def test_claude_cli_fallback_only_for_auth(self):
        from subprocess import CompletedProcess
        expired={'provider':'claude','error':{'message':'Claude OAuth token expired. SECRET'}}
        calls=[]
        def fake(args,**kwargs):
            calls.append(args)
            return CompletedProcess(args,0,json.dumps([expired if len(calls)==1 else row('claude')]),'')
        with patch.object(limits.subprocess,'run',side_effect=fake):
            data,error=limits.fetch('claude')
        self.assertIsNone(error)
        self.assertEqual(data['id'],'claude')
        self.assertEqual([c[c.index('--source')+1] for c in calls],['oauth','cli'])

    def test_real_data_contract(self):
        location=os.environ.get('LIVE_USAGE_JSON')
        if not location:self.skipTest('Set LIVE_USAGE_JSON for an optional private probe')
        live=Path(location)
        for data in json.loads(live.read_text()):
            self.assertFalse(data.get('error'))
            normalized=limits.normalize(data,data['provider'])
            for window in normalized['windows'].values():self.assertIsNotNone(window)
            self.assertEqual(set(normalized),{'id','lastSuccess','windows'})

if __name__=='__main__':unittest.main()
