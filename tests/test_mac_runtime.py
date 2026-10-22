"""Native candidate lifetime regression; requires macOS and PyObjC."""

import gc
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    if sys.platform != "darwin":
        raise ImportError("macOS only")
    from AppKit import NSApplication
    import objc
    from InputMethodKit import IMKServer
    from macime.app import KorKanaInputController
except ImportError:
    IMKServer = None


@unittest.skipIf(IMKServer is None, "requires macOS and PyObjC")
class CandidateLifetimeTests(unittest.TestCase):
    def setUp(self):
        logging = patch("macime.app.applog.log")
        logging.start()
        self.addCleanup(logging.stop)

    def test_panel_survives_input_context_teardown(self):
        application = NSApplication.sharedApplication()
        identifier = uuid.uuid4().hex
        server = IMKServer.alloc().initWithName_bundleIdentifier_(
            "KorKanaLifetimeTest_" + identifier,
            "org.korkana.inputmethod.LifetimeTest" + identifier)
        self.assertIsNotNone(server)
        for _ in range(20):
            controller = KorKanaInputController.alloc().initWithServer_delegate_client_(
                server, None, None)
            panel = objc.WeakRef(controller.panel)
            controller.deactivateServer_(None)
            controller.inputControllerWillClose()
            del controller
            gc.collect()
            # IMKServer queries panel visibility after its controller is gone.
            self.assertIsNotNone(panel(), "candidate panel died with its input context")
            self.assertFalse(panel().isVisible())
        self.assertIsNotNone(application)


if __name__ == "__main__":
    unittest.main()
