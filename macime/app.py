"""InputMethodKit application entry point; build with macime/setup.py on macOS."""

import objc
from AppKit import (NSApplication, NSEventMaskKeyDown, NSEventTypeKeyDown,
                    NSEventModifierFlagShift, NSEventModifierFlagControl,
                    NSEventModifierFlagOption, NSEventModifierFlagCommand)
from Foundation import NSBundle, NSMakeRange, NSNotFound
from InputMethodKit import (IMKInputController, IMKServer, IMKCandidates,
                            kIMKSingleColumnScrollingCandidatePanel,
                            kIMKLocateCandidatesBelowHint,
                            IMKCandidatesSendServerKeyEventFirst)
from PyObjCTools import AppHelper

import applog
from korkana.native import NativeSession
from macime.keymap import translate


_candidate_panel = None


def _panel_for_server(server):
    global _candidate_panel
    if _candidate_panel is None:
        # IMKServer also consults its candidate panel after an input controller
        # closes. Keep one panel alive for the entire server, not per session.
        _candidate_panel = IMKCandidates.alloc().initWithServer_panelType_(
            server, kIMKSingleColumnScrollingCandidatePanel)
        _candidate_panel.setAttributes_({IMKCandidatesSendServerKeyEventFirst: True})
    return _candidate_panel


class KorKanaInputController(IMKInputController):
    def initWithServer_delegate_client_(self, server, delegate, client):
        self = objc.super(KorKanaInputController, self).initWithServer_delegate_client_(
            server, delegate, client)
        if self is not None:
            self.session = NativeSession(automatic_candidates=True)
            self.panel = _panel_for_server(server)
            self.panel_items = ()
            self.syncing = False
            self.has_marked = False
            applog.log("[macOS] input context opened")
        return self

    def recognizedEvents_(self, sender):
        return NSEventMaskKeyDown

    @objc.python_method
    def _apply(self, result, client):
        for text in result.commits:
            if text:
                # insertText replaces the existing marked range atomically.
                client.insertText_replacementRange_(text, NSMakeRange(NSNotFound, 0))
                self.has_marked = False
        self._render(client)
        return result.handled

    @objc.python_method
    def _render(self, client):
        state = self.session.snapshot()
        preedit = self.session.preedit()
        if preedit or self.has_marked:
            # NSTextInput ranges count UTF-16 code units, not Python characters.
            length = len(preedit.encode("utf-16-le")) // 2
            client.setMarkedText_selectionRange_replacementRange_(
                preedit, NSMakeRange(length, 0), NSMakeRange(NSNotFound, 0))
        self.has_marked = bool(preedit)
        items = tuple(state["candidates"])
        self.syncing = True
        try:
            self.panel_items = items
            if items:
                # The shared panel may previously have displayed another
                # context's candidates, even when this context is unchanged.
                self.panel.updateCandidates()
                identifier = self.panel.candidateStringIdentifier_(items[state["index"]])
                self.panel.selectCandidateWithIdentifier_(identifier)
                self.panel.show_(kIMKLocateCandidatesBelowHint)
            else:
                self.panel.hide()
        finally:
            self.syncing = False

    def handleEvent_client_(self, event, client):
        if event.type() != NSEventTypeKeyDown:
            return False
        flags = event.modifierFlags()
        shift = bool(flags & NSEventModifierFlagShift)
        key, text = translate(event.keyCode(), shift)
        try:
            return self._apply(self.session.process(
                key, text, shift=shift,
                ctrl=bool(flags & NSEventModifierFlagControl),
                alt=bool(flags & NSEventModifierFlagOption),
                meta=bool(flags & NSEventModifierFlagCommand)), client)
        except Exception:
            applog.exception("macOS input callback")
            self.session.reset()
            self.panel.hide()
            return False

    def candidates_(self, sender):
        return list(self.panel_items)

    @objc.python_method
    def _candidate_index(self, candidate):
        # Mouse callbacks may carry an attributed string.
        text = str(candidate.string() if hasattr(candidate, "string") else candidate)
        try:
            return self.panel_items.index(text)
        except ValueError:
            return None

    def candidateSelectionChanged_(self, candidate):
        if self.syncing:
            return
        index = self._candidate_index(candidate)
        if index is not None:
            self.session.highlight(index)
            self._render(self.client())

    def candidateSelected_(self, candidate):
        if self.syncing:
            return
        index = self._candidate_index(candidate)
        if index is not None:
            self._apply(self.session.select(index), self.client())

    def commitComposition_(self, sender):
        self._apply(self.session.commit(), sender)

    def deactivateServer_(self, sender):
        self.session.reset()
        if self.has_marked:
            sender.setMarkedText_selectionRange_replacementRange_(
                "", NSMakeRange(0, 0), NSMakeRange(NSNotFound, 0))
            self.has_marked = False
        self.panel.hide()

    def inputControllerWillClose(self):
        self.session.reset()
        self.panel.hide()
        applog.log("[macOS] input context closed")


def main():
    app = NSApplication.sharedApplication()
    bundle = NSBundle.mainBundle()
    connection = bundle.objectForInfoDictionaryKey_("InputMethodConnectionName")
    if not connection:
        raise RuntimeError("Build and install KorKanaIME.app; see docs/PORTING.md")
    # Hold the server for the lifetime of the run loop.
    server = IMKServer.alloc().initWithName_bundleIdentifier_(
        connection, bundle.bundleIdentifier())
    if server is None:
        raise RuntimeError("InputMethodKit server initialization failed")
    _panel_for_server(server)
    applog.log("[macOS] input server started")
    AppHelper.runEventLoop()
    return app, server


if __name__ == "__main__":
    main()
