#!/usr/bin/env python3
"""Run the suite and fail CI closed if headless GUI coverage disappears."""
import os
import re
import sys
import unittest


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def main() -> int:
    require_gui = os.environ.get("HERMESKEY_REQUIRE_GUI_TESTS") == "1"
    if require_gui:
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            print("CI requires QT_QPA_PLATFORM=offscreen; refusing desktop access.", file=sys.stderr)
            return 1
        try:
            from PySide6.QtWidgets import QApplication  # noqa: F401
        except ImportError as exc:
            # Keep CI diagnostics useful without dumping an uncontrolled
            # import exception (which may contain private filesystem paths).
            library = re.search(r"\blib[A-Za-z0-9_+.-]+\.so(?:\.[0-9]+)*\b", str(exc))
            reason = f"missing {library.group()}" if library else "Qt import failed"
            print(f"CI requires PySide6 for the test Python ({reason}); GUI tests cannot skip.", file=sys.stderr)
            return 1

    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    selected = list(cases(suite))
    # This module is mandatory even if a future refactor inadvertently removes
    # its tests. All skips, including future GUI tests, fail required CI runs.
    settings_cases = [test for test in selected if test.id().startswith("test_settings_shell.")]
    if require_gui and not settings_cases:
        print("CI did not discover Settings GUI tests.", file=sys.stderr)
        return 1

    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if require_gui and (result.skipped or result.testsRun != len(selected)):
        print(f"CI requires every test to run: {len(result.skipped)} skipped; "
              f"{result.testsRun}/{len(selected)} attempted.", file=sys.stderr)
        return 1
    if require_gui:
        print(f"Settings GUI tests ran headlessly: {len(settings_cases)}; no tests skipped.")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
