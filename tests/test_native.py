"""Portable regression tests for native adapters; no GUI/OS dependencies.

    python -m unittest discover -s tests -p test_native.py -v
"""

import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from korkana import keys
from korkana.native import NativeSession
from linuxime.install import component_xml, install
from macime.keymap import translate


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.session = NativeSession()
        # Stable dictionary results on all machines, including kana-only builds.
        self.dictionary = patch("korkana.composition.candidates",
                                return_value=["私は学生です", "わたしはがくせいです"])
        self.dictionary.start()
        self.addCleanup(self.dictionary.stop)

    def type(self, text, session=None):
        session = session or self.session
        for char in text:
            result = session.process(keys.from_character(char), char,
                                     shift=char.isupper())
            self.assertTrue(result.handled)
            self.assertEqual(result.commits, ())

    def test_kana_commit(self):
        self.type("gkwlapaktlEp")
        self.assertEqual(self.session.snapshot()["hangul"], "하지메마시떼")
        self.assertEqual(self.session.preedit(), "はじめまして")
        self.assertEqual(self.session.process(keys.VK_RETURN).commits, ("はじめまして",))
        self.assertEqual(self.session.preedit(), "")

    def test_ordered_punctuation(self):
        self.type("gk")
        self.assertEqual(self.session.process(keys.from_character("."), ".").commits,
                         ("は", "。"))

    def test_shifted_symbol_and_digit_order(self):
        for char in (">", "{", "!", "2", "_"):
            with self.subTest(char=char):
                self.type("gk")
                result = self.session.process(keys.from_character(char), char,
                                              shift=char in ">{!_")
                self.assertTrue(result.handled)
                self.assertEqual(result.commits, ("は", char))

    def test_tab_preserves_app_navigation(self):
        self.type("gk")
        result = self.session.process(keys.VK_TAB, "\t")
        self.assertFalse(result.handled)
        self.assertEqual(result.commits, ("は",))

    def test_empty_controls_pass_through(self):
        for key in (keys.VK_RETURN, keys.VK_BACK, keys.VK_SPACE, keys.VK_ESCAPE, 0):
            self.assertFalse(self.session.process(key).handled)

    def test_shortcuts_commit_then_pass(self):
        for modifier in ("ctrl", "alt", "meta"):
            self.type("gk")
            result = self.session.process(ord("C"), "c", **{modifier: True})
            self.assertFalse(result.handled)
            self.assertEqual(result.commits, ("は",))

    def test_candidate_navigation_and_number(self):
        self.type("dkxktlgkrn tpdleptm".replace(" ", ""))
        self.assertTrue(self.session.process(keys.VK_SPACE).handled)
        self.assertEqual(self.session.preedit(), "私は学生です")
        self.session.process(0x28)
        self.assertEqual(self.session.preedit(), "わたしはがくせいです")
        self.assertEqual(self.session.process(ord("1"), "1").commits, ("私は学生です",))

    def test_candidate_click(self):
        self.type("gk")
        self.session.process(keys.VK_SPACE)
        self.assertEqual(self.session.select(1).commits, ("わたしはがくせいです",))
        self.assertEqual(self.session.preedit(), "")

    def test_escape_twice(self):
        self.type("gk")
        self.session.process(keys.VK_SPACE)
        self.session.process(keys.VK_ESCAPE)
        self.assertEqual(self.session.preedit(), "は")
        self.session.process(keys.VK_ESCAPE)
        self.assertEqual(self.session.preedit(), "")

    def test_katakana_preserves_kanji(self):
        self.session.controller.katakana = True
        self.type("fk-aps")
        self.assertEqual(self.session.process(keys.VK_SPACE).commits, ("ラーメン",))
        # Candidate text must never get converted to katakana.
        self.session.controller.katakana = False
        self.type("gk")
        self.session.process(keys.VK_SPACE)
        self.session.controller.katakana = True
        self.assertEqual(self.session.commit().commits, ("私は学生です",))

    def test_shifted_vowel_and_modifier(self):
        self.type("s")
        self.assertFalse(self.session.process(0x10, shift=True).handled)
        self.type("O")
        self.assertEqual(self.session.snapshot()["hangul"], "냬")
        self.assertEqual(self.session.preedit(), "にぇ")

    def test_backspace_and_consonant_visibility(self):
        self.type("zydn")  # 쿄우
        self.session.process(keys.VK_BACK)  # remove ㅜ, leaving 쿄 + ㅇ
        self.assertEqual(self.session.snapshot()["reading"], "きょ")
        self.assertEqual(self.session.preedit(), "きょㅇ")
        self.session.process(keys.VK_BACK)
        self.assertEqual(self.session.snapshot()["hangul"], "쿄")
        self.session.reset()
        self.type("w")
        self.assertEqual(self.session.preedit(), "ㅈ")
        self.session.process(keys.VK_BACK)
        self.assertEqual(self.session.preedit(), "")

    def test_context_reset_isolation(self):
        other = NativeSession()
        self.type("gk")
        self.assertEqual(other.preedit(), "")
        self.session.reset()
        self.assertEqual(self.session.commit().commits, ())
        self.type("gk", other)
        self.assertEqual(other.commit().commits, ("は",))

    def test_native_quit_does_not_kill_server(self):
        self.type("gk")
        result = self.session.process(ord("Q"), "q", ctrl=True, alt=True)
        self.assertFalse(result.handled)
        self.assertEqual(result.commits, ("は",))
        self.assertFalse(self.session.controller.quit_requested())

    def test_native_keyup_bookkeeping_does_not_accumulate(self):
        self.type("gkwlapaktlEp")
        self.assertEqual(self.session.controller._swallowed, set())

    def test_mac_physical_keys(self):
        self.assertEqual(translate(5), (ord("G"), "g"))
        self.assertEqual(translate(14, True), (ord("E"), "E"))
        self.assertEqual(translate(47, True), (keys.from_character("."), ">"))
        self.assertEqual(translate(48), (keys.VK_TAB, ""))
        self.assertEqual(translate(123), (0x25, ""))
        self.assertEqual(translate(999), (0, ""))

    def test_mac_sequence_matches_core(self):
        for code in (5, 40, 13, 34, 37, 14):
            key, text = translate(code, code == 14)
            self.session.process(key, text, shift=code == 14)
        # More useful explicit equality against the same physical QWERTY input.
        expected = NativeSession()
        self.type("gkwilE", expected)
        self.assertEqual(self.session.snapshot(), expected.snapshot())

    def test_installer_escaping_and_copied_modules(self):
        with tempfile.TemporaryDirectory(prefix="korkana & '") as tmp:
            descriptor = install(Path(tmp), Path(sys.executable))
            tree = ET.fromstring(descriptor.read_text(encoding="utf-8"))
            command = shlex.split(tree.findtext("exec"))
            self.assertEqual(command[1:], ["--ibus"])
            launcher = Path(command[0])
            self.assertTrue(launcher.is_file())
            self.assertIn(shlex.quote(str(Path(sys.executable))),
                          launcher.read_text(encoding="utf-8"))
            self.assertTrue((launcher.parent / "korkana" / "controller.py").is_file())
            self.assertEqual(tree.findtext("engines/engine/name"), "korkana")

    def test_cli_and_core_never_import_winapi(self):
        code = """
import sys
sys.modules['winime'] = None
import ime
from korkana.native import NativeSession
assert ime.main(['--convert', '하지메마시떼']) == 0
assert NativeSession().preedit() == ''
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, encoding="utf-8",
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("はじめまして", result.stdout)


if __name__ == "__main__":
    unittest.main()
