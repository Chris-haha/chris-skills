"""POSIX cancellation must reap nested media tools, including their children."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from portable import run_process
from public_media import PublicMediaReader


@unittest.skipIf(os.name == 'nt', 'POSIX process group regression; Windows uses taskkill /T')
class ToolCleanupTests(unittest.TestCase):
    def test_cancelled_worker_reaps_tool_and_grandchild(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ids = root / 'ids.json'
            descendant = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
            tool = ('import json,os,subprocess,sys,time;from pathlib import Path;'
                    'p=subprocess.Popen([sys.executable,"-c",' + repr(descendant) + ']);'
                    'Path(' + repr(str(ids)) + ').write_text(json.dumps([os.getpid(),p.pid]));time.sleep(60)')
            worker = ('import sys;sys.path.insert(0,' + repr(str(SCRIPTS)) + ');'
                      'from public_media import PublicMediaReader;'
                      'PublicMediaReader(' + repr(str(root)) + ',{}).execute([sys.executable,"-c",' + repr(tool) + '],timeout=30)')
            pids = []
            try:
                with self.assertRaisesRegex(RuntimeError, '超时'):
                    run_process([sys.executable, '-c', worker], root, dict(os.environ), root / 'worker.log', timeout=1)
                self.assertTrue(ids.is_file(), 'worker did not reach tool launch')
                pids = json.loads(ids.read_text())
                for pid in pids:
                    for _ in range(100):
                        state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
                        if not state or state.startswith('Z'):
                            break
                        time.sleep(0.02)
                    else:
                        self.fail('cancelled media descendant is still running: ' + str(pid))
            finally:
                if not pids and ids.exists():
                    pids = json.loads(ids.read_text())
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_tool_timeout_reports_failure_and_restores_handlers(self):
        with tempfile.TemporaryDirectory() as temporary:
            reader = PublicMediaReader(temporary, {})
            handlers = [signal.getsignal(signum) for signum in (signal.SIGTERM, signal.SIGINT)]
            with self.assertRaisesRegex(RuntimeError, '媒体工具超时'):
                reader.execute([sys.executable, '-c', 'import time;time.sleep(60)'], timeout=0.1)
            self.assertEqual(handlers, [signal.getsignal(signum) for signum in (signal.SIGTERM, signal.SIGINT)])


if __name__ == '__main__':
    unittest.main()
