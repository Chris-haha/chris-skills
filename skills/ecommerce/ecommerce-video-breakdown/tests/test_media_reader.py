"""Offline contracts for anonymous media acquisition; no network or model install."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from public_media import PublicMediaReader


class MediaReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader = PublicMediaReader(Path(self.temp.name), {})

    def test_xhs_identity_is_required_before_media(self):
        note = {'noteId': 'wrong', 'video': {'media': {'stream': {
            'h264': [{'masterUrl': 'https://cdn.invalid/media.mp4'}]}}}}
        page = 'window.__SETUP_SERVER_STATE__=' + json.dumps({
            'LAUNCHER_SSR_STORE_PAGE_DATA': {'noteData': note}}) + ';</script>'
        url = 'https://www.xiaohongshu.com/explore/abc123?xsec_token=share'
        with patch.object(self.reader, 'fetch', return_value=(page.encode(), url)):
            with self.assertRaisesRegex(ValueError, '身份'):
                self.reader.page_details(url)

    def test_login_page_is_not_an_empty_success(self):
        url = 'https://www.xiaohongshu.com/explore/abc123'
        with patch.object(self.reader, 'fetch', return_value=(b'<html>login</html>', url)):
            with self.assertRaisesRegex(ValueError, '匿名'):
                self.reader.page_details(url)

    def test_multi_part_stops_before_subtitle_requests(self):
        url = 'https://www.bilibili.com/video/BV1234567890'
        payload = {'code': 0, 'data': {'bvid': 'BV1234567890',
                   'pages': [{'cid': 1}, {'cid': 2}]}}
        with patch.object(self.reader, 'fetch', return_value=(json.dumps(payload).encode(), url)) as fetch:
            with self.assertRaisesRegex(ValueError, '多P'):
                self.reader.page_details(url)
        self.assertEqual(fetch.call_count, 1)

    def test_cache_uses_complete_identity_and_actual_frame_times(self):
        url = 'https://www.douyin.com/video/123'
        frame = self.reader.state / 'frame.jpg'
        frame.write_bytes(b'jpeg-fixture')
        details = {'platform': 'douyin', 'video_id': '123', 'creator_id': '42',
                   'url': url, 'info': {'duration': 8}, 'subtitle_text': '重复\n重复',
                   'source': 'subtitle', 'frames': [{'path': str(frame), 'timestamp': 8.57 / 12}],
                   'media_duration': 8.57}
        self.reader.save_result(url, details)
        with patch.object(self.reader, 'page_details', side_effect=AssertionError('cache must avoid requests')):
            result = self.reader.extract(url)
        self.assertEqual(result['frames'], details['frames'])
        self.assertEqual(result['creator_id'], '42')
        self.assertEqual(result['subtitle_text'], '重复\n重复')


if __name__ == '__main__':
    unittest.main()
