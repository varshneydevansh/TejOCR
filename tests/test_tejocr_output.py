# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import sys
import types
import unittest


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
PYTHON_ROOT = os.path.join(PROJECT_ROOT, "python")
if PYTHON_ROOT not in sys.path:
    sys.path.insert(0, PYTHON_ROOT)


def _install_uno_stubs():
    uno_base = type("UnoBase", (object,), {})
    uno = sys.modules.get("uno", types.ModuleType("uno"))
    uno.Any = lambda *_args: _args[-1] if _args else None
    uno.getConstantByName = lambda _name: None
    uno.systemPathToFileUrl = lambda value: value
    uno.fileUrlToSystemPath = lambda value: value
    uno.createUnoStruct = lambda _name: types.SimpleNamespace()
    sys.modules["uno"] = uno

    unohelper = sys.modules.get("unohelper", types.ModuleType("unohelper"))
    unohelper.Base = uno_base
    sys.modules["unohelper"] = unohelper

    sys.modules.setdefault("com", types.ModuleType("com"))
    sys.modules.setdefault("com.sun", types.ModuleType("com.sun"))
    sys.modules.setdefault("com.sun.star", types.ModuleType("com.sun.star"))

    text_module = sys.modules.get("com.sun.star.text", types.ModuleType("com.sun.star.text"))
    text_module.XTextDocument = type("XTextDocument", (object,), {})
    text_module.XText = type("XText", (object,), {})
    text_module.XTextRange = type("XTextRange", (object,), {})
    text_module.XTextContent = type("XTextContent", (object,), {})
    sys.modules["com.sun.star.text"] = text_module

    container_module = sys.modules.get("com.sun.star.container", types.ModuleType("com.sun.star.container"))
    container_module.XNamed = type("XNamed", (object,), {})
    sys.modules["com.sun.star.container"] = container_module

    data_module = sys.modules.get("com.sun.star.datatransfer", types.ModuleType("com.sun.star.datatransfer"))
    data_module.XTransferable = type("XTransferable", (object,), {})
    data_module.DataFlavor = type("DataFlavor", (object,), {})
    sys.modules["com.sun.star.datatransfer"] = data_module

    clipboard_module = sys.modules.get(
        "com.sun.star.datatransfer.clipboard",
        types.ModuleType("com.sun.star.datatransfer.clipboard"),
    )
    clipboard_module.XClipboard = type("XClipboard", (object,), {})
    sys.modules["com.sun.star.datatransfer.clipboard"] = clipboard_module


_install_uno_stubs()

from tejocr import tejocr_output


class _FakeTextCursor:
    def __init__(self):
        self.props = {}
        self.go_left_calls = []
        self.collapsed = False

    def setPropertyValue(self, name, value):
        self.props[name] = value

    def gotoStart(self, _select):
        return None

    def gotoEnd(self, _select):
        return None

    def goLeft(self, count, select):
        self.go_left_calls.append((count, select))

    def collapseToEnd(self):
        self.collapsed = True


class _FakeText:
    def __init__(self, cursor=None):
        self.cursor = cursor or _FakeTextCursor()

    def createTextCursor(self):
        return self.cursor

    def createTextCursorByRange(self, _range):
        return self.cursor


class _FakeRange:
    def __init__(self, cursor=None):
        self.cursor = cursor or _FakeTextCursor()
        self._text = _FakeText(self.cursor)

    def setPropertyValue(self, name, value):
        self.cursor.setPropertyValue(name, value)

    def getText(self):
        return self._text

    def collapseToEnd(self):
        self.cursor.collapseToEnd()

    def goLeft(self, count, select):
        self.cursor.goLeft(count, select)


class TestTejocrOutputFormatting(unittest.TestCase):
    def test_apply_font_size_to_text_range_sets_all_supported_properties(self):
        target = _FakeTextCursor()

        applied = tejocr_output._apply_font_size_to_text_range(target, 6.0)

        self.assertTrue(applied)
        self.assertEqual(target.props["CharHeight"], 6.0)
        self.assertEqual(target.props["CharHeightAsian"], 6.0)
        self.assertEqual(target.props["CharHeightComplex"], 6.0)

    def test_apply_font_size_to_recent_insertion_selects_recent_text(self):
        cursor = _FakeRange()

        applied = tejocr_output._apply_font_size_to_recent_insertion(cursor, "hello", 6.0)

        self.assertTrue(applied)
        self.assertIn((5, True), cursor.cursor.go_left_calls)
        self.assertEqual(cursor.cursor.props["CharHeight"], 6.0)

    def test_apply_textbox_font_size_styles_entire_text_box(self):
        cursor = _FakeTextCursor()
        frame_text = _FakeText(cursor)

        applied = tejocr_output._apply_textbox_font_size(frame_text, 6.0)

        self.assertTrue(applied)
        self.assertEqual(cursor.props["CharHeight"], 6.0)


if __name__ == "__main__":
    unittest.main()
