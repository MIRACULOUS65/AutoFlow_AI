"""Desktop environment detection (honest availability check)."""

from __future__ import annotations

import sys


def desktop_available() -> bool:
    """True only when a real interactive Windows desktop + UIA is reachable.

    Returns False on non-Windows, when uiautomation is missing, or when the
    root control cannot be enumerated (e.g. non-interactive session). Real
    desktop tests use this to SKIP rather than fake a pass.
    """

    if sys.platform != "win32":
        return False
    try:
        import uiautomation as auto
    except Exception:  # noqa: BLE001
        return False
    try:
        root = auto.GetRootControl()
        # enumerating children requires an interactive desktop
        _ = root.GetChildren()
        return True
    except Exception:  # noqa: BLE001
        return False


def desktop_info() -> dict:
    info = {"platform": sys.platform, "available": False, "adapter": None, "windows": 0}
    if not desktop_available():
        return info
    import uiautomation as auto

    info["available"] = True
    info["adapter"] = "windows-uia"
    try:
        info["windows"] = len(auto.GetRootControl().GetChildren())
    except Exception:  # noqa: BLE001
        pass
    return info
