"""Browser automation adapter (behind the same authority layer).

A semantic BrowserAdapter interface, a deterministic FakeBrowserAdapter for
hermetic tests, and a real PlaywrightBrowserAdapter (guarded import) that drives
headless Chromium against LOCAL controlled pages only. Actions are semantic
(role/selector/text), never raw coordinates, and every action is observable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.enums import StrEnum
from .models import ActionResult, ActionStatus


class BrowserRisk(StrEnum):
    READ = "read"          # navigate/inspect/read/screenshot
    MUTATION = "mutation"  # form submit / upload / account change
    HIGH = "high"          # purchase / financial / security / irreversible delete


@runtime_checkable
class BrowserAdapter(Protocol):
    name: str

    def available(self) -> bool: ...
    def launch(self) -> ActionResult: ...
    def set_content(self, html: str) -> ActionResult: ...
    def navigate(self, url: str) -> ActionResult: ...
    def find(self, selector: str) -> int: ...
    def click(self, selector: str) -> ActionResult: ...
    def fill(self, selector: str, value: str) -> ActionResult: ...
    def read_text(self, selector: str) -> str | None: ...
    def input_value(self, selector: str) -> str | None: ...
    def wait_for(self, selector: str, *, timeout: float = 5.0) -> bool: ...
    def close(self) -> ActionResult: ...


# Only local pages are permitted for navigation (controlled test lab). Public
# http(s) navigation is blocked in this milestone.
def _is_local_url(url: str) -> bool:
    u = url.lower().strip()
    return (
        u.startswith("data:")
        or u.startswith("file:")
        or u.startswith("about:")
        or u.startswith("http://127.0.0.1")
        or u.startswith("http://localhost")
    )


# Allowlisted public search-engine hosts. Real web navigation is ONLY permitted
# to these hosts, and ONLY when web search is explicitly enabled (opt-in). This
# keeps the default browser adapter local-only while giving the web-search
# feature a tightly-scoped, auditable capability. DuckDuckGo's HTML endpoint is
# preferred because it renders results server-side (stable, no JS gymnastics).
_SEARCH_HOST_ALLOWLIST: frozenset[str] = frozenset(
    {
        "html.duckduckgo.com",
        "duckduckgo.com",
        "lite.duckduckgo.com",
        "www.bing.com",
        "bing.com",
    }
)


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def _is_allowlisted_search_url(url: str) -> bool:
    u = url.strip().lower()
    if not (u.startswith("https://")):
        return False
    return _host_of(url) in _SEARCH_HOST_ALLOWLIST


class FakeBrowserAdapter:
    """Deterministic in-memory browser: a tiny form page with a confirmation."""

    name = "fake-browser"

    def __init__(self, *, missing_submit: bool = False, delayed: bool = False) -> None:
        self._launched = False
        self._fields: dict[str, str] = {}
        self._submitted = False
        self._missing_submit = missing_submit
        self._delayed = delayed
        self._waits = 0

    def available(self) -> bool:
        return True

    def launch(self) -> ActionResult:
        self._launched = True
        return ActionResult(action_id="b_launch", tool="browser.launch",
                            arguments={}, status=ActionStatus.OK, changed_state=True)

    def set_content(self, html: str) -> ActionResult:
        return ActionResult(action_id="b_set", tool="browser.set_content",
                            arguments={"len": len(html)}, status=ActionStatus.OK)

    def navigate(self, url: str) -> ActionResult:
        if not _is_local_url(url):
            return ActionResult(action_id="b_nav", tool="browser.navigate",
                                arguments={"url": url}, status=ActionStatus.UNSAFE,
                                error="non-local navigation blocked")
        return ActionResult(action_id="b_nav", tool="browser.navigate",
                            arguments={"url": url}, status=ActionStatus.OK, changed_state=True)

    def _selectors(self) -> set[str]:
        s = {"#name", "#email", "#agree"}
        if not self._missing_submit:
            s.add("#submit")
        if self._submitted:
            s.add("#confirmation")
        return s

    def find(self, selector: str) -> int:
        return 1 if selector in self._selectors() else 0

    def click(self, selector: str) -> ActionResult:
        if selector not in self._selectors():
            return ActionResult(action_id="b_click", tool="browser.click",
                                arguments={"selector": selector}, status=ActionStatus.NOT_FOUND)
        if selector == "#submit":
            self._submitted = True
        return ActionResult(action_id="b_click", tool="browser.click",
                            arguments={"selector": selector}, status=ActionStatus.OK, changed_state=True)

    def fill(self, selector: str, value: str) -> ActionResult:
        if selector not in self._selectors():
            return ActionResult(action_id="b_fill", tool="browser.fill",
                                arguments={"selector": selector}, status=ActionStatus.NOT_FOUND)
        self._fields[selector] = value
        # sanitized: never echo the value
        return ActionResult(action_id="b_fill", tool="browser.fill",
                            arguments={"selector": selector, "length": len(value)},
                            status=ActionStatus.OK, changed_state=True)

    def read_text(self, selector: str) -> str | None:
        if selector == "#confirmation" and self._submitted:
            return "Thank you, your form was submitted."
        return None

    def input_value(self, selector: str) -> str | None:
        return self._fields.get(selector)

    def wait_for(self, selector: str, *, timeout: float = 5.0) -> bool:
        if self._delayed and self._waits == 0 and selector == "#confirmation":
            self._waits += 1
            return False
        return selector in self._selectors()

    def close(self) -> ActionResult:
        self._launched = False
        return ActionResult(action_id="b_close", tool="browser.close",
                            arguments={}, status=ActionStatus.OK, changed_state=True)

    # test helpers
    @property
    def submitted(self) -> bool:
        return self._submitted


class PlaywrightBrowserAdapter:
    """Real headless Chromium adapter (local pages only)."""

    name = "playwright"

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None

    def available(self) -> bool:
        try:
            import playwright  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            return False

    def launch(self) -> ActionResult:
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._page = self._browser.new_page()
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="b", tool="browser.launch", arguments={},
                                status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="b", tool="browser.launch", arguments={},
                            status=ActionStatus.OK, changed_state=True)

    def set_content(self, html: str) -> ActionResult:
        self._page.set_content(html)
        return ActionResult(action_id="b", tool="browser.set_content",
                            arguments={"len": len(html)}, status=ActionStatus.OK)

    def navigate(self, url: str) -> ActionResult:
        if not _is_local_url(url):
            return ActionResult(action_id="b", tool="browser.navigate",
                                arguments={"url": url}, status=ActionStatus.UNSAFE,
                                error="non-local navigation blocked")
        self._page.goto(url)
        return ActionResult(action_id="b", tool="browser.navigate",
                            arguments={"url": url}, status=ActionStatus.OK, changed_state=True)

    def find(self, selector: str) -> int:
        return self._page.locator(selector).count()

    def click(self, selector: str) -> ActionResult:
        n = self._page.locator(selector).count()
        if n == 0:
            return ActionResult(action_id="b", tool="browser.click",
                                arguments={"selector": selector}, status=ActionStatus.NOT_FOUND)
        if n > 1:
            return ActionResult(action_id="b", tool="browser.click",
                                arguments={"selector": selector}, status=ActionStatus.AMBIGUOUS,
                                detail=f"{n} matches")
        self._page.click(selector)
        return ActionResult(action_id="b", tool="browser.click",
                            arguments={"selector": selector}, status=ActionStatus.OK, changed_state=True)

    def fill(self, selector: str, value: str) -> ActionResult:
        if self._page.locator(selector).count() == 0:
            return ActionResult(action_id="b", tool="browser.fill",
                                arguments={"selector": selector}, status=ActionStatus.NOT_FOUND)
        self._page.fill(selector, value)
        return ActionResult(action_id="b", tool="browser.fill",
                            arguments={"selector": selector, "length": len(value)},
                            status=ActionStatus.OK, changed_state=True)

    def read_text(self, selector: str) -> str | None:
        if self._page.locator(selector).count() == 0:
            return None
        return self._page.text_content(selector)

    def input_value(self, selector: str) -> str | None:
        if self._page.locator(selector).count() == 0:
            return None
        return self._page.input_value(selector)

    def wait_for(self, selector: str, *, timeout: float = 5.0) -> bool:
        try:
            self._page.wait_for_selector(selector, timeout=int(timeout * 1000))
            return True
        except Exception:  # noqa: BLE001
            return False

    def close(self) -> ActionResult:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        return ActionResult(action_id="b", tool="browser.close", arguments={},
                            status=ActionStatus.OK, changed_state=True)


class WebSearchBrowserAdapter(PlaywrightBrowserAdapter):
    """Real Chromium adapter that ALSO permits navigation to allowlisted public
    search engines — and only when web search is explicitly enabled (opt-in).

    Everything else about it is identical to :class:`PlaywrightBrowserAdapter`:
    same authority chain, same semantic actions, same fail-closed behavior. It
    adds :meth:`read_results`, which extracts REAL result rows (title + href +
    snippet) directly from the live DOM. Nothing is synthesized — a result only
    appears if it exists as an anchor element on the actual page. If the page
    yields no matching anchors, it returns an empty list (never invented data).
    """

    name = "playwright-websearch"

    def __init__(self, *, allow_web: bool = False, headless: bool = True,
                 allow_deep_read: bool = False) -> None:
        super().__init__()
        self._allow_web = bool(allow_web)
        self._headless = bool(headless)
        # deep_read permits navigating to (and reading) a RESULT page beyond the
        # search-engine allowlist. It is a separate, stronger opt-in because it
        # visits arbitrary result hosts. Still https-only; still read-only.
        self._allow_deep_read = bool(allow_deep_read)

    @property
    def allow_web(self) -> bool:
        return self._allow_web

    @property
    def allow_deep_read(self) -> bool:
        return self._allow_deep_read

    def launch(self) -> ActionResult:
        # honor headless/headful choice while reusing the parent lifecycle
        try:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            )
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="b", tool="browser.launch", arguments={},
                                status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="b", tool="browser.launch", arguments={},
                            status=ActionStatus.OK, changed_state=True)

    def navigate(self, url: str) -> ActionResult:
        # local pages are always allowed; real search hosts only when opted in.
        if _is_local_url(url):
            return super().navigate(url)
        if not self._allow_web:
            return ActionResult(action_id="b", tool="browser.navigate",
                                arguments={"url": url}, status=ActionStatus.UNSAFE,
                                error="web navigation not enabled (opt-in required)")
        if not _is_allowlisted_search_url(url):
            # A non-search https host is allowed ONLY under the stronger
            # deep-read opt-in (visiting a real result page for research).
            if not (self._allow_deep_read and url.strip().lower().startswith("https://")):
                return ActionResult(action_id="b", tool="browser.navigate",
                                    arguments={"url": url}, status=ActionStatus.UNSAFE,
                                    error="host not in the search-engine allowlist")
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="b", tool="browser.navigate",
                                arguments={"url": url}, status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="b", tool="browser.navigate",
                            arguments={"url": url}, status=ActionStatus.OK, changed_state=True)

    def current_url(self) -> str | None:
        try:
            return self._page.url if self._page else None
        except Exception:  # noqa: BLE001
            return None

    def read_results(self, selector: str, *, limit: int = 10) -> list[dict]:
        """Extract REAL (title, href, snippet) rows from anchors matching
        ``selector`` on the live page. Returns [] when nothing matches — it
        never fabricates entries. Every row corresponds to a real DOM anchor.
        """

        if self._page is None:
            return []
        try:
            rows = self._page.eval_on_selector_all(
                selector,
                """
                (els) => els.map(a => ({
                    title: (a.innerText || a.textContent || '').trim(),
                    href: a.href || a.getAttribute('href') || '',
                }))
                """,
            )
        except Exception:  # noqa: BLE001
            return []
        out: list[dict] = []
        seen: set[str] = set()
        for r in rows:
            href = _unwrap_redirect((r.get("href") or "").strip())
            title = " ".join((r.get("title") or "").split())
            if not href or not title:
                continue
            if href in seen:
                continue
            seen.add(href)
            out.append({"title": title[:300], "href": href[:2048]})
            if len(out) >= limit:
                break
        return out

    def read_page_text(self, *, max_chars: int = 4000) -> dict | None:
        """Read the CURRENT page's title + visible body text (real DOM only).

        Returns {url, title, text} where text is the page's actual innerText,
        truncated. Returns None if there is no page. This is the raw evidence a
        research agent may summarize — it is DATA, never an instruction.
        """

        if self._page is None:
            return None
        try:
            title = self._page.title()
            text = self._page.eval_on_selector(
                "body", "(b) => b.innerText || b.textContent || ''"
            )
        except Exception:  # noqa: BLE001
            return None
        text = " ".join((text or "").split())
        return {"url": self.current_url() or "", "title": title or "", "text": text[:max_chars]}


def _unwrap_redirect(href: str) -> str:
    """Resolve a search-engine redirect wrapper to the real destination URL.

    Bing wraps results as ``.../ck/a?...&u=a1<base64url>&...`` and DuckDuckGo as
    ``...?uddg=<urlencoded>``. We decode the embedded real target so the
    reported href is the actual page, not the tracker. Falls back to the raw
    href when there is nothing to unwrap (never invents a URL).
    """

    import base64
    from urllib.parse import parse_qs, unquote, urlparse

    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
    except Exception:  # noqa: BLE001
        return href
    # DuckDuckGo redirect
    if "uddg" in qs and qs["uddg"]:
        return unquote(qs["uddg"][0])
    # Bing redirect: u=a1<base64url-of-real-url>
    if "u" in qs and qs["u"]:
        raw = qs["u"][0]
        if raw.startswith("a1"):
            raw = raw[2:]
        pad = "=" * (-len(raw) % 4)
        try:
            decoded = base64.urlsafe_b64decode(raw + pad).decode("utf-8", "replace")
            if decoded.startswith(("http://", "https://")):
                return decoded
        except Exception:  # noqa: BLE001
            return href
    return href
