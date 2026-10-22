"""IBus engine with native preedit, auxiliary Hangul and candidate UI."""

import argparse
import sys

from korkana import keys
from korkana.native import NativeSession

ENGINE_NAME = "korkana"
BUS_NAME = "org.freedesktop.IBus.KorKana"


def main(argv=None):
    parser = argparse.ArgumentParser(description="KorKana IBus engine")
    parser.add_argument("--ibus", action="store_true",
                        help="started by ibus-daemon from the component XML")
    args = parser.parse_args(argv)
    try:
        import gi
        gi.require_version("IBus", "1.0")
        from gi.repository import IBus, GLib
    except (ImportError, ValueError) as exc:
        print(f"IBus/PyGObject 필요: {exc}\n"
              "설치 안내: docs/PORTING.md", file=sys.stderr)
        return 1

    class KorKanaEngine(IBus.Engine):
        __gtype_name__ = "KorKanaEngine"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.session = NativeSession()
            self.private_input = False

        def _render(self):
            state = self.session.snapshot()
            preedit = self.session.preedit()
            text = IBus.Text.new_from_string(preedit)
            text.append_attribute(IBus.AttrType.UNDERLINE,
                                  IBus.AttrUnderline.SINGLE, 0, len(preedit))
            # CLEAR lets us own focus-out cancellation without a framework
            # auto-commit duplicating text or moving it into another context.
            self.update_preedit_text_with_mode(
                text, len(preedit), bool(preedit), IBus.PreeditFocusMode.CLEAR)
            self.update_auxiliary_text(
                IBus.Text.new_from_string(state["hangul"]), bool(preedit))
            table = IBus.LookupTable.new(9, 0, True, True)
            table.set_orientation(IBus.Orientation.VERTICAL)
            for index, candidate in enumerate(state["candidates"]):
                table.append_candidate(IBus.Text.new_from_string(candidate))
                table.set_label(index, IBus.Text.new_from_string(str(index + 1)))
            table.set_cursor_pos(state["index"])
            self.update_lookup_table(table, state["selecting"])

        def _apply(self, result):
            if result.commits:
                self.hide_preedit_text()
                self.hide_lookup_table()
                for text in result.commits:
                    if text:
                        self.commit_text(IBus.Text.new_from_string(text))
            self._render()
            return result.handled

        def do_process_key_event(self, keyval, keycode, state):
            if state & IBus.ModifierType.RELEASE_MASK or self.private_input:
                return False
            name = IBus.keyval_name(keyval) or ""
            # Modifier/lock key presses must never finalize a syllable.
            if name in {"Shift_L", "Shift_R", "Control_L", "Control_R",
                        "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L",
                        "Meta_R", "Caps_Lock", "Num_Lock", "Scroll_Lock",
                        "ISO_Level3_Shift", "ISO_Level5_Shift"}:
                return False
            codepoint = IBus.keyval_to_unicode(keyval)
            if isinstance(codepoint, str):
                text = codepoint if codepoint != "\0" else ""
            else:
                text = chr(codepoint) if codepoint else ""
            key = keys.SPECIAL_KEYS.get(name, keys.from_character(text))
            # Keypad navigation follows the same composition policy, but the
            # original key retains its app-specific behavior when forwarded.
            if name.startswith("KP_"):
                suffix = name[3:]
                key = keys.SPECIAL_KEYS.get(suffix, key)
                if suffix == "Enter":
                    key = keys.VK_RETURN
            mods = IBus.ModifierType
            return self._apply(self.session.process(
                key, text, shift=bool(state & mods.SHIFT_MASK),
                ctrl=bool(state & mods.CONTROL_MASK),
                alt=bool(state & (mods.MOD1_MASK | mods.MOD5_MASK)),
                meta=bool(state & (mods.SUPER_MASK | mods.META_MASK |
                                   mods.MOD4_MASK)),
            ))

        def do_candidate_clicked(self, index, button, state):
            if button == 1:
                self._apply(self.session.select(index))

        def do_cursor_up(self):
            self._apply(self.session.process(0x26))

        def do_cursor_down(self):
            self._apply(self.session.process(0x28))

        def do_page_up(self):
            self.do_cursor_up()

        def do_page_down(self):
            self.do_cursor_down()

        def do_set_content_type(self, purpose, hints):
            self.private_input = purpose in (
                IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN)
            if self.private_input:
                self.do_reset()

        def do_focus_out(self):
            self.do_reset()

        def do_disable(self):
            self.do_reset()

        def do_reset(self):
            self.session.reset()
            self._render()

    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("IBus에 연결할 수 없습니다. 데스크톱 세션에서 실행하세요.",
              file=sys.stderr)
        return 1
    loop = GLib.MainLoop()
    bus.connect("disconnected", lambda *_: loop.quit())
    factory = IBus.Factory(connection=bus.get_connection(),
                           object_path=IBus.PATH_FACTORY)
    factory.add_engine(ENGINE_NAME, KorKanaEngine)
    if args.ibus:
        bus.request_name(BUS_NAME, 0)
    else:
        component = IBus.Component(
            name=BUS_NAME, description="Korean pronunciation Japanese IME",
            version="0.1.0", license="MIT", author="KorKana contributors",
            homepage="https://github.com/Liter4553/korkana-ime",
            command_line=f"{sys.executable} -m linuxime.engine --ibus")
        component.add_engine(IBus.EngineDesc(
            name=ENGINE_NAME, longname="KorKana", language="ja",
            license="MIT", author="KorKana contributors", layout="us",
            symbol="あ", description="두벌식 한글 발음 일본어 입력기"))
        bus.register_component(component)
        print("KorKana 등록 완료. 다른 터미널에서: ibus engine korkana")
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
