"""Shared boundary for native IMEs: ordered text output, no key injection.

Each native input context owns a session. Framework callbacks run on the UI
thread; output is collected before touching the client to avoid reentrancy while
the controller's lock is held.
"""

from dataclasses import dataclass

from .controller import KoreanKanaIME, HOTKEY_QUIT


@dataclass(frozen=True)
class Result:
    handled: bool
    commits: tuple[str, ...] = ()


class NativeSession:
    def __init__(self):
        self._output = []
        self._text = ""
        self._forward = False
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
        # Native IMEs are managed by the OS. Never terminate the shared server
        # using the Windows-only quit shortcut.
        if ctrl and alt and not meta and key == HOTKEY_QUIT:
            self.controller.commit()
            return Result(False, tuple(self._output))
        handled = self.controller.on_key(key, True, shift, ctrl, alt, meta)
        # IMK only subscribes to keyDown. Balance internal key bookkeeping here.
        self.controller.on_key(key, False, shift, ctrl, alt, meta)
        return Result(handled and not self._forward, tuple(self._output))

    def commit(self):
        self._output.clear()
        self.controller.commit()
        return Result(True, tuple(self._output))

    def select(self, index):
        if self.controller.comp.select(index):
            return self.commit()
        return Result(False)

    def reset(self):
        self._output.clear()
        self.controller.reset()

    def snapshot(self):
        return self.controller.snapshot()

    def preedit(self):
        state = self.snapshot()
        if state["selecting"]:
            return state["candidates"][state["index"]]
        # A consonant without a vowel has no kana yet. Keep it visible so the
        # user can see and delete it rather than showing an empty marked range.
        composer = self.controller.comp.composer
        pending = composer.pending() if composer.jung is None else ""
        return state["reading"] + pending
