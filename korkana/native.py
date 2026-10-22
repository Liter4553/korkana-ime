"""Shared boundary for native IMEs: ordered text output, no key injection.

Each native input context owns a session. Framework callbacks run on the UI
thread; output is collected before touching the client to avoid reentrancy while
the controller's lock is held.
"""

from dataclasses import dataclass

from . import keys
from .kanji import candidates
from .controller import KoreanKanaIME, HOTKEY_QUIT


@dataclass(frozen=True)
class Result:
    handled: bool
    commits: tuple[str, ...] = ()


class NativeSession:
    def __init__(self, *, automatic_candidates=False):
        self._output = []
        self._text = ""
        self._forward = False
        self.automatic_candidates = automatic_candidates
        self._preview_reading = ""
        self._preview_items = []
        self._dismissed_hangul = None
        self.controller = KoreanKanaIME(
            enabled=True, send_text=self._output.append,
            send_key=self._replay_text,
        )

    def _replay_text(self, key):
        # Tab must retain its focus/navigation behavior in the client app.
        if self._text and self._text.isprintable():
            self._output.append(self._text)
        else:
            self._forward = True

    def process(self, key, text="", *, shift=False, ctrl=False,
                alt=False, meta=False):
        self._output.clear()
        self._text = text
        self._forward = False
        before = self.controller.snapshot()
        if not (shift or ctrl or alt or meta):
            preview = self._suggestions(before)
            if preview and key == keys.VK_ESCAPE:
                self._dismissed_hangul = before["hangul"]
                return Result(True)
            if preview and key in (0x26, 0x28):
                self.highlight(len(preview) - 1 if key == 0x26 else 0)
                return Result(True)
            if preview and ord("1") <= key <= ord("9"):
                return self.select(key - ord("1"))
        # Native IMEs are managed by the OS. Never terminate the shared server
        # using the Windows-only quit shortcut.
        if ctrl and alt and not meta and key == HOTKEY_QUIT:
            self.controller.commit()
            return Result(False, tuple(self._output))
        handled = self.controller.on_key(key, True, shift, ctrl, alt, meta)
        # IMK only subscribes to keyDown. Balance internal key bookkeeping here.
        self.controller.on_key(key, False, shift, ctrl, alt, meta)
        after = self.controller.snapshot()
        if before["selecting"] and not after["selecting"] and key in (
                keys.VK_ESCAPE, keys.VK_BACK):
            self._dismissed_hangul = after["hangul"]
        elif after["hangul"] != before["hangul"]:
            self._dismissed_hangul = None
        return Result(handled and not self._forward, tuple(self._output))

    def commit(self):
        self._output.clear()
        self.controller.commit()
        return Result(True, tuple(self._output))

    def select(self, index):
        if self.highlight(index):
            return self.commit()
        return Result(bool(self.snapshot()["candidates"]))

    def highlight(self, index):
        state = self.snapshot()
        if not 0 <= index < len(state["candidates"]):
            return False
        # Previewing must not enter conversion mode: subsequent letters still
        # edit the same phrase until the user explicitly chooses a candidate.
        if not state["selecting"]:
            self.controller.comp.cands = list(state["candidates"])
        return self.controller.comp.select(index)

    def reset(self):
        self._output.clear()
        self.controller.reset()
        self._preview_reading = ""
        self._preview_items = []
        self._dismissed_hangul = None

    def _suggestions(self, state):
        if (not self.automatic_candidates or state["selecting"]
                or not state["enabled"] or state["katakana"]
                or not state["reading"]
                or state["hangul"] == self._dismissed_hangul):
            return []
        if state["reading"] != self._preview_reading:
            self._preview_reading = state["reading"]
            self._preview_items = candidates(state["reading"])
        return self._preview_items

    def snapshot(self):
        state = self.controller.snapshot()
        if not state["selecting"]:
            state["candidates"] = list(self._suggestions(state))
        return state

    def preedit(self):
        state = self.snapshot()
        if state["selecting"]:
            return state["candidates"][state["index"]]
        # A consonant without a vowel has no kana yet. Keep it visible so the
        # user can see and delete it rather than showing an empty marked range.
        composer = self.controller.comp.composer
        pending = composer.pending() if composer.jung is None else ""
        return state["reading"] + pending
