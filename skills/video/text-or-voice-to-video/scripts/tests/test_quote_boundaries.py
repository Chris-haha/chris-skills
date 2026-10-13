"""Quoted sentence boundaries must preserve punctuation and speech content."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'prepare_script.py'
spec = importlib.util.spec_from_file_location('quote_prepare', MODULE)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class QuoteBoundariesTests(unittest.TestCase):
    def prepare(self, text):
        with tempfile.TemporaryDirectory() as directory:
            script = prep.prepare(text, directory)
        units = [u['text'] for u in script['units']]
        self.assertEqual(''.join(units), text)
        return units

    def test_chinese_question_quotes_stay_with_their_sentence(self):
        text = '连续追问： “你负责哪一块？” “结果怎么验证？” “如果重做会怎么改？” 这比背答案有用。'
        self.assertEqual(self.prepare(text), [
            '连续追问： “你负责哪一块？”', ' “结果怎么验证？”',
            ' “如果重做会怎么改？”', ' 这比背答案有用。'])

    def test_ascii_and_nested_closers_are_not_next_sentence_prefixes(self):
        self.assertEqual(self.prepare('He asks "Why?" Then says "Try again!" Finish.'),
                         ['He asks "Why?"', ' Then says "Try again!"', ' Finish.'])
        self.assertEqual(self.prepare('他说：「你确定『可以吗？』」下一句。'),
                         ['他说：「你确定『可以吗？』」', '下一句。'])

    def test_chunk_limit_does_not_separate_a_closing_quote(self):
        text = '“' + '长' * 78 + '？”下一句。'
        units = self.prepare(text)
        self.assertFalse(any(u.lstrip().startswith('”') for u in units))
        chunks = prep.split_chunks([text], 80)
        self.assertEqual(''.join(chunks), text)
        self.assertFalse(any(c.lstrip().startswith('”') for c in chunks))

    def test_speech_paragraph_stays_byte_identical_after_unit_splitting(self):
        text = '连续追问：“为什么？” “怎么做？” “还有呢？”结束。'
        units = self.prepare(text)
        self.assertEqual(prep.split_chunks([text], 300), [text])
        self.assertFalse(any(u.lstrip().startswith('”') for u in units))


if __name__ == '__main__':
    unittest.main()
