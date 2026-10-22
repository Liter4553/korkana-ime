"""Exercise the real optional dictionary from an installation path with spaces."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from korkana import kanji

try:
    from mozcpy import mozcpy as backend
except ImportError:
    backend = None


class DictionaryPathTests(unittest.TestCase):
    @unittest.skipIf(backend is None or os.name != "posix", "requires mozcpy on POSIX")
    def test_real_conversion_from_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="KorKana Input Methods ") as temp:
            dictionary = Path(temp) / "dictionary"
            dictionary.symlink_to(Path(backend.DICT_DIR).resolve(), target_is_directory=True)
            with patch.object(backend, "DICT_DIR", str(dictionary)), \
                    patch.object(backend, "MECAB_ARGS", f"-d {dictionary} -r /dev/null"), \
                    patch.multiple(kanji, _loaded=False, _converter=None, _load_error=None):
                self.assertTrue(kanji.available(), kanji.dict_info())
                self.assertIn("私は学生です", kanji.candidates("わたしはがくせいです"))
                self.assertIn("東京", kanji.candidates("とうきょう"))


if __name__ == "__main__":
    unittest.main()
