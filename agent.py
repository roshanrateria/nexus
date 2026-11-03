import asyncio
import base64
import json
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal
import urllib.request
import urllib.robotparser
from urllib.parse import urljoin, urlsplit

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, StreamWriter
from playwright.async_api import async_playwright
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter

from ledger import Ledger, LedgerHandler
from schemas import (
    AgentState,
    ClickArgs,
    EmptyArgs,
    ExecutorInput,
    ExecutorOutput,
    ExecutorState,
    GetPageTextArgs,
    HoverArgs,
    NavigateArgs,
    NewTabArgs,
    PlannerDecision,
    PressKeyArgs,
    RunJavascriptArgs,
    ScrollArgs,
    ScrollToTextArgs,
    SelectOptionArgs,
    Settings,
    TabArgs,
    TypeTextArgs,
    VerificationResult,
    WaitArgs,
)

PROMPTS = yaml.safe_load((Path(__file__).parent / "prompts.yml").read_text(encoding="utf-8"))
REPORT_RE = re.compile(PROMPTS["executor"]["report_pattern"], re.IGNORECASE)

# Sentinel for "robots.txt could not be fetched": cached fail-open decision.
_ROBOTS_FAIL_OPEN = object()

SNAPSHOT_JS = """
({start, margin, maxChars, ref}) => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const interactiveTags = new Set(['a', 'button', 'input', 'select', 'textarea', 'summary']);
  const roles = new Set(['button', 'link', 'checkbox', 'radio', 'tab', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'switch', 'combobox', 'textbox', 'searchbox', 'slider', 'spinbutton', 'treeitem', 'listbox']);
  const skip = new Set(['script', 'style', 'noscript', 'template', 'head', 'meta', 'link', 'svg', 'canvas', 'iframe', 'frame', 'object', 'embed', 'option']);
  const lines = [];
  const boxes = [];
  let buffer = [];
  let index = start;
  let size = 0;
  let truncated = false;
  const clean = (text) => text.replace(/\\s+/g, ' ').trim();
  const flush = () => {
    if (buffer.length) {
      const text = clean(buffer.join(' '));
      if (text) {
        lines.push(text.slice(0, 400));
        size += Math.min(text.length, 400);
      }
      buffer = [];
    }
  };
  const inView = (rect) => rect.bottom > -margin && rect.top < vh + margin && rect.right > -margin && rect.left < vw + margin;
  const labelOf = (el) => {
    const text = (el.innerText || '').split(/\\n+/).map(clean).filter(Boolean).join(' | ');
    const img = el.querySelector('img[alt]');
    return (text || el.getAttribute('aria-label') || el.getAttribute('title') || (img && img.alt) || el.getAttribute('placeholder') || '').slice(0, 200);
  };
  const attrsOf = (el, tag) => {
    const out = [];
    const add = (key, value) => {
      if (value !== null && value !== undefined && value !== '') out.push(key + '=' + JSON.stringify(String(value).slice(0, 100)));
    };
    add('type', el.getAttribute('type'));
    add('role', el.getAttribute('role'));
    add('aria-label', el.getAttribute('aria-label'));
    add('placeholder', el.getAttribute('placeholder'));
    add('name', el.getAttribute('name'));
    if (tag === 'a') add('href', el.getAttribute('href'));
    if (tag === 'input' || tag === 'textarea' || tag === 'select') add('value', el.type === 'password' ? (el.value ? '***' : '') : el.value);
    if (tag === 'select') add('options', Array.from(el.options).slice(0, 20).map((o) => clean(o.text)).join(' | '));
    if (el.checked) out.push('checked');
    if (el.disabled) out.push('disabled');
    add('expanded', el.getAttribute('aria-expanded'));
    add('selected', el.getAttribute('aria-selected'));
    return out.join(' ');
  };
  const walk = (node, inside) => {
    if (truncated) return;
    if (size > maxChars) { truncated = true; return; }
    if (node.nodeType === 3) {
      if (!inside) buffer.push(node.textContent);
      return;
    }
    if (node.nodeType !== 1) return;
    const tag = node.tagName.toLowerCase();
    if (skip.has(tag)) return;
    if (tag === 'input' && node.type === 'hidden') return;
    if (!node.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return;
    if (tag === 'br') { flush(); return; }
    const rect = node.getBoundingClientRect();
    const sized = rect.width > 0 && rect.height > 0;
    if (sized && !inView(rect)) return;
    const style = getComputedStyle(node);
    const role = node.getAttribute('role');
    const parentStyle = node.parentElement ? getComputedStyle(node.parentElement) : null;
    const pointerRoot = style.cursor === 'pointer' && !(parentStyle && parentStyle.cursor === 'pointer');
    const editable = node.getAttribute('contenteditable') === 'true' || node.getAttribute('contenteditable') === '';
    const interactive = sized && (interactiveTags.has(tag) || (role && roles.has(role)) || node.hasAttribute('onclick') || editable || (node.hasAttribute('tabindex') && node.tabIndex >= 0) || pointerRoot);
    const scrollable = sized && tag !== 'body' && tag !== 'html' && (style.overflowY === 'auto' || style.overflowY === 'scroll') && node.scrollHeight > node.clientHeight + 8;
    const block = !style.display.startsWith('inline');
    if (interactive || scrollable) {
      flush();
      const i = index++;
      node.setAttribute('data-agent-ref', ref + ':' + i);
      boxes.push({i, x: rect.x, y: rect.y, w: rect.width, h: rect.height});
      const attrs = (attrsOf(node, tag) + (scrollable ? ' scrollable' : '')).trim();
      const label = interactive ? labelOf(node) : '';
      const head = '[' + i + ']<' + tag + (attrs ? ' ' + attrs : '');
      lines.push(label ? head + '>' + label + '</' + tag + '>' : head + '/>');
      size += head.length + label.length;
    } else if (block) {
      flush();
    }
    const childInside = inside || interactive;
    if (node.shadowRoot) node.shadowRoot.childNodes.forEach((child) => walk(child, childInside));
    node.childNodes.forEach((child) => walk(child, childInside));
    if (block || interactive) flush();
  };
  if (document.body) walk(document.body, false);
  flush();
  const doc = document.scrollingElement || document.documentElement;
  let scrollY = window.scrollY || (doc ? doc.scrollTop : 0);
  let scrollHeight = doc ? doc.scrollHeight : window.innerHeight;
  let innerHeight = vh;
  if (scrollHeight <= innerHeight + 20 && scrollY === 0) {
    let maxScroll = 0;
    for (const el of document.querySelectorAll('*')) {
      const style = getComputedStyle(el);
      if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 20) {
        const scrollable = el.scrollHeight - el.clientHeight;
        if (scrollable > maxScroll) {
          maxScroll = scrollable;
          scrollY = el.scrollTop;
          scrollHeight = el.scrollHeight;
          innerHeight = el.clientHeight;
        }
      }
    }
  }
  return {lines, boxes, next: index, truncated, size, scrollY, scrollHeight, innerHeight, innerWidth: vw, title: document.title};
}
"""

MARKS_JS = """
(boxes) => {
  const root = document.createElement('div');
  root.id = '__agent_marks__';
  root.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none';
  for (const b of boxes) {
    if (b.x > window.innerWidth || b.y > window.innerHeight || b.x + b.w < 0 || b.y + b.h < 0) continue;
    const box = document.createElement('div');
    box.style.cssText = `position:fixed;left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;border:2px solid #e11d48;box-sizing:border-box;pointer-events:none`;
    const tag = document.createElement('span');
    tag.textContent = b.i;
    tag.style.cssText = 'position:absolute;left:0;top:-14px;background:#e11d48;color:#fff;font:bold 11px/14px monospace;padding:0 3px;pointer-events:none';
    box.appendChild(tag);
    root.appendChild(box);
  }
  document.documentElement.appendChild(root);
}
"""

CLEAR_MARKS_JS = """
() => {
  const root = document.getElementById('__agent_marks__');
  if (root) root.remove();
}
"""

LINKS_JS = """
(limit) => Array.from(document.querySelectorAll('a[href]'))
  .filter((a) => a.checkVisibility())
  .map((a) => ((a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80) || a.getAttribute('aria-label') || '') + ' -> ' + a.href)
  .filter((value, i, all) => all.indexOf(value) === i)
  .slice(0, limit)
"""


@dataclass
class Observation:
    text: str
    screenshot: str
    url: str
    title: str


def _origin(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _fetch_robots(origin: str) -> urllib.robotparser.RobotFileParser | None:
    """Fetch and parse a robots.txt; None means the fetch failed (fail open)."""
    try:
        with urllib.request.urlopen(f"{origin}/robots.txt", timeout=10) as response:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(response.read().decode("utf-8", "replace").splitlines())
            return parser
    except Exception:
        return None


RUNS_DIR = "runs"
_shot_lock = threading.Lock()
_shot_counters: dict[str, int] = {}


def save_shot(run_id: str, b64: str) -> str:
    """Write a screenshot as runs/<run_id>/shots/<seq>.jpg; returns "<run_id>/<seq>.jpg"."""
    with _shot_lock:
        seq = _shot_counters.get(run_id, 0) + 1
        _shot_counters[run_id] = seq
    directory = Path(RUNS_DIR) / run_id / "shots"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{seq}.jpg").write_bytes(base64.b64decode(b64))
    return f"{run_id}/{seq}.jpg"


class BrowserSession:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = asyncio.Lock()
        self.ref = 0
        self.frame_ranges: list = []
        self.dialogs: list[str] = []
        self._robots: dict[str, urllib.robotparser.RobotFileParser | object] = {}

    async def __aenter__(self) -> "BrowserSession":
        s = self.settings
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            s.browser_profile_dir,
            headless=s.browser_headless,
            channel=s.browser_channel or None,
            viewport={"width": s.browser_viewport_width, "height": s.browser_viewport_height},
            locale=s.browser_locale,
            timezone_id=s.browser_timezone,
            extra_http_headers=s.browser_extra_headers,
            args=s.browser_launch_args,
        )
        self.context.set_default_timeout(s.action_timeout_ms)
        self.context.set_default_navigation_timeout(s.navigation_timeout_ms)
        self.context.on("page", self._adopt)
        self.page = self.context.pages[0]
        self.page.on("dialog", self._on_dialog)
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.context.close()
        await self.playwright.stop()

    def _adopt(self, page) -> None:
        self.page = page
        page.on("dialog", self._on_dialog)

    async def _on_dialog(self, dialog) -> None:
        self.dialogs.append(f"{dialog.type}: {dialog.message}")
        await dialog.accept()

    async def _robots_allows(self, url: str) -> bool:
        origin = _origin(url)
        if origin is None:
            return True
        if origin not in self._robots:
            parser = await asyncio.to_thread(_fetch_robots, origin)
            self._robots[origin] = parser if parser is not None else _ROBOTS_FAIL_OPEN
        parser = self._robots[origin]
        return parser is _ROBOTS_FAIL_OPEN or parser.can_fetch("*", url)

    @property
    def active_page(self):
        if self.page.is_closed():
            self.page = self.context.pages[-1]
        return self.page

    async def _settle(self) -> None:
        page = self.active_page
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(self.settings.settle_ms)

    def locator(self, index: int):
        for start, end, frame in self.frame_ranges:
            if start <= index < end:
                return frame.locator(f'[data-agent-ref="{self.ref}:{index}"]').first
        raise ValueError(f"No element with index {index} in the current page state. Use only indexes listed in the latest state.")

    async def observe(self, marks: bool = True) -> Observation:
        s = self.settings
        page = self.active_page
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(s.settle_ms)
        self.ref += 1
        self.frame_ranges = []
        lines: list[str] = []
        boxes: list[dict] = []
        head = None
        start = 0
        budget = s.max_observation_chars
        truncated = False
        for frame in page.frames:
            offset = {"x": 0, "y": 0}
            if head is not None:
                box = await (await frame.frame_element()).bounding_box()
                margin = s.observation_viewport_margin
                if box is None or box["width"] < 30 or box["height"] < 30 or box["y"] > head["innerHeight"] + margin or box["y"] + box["height"] < -margin:
                    continue
                offset = box
            data = await frame.evaluate(
                SNAPSHOT_JS,
                {"start": start, "margin": s.observation_viewport_margin, "maxChars": budget, "ref": self.ref},
            )
            if head is None:
                head = data
            else:
                lines.append(f"--- embedded frame {frame.url[:100]} ---")
            lines.extend(data["lines"])
            boxes.extend({**b, "x": b["x"] + offset["x"], "y": b["y"] + offset["y"]} for b in data["boxes"])
            self.frame_ranges.append((start, data["next"], frame))
            start = data["next"]
            budget -= data["size"]
            truncated = truncated or data["truncated"]
            if budget <= 0:
                truncated = True
                break
        tabs = [
            f"  [{i}]{' (active)' if p == page else ''} {await p.title()} - {p.url}"
            for i, p in enumerate(self.context.pages)
        ]
        below = max(0, head["scrollHeight"] - head["scrollY"] - head["innerHeight"])
        parts = [
            f"URL: {page.url}",
            f"Title: {head['title']}",
            "Tabs:",
            *tabs,
            f"Scroll: {round(head['scrollY'])}px above, {round(below)}px below (viewport {head['innerWidth']}x{head['innerHeight']})",
        ]
        if self.dialogs:
            parts.append("Dialogs dismissed automatically since the last state: " + "; ".join(self.dialogs))
            self.dialogs.clear()
        parts.append("Page content:")
        parts.extend(lines)
        if truncated:
            parts.append("[Content cut off here. Scroll or use get_page_text to see the rest.]")
        if marks:
            await page.evaluate(MARKS_JS, boxes)
        shot = await page.screenshot(type="jpeg", quality=s.screenshot_quality, animations="disabled", caret="hide")
        if marks:
            await page.evaluate(CLEAR_MARKS_JS)
        return Observation("\n".join(parts), base64.b64encode(shot).decode(), page.url, head["title"])

    async def read_text(self, index: int | None, start: int, include_links: bool, limit: int) -> str:
        page = self.active_page
        body = await page.evaluate("() => document.body.innerText") if index is None else await self.locator(index).inner_text()
        if include_links:
            links = await page.evaluate(LINKS_JS, self.settings.max_links)
            body += "\n\nLINKS:\n" + "\n".join(links)
        end = min(start + limit, len(body))
        more = f"\n[Output cut off. Call get_page_text again with start={end} to continue.]" if end < len(body) else ""
        return f"URL: {page.url}\nTitle: {await page.title()}\nCharacters {start}-{end} of {len(body)}\n---\n{body[start:end]}{more}"

    async def navigate(self, url: str) -> str:
        page = self.active_page
        target = urljoin(page.url, url)
        if not await self._robots_allows(target):
            raise ValueError("blocked by robots.txt")
        response = await page.goto(target, wait_until="domcontentloaded")
        await self._settle()
        status = f" (HTTP {response.status})" if response else ""
        return f"Navigated to {self.active_page.url}{status}"

    async def go_back(self) -> str:
        await self.active_page.go_back(wait_until="domcontentloaded")
        await self._settle()
        return f"Went back to {self.active_page.url}"

    async def click(self, index: int) -> str:
        locator = self.locator(index)
        before_pages = len(self.context.pages)
        before_url = self.active_page.url
        await locator.click()
        await self._settle()
        if len(self.context.pages) == before_pages:
            await self.active_page.wait_for_timeout(self.settings.settle_ms)
        if len(self.context.pages) > before_pages:
            return f"Clicked element {index}. A new tab opened and is now active. Active URL: {self.active_page.url}"
        url_change = f" URL remained {before_url}" if self.active_page.url == before_url else f" Active URL: {self.active_page.url}"
        return f"Clicked element {index}.{url_change}"

    async def type_text(self, index: int, text: str, submit: bool = False, clear: bool = True) -> str:
        locator = self.locator(index)
        await locator.click()
        if clear:
            await locator.fill("")
        s = self.settings
        await locator.press_sequentially(text, delay=s.typing_delay_ms, timeout=s.action_timeout_ms + len(text) * s.typing_delay_ms * 2)
        if submit:
            await locator.press("Enter")
        await self._settle()
        return f"Typed {len(text)} characters into element {index}{' and pressed Enter' if submit else ''}. Active URL: {self.active_page.url}"

    async def press_key(self, key: str) -> str:
        await self.active_page.keyboard.press(key)
        await self._settle()
        return f"Pressed {key}. Active URL: {self.active_page.url}"

    async def select_option(self, index: int, option: str) -> str:
        chosen = await self.locator(index).select_option(option)
        await self._settle()
        return f"Selected {chosen} in element {index}"

    async def hover(self, index: int) -> str:
        await self.locator(index).hover()
        await self.active_page.wait_for_timeout(self.settings.settle_ms)
        return f"Hovered over element {index}"

    async def scroll(self, direction: str, pages: float = 1.0, index: int | None = None) -> str:
        page = self.active_page
        sign = -1 if direction == "up" else 1
        size = page.viewport_size
        if index is None:
            pos = await page.evaluate(
                """() => {
  const doc = document.scrollingElement || document.documentElement;
  if (doc.scrollHeight > window.innerHeight + 20 || window.scrollY > 0) {
    return null;
  }
  let best = null;
  let maxScroll = 0;
  for (const el of document.querySelectorAll('*')) {
    const style = getComputedStyle(el);
    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 20) {
      const scrollable = el.scrollHeight - el.clientHeight;
      if (scrollable > maxScroll) {
        maxScroll = scrollable;
        best = el;
      }
    }
  }
  if (best) {
    const r = best.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2, height: r.height};
  }
  return null;
}"""
            )
            if pos:
                await page.mouse.move(pos["x"], pos["y"])
                delta = sign * pages * pos["height"]
            else:
                await page.mouse.move(size["width"] / 2, size["height"] / 2)
                delta = sign * pages * size["height"]
        else:
            box = await self.locator(index).bounding_box()
            await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            delta = sign * pages * box["height"]
        await page.mouse.wheel(0, delta)
        await page.wait_for_timeout(self.settings.settle_ms)
        y, total, height = await page.evaluate(
            """() => {
  const doc = document.scrollingElement || document.documentElement;
  let scrollY = window.scrollY || (doc ? doc.scrollTop : 0);
  let scrollHeight = doc ? doc.scrollHeight : window.innerHeight;
  let innerHeight = window.innerHeight;
  if (scrollHeight <= innerHeight + 20 && scrollY === 0) {
    let maxScroll = 0;
    for (const el of document.querySelectorAll('*')) {
      const style = getComputedStyle(el);
      if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 20) {
        const scrollable = el.scrollHeight - el.clientHeight;
        if (scrollable > maxScroll) {
          maxScroll = scrollable;
          scrollY = el.scrollTop;
          scrollHeight = el.scrollHeight;
          innerHeight = el.clientHeight;
        }
      }
    }
  }
  return [Math.round(scrollY), scrollHeight, innerHeight];
}"""
        )
        return f"Scrolled {direction}. Page is at {y}px of {total}px (viewport height {height}px)"

    async def scroll_to_text(self, text: str) -> str:
        await self.active_page.get_by_text(text).first.scroll_into_view_if_needed()
        await self.active_page.wait_for_timeout(self.settings.settle_ms)
        return f"Scrolled to the text {text!r}"

    async def get_page_text(self, index: int | None = None, start: int = 0, include_links: bool = False) -> str:
        return await self.read_text(index, start, include_links, self.settings.max_page_text_chars)

    async def run_javascript(self, expression: str) -> str:
        result = await self.active_page.evaluate(expression)
        text = json.dumps(result, ensure_ascii=False, default=str)
        limit = self.settings.max_page_text_chars
        more = f"\n[Output cut off after {limit} of {len(text)} characters]" if len(text) > limit else ""
        return f"URL: {self.active_page.url}\n{text[:limit]}{more}"

    async def wait(self, seconds: float = 2.0) -> str:
        await self.active_page.wait_for_timeout(seconds * 1000)
        return f"Waited {seconds} seconds"

    async def switch_tab(self, tab_index: int) -> str:
        self.page = self.context.pages[tab_index]
        await self.page.bring_to_front()
        return f"Switched to tab {tab_index}: {self.page.url}"

    async def new_tab(self, url: str) -> str:
        page = await self.context.new_page()
        self.page = page
        await page.goto(url, wait_until="domcontentloaded")
        await self._settle()
        return f"Opened a new tab at {page.url}"

    async def close_tab(self, tab_index: int) -> str:
        await self.context.pages[tab_index].close()
        self.page = self.context.pages[-1]
        return f"Closed tab {tab_index}. Active tab: {self.page.url}"


@dataclass
class Models:
    planner: Runnable
    executor: BaseChatModel
    verifier: Runnable
    reporter: BaseChatModel


def reject_none(value):
    if value is None:
        raise ValueError("the model returned no structured output")
    return value


# Typography folding for verbatim evidence matching: a quote must survive
# curly quotes, dashes, NBSP and zero-width characters the page throws at us.
_CHAR_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2015": "-", "\u2212": "-", "\ufe63": "-", "\u2043": "-",
    "\u00a0": " ", "\u202f": " ", "\u2007": " ", "\u2029": " ", "\u2028": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "", "\u00ad": "",
}
_CHAR_TABLE = str.maketrans(_CHAR_MAP)


def _norm(s: str) -> str:
    """Casefold, collapse whitespace and fold typography so verbatim checks are
    stable across copy differences: NFKC, curly quotes -> straight, en/em dash
    and minus -> "-", NBSP -> space, zero-width characters -> empty."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s).translate(_CHAR_TABLE)).strip().casefold()


def evidence_is_real(original_text: str, *sources: str) -> bool:
    """True iff the (whitespace-normalized) excerpt appears verbatim in one source."""
    needle = _norm(original_text)
    return bool(needle) and any(needle in _norm(src) for src in sources)


def require_action(message: AIMessage) -> AIMessage:
    if message.tool_calls or REPORT_RE.match(message.text):
        return message
    raise ValueError("the response was neither a tool call nor a final report starting with STATUS")


def require_report(message: AIMessage) -> AIMessage:
    if REPORT_RE.match(message.text):
        return message
    raise ValueError("the final report must start with STATUS")


META_BASE_URL = "https://api.meta.ai/v1"
BASETEN_BASE_URL = "https://inference.baseten.co/v1"
BASETEN_MODEL = "meta-models/muse-spark-open-1026"

# LLM endpoint keys used by the Privacy Ledger: "cloud" = hosted Meta Model API,
# "open" = open-weights models on Baseten (runs on credits, not billed tokens).


def check_model_key(settings: Settings) -> None:
    """Runner-start preflight: GET /v1/models with the Bearer key.

    A 401 means the key itself is bad: print a clear message and exit.
    Network trouble (and any other HTTP status) only warns: the run may still
    work, so don't hard-kill the server.
    """
    request = urllib.request.Request(
        f"{META_BASE_URL}/models", headers={"Authorization": f"Bearer {settings.model_api_key}"}
    )
    try:
        urllib.request.urlopen(request, timeout=15)
        print(f"Preflight OK: key accepted by {META_BASE_URL}/models")
    except urllib.error.HTTPError as error:
        if error.code == 401:
            print(
                f"MODEL_API_KEY was rejected with HTTP 401. Check the key at dev.meta.ai (API keys) and update"
                f" MODEL_API_KEY in .env. (This preflight request was GET {META_BASE_URL}/models.)"
            )
            raise SystemExit(1)
        print(f"Preflight warning: {META_BASE_URL}/models returned HTTP {error.code}; continuing anyway.")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"Preflight warning: could not reach {META_BASE_URL}/models ({type(error).__name__}: {error}) — continuing anyway, calls may fail at runtime.")


def resolve_mode(settings: Settings) -> Literal["hybrid", "cloud"]:
    """nexus_mode auto: hybrid when BASETEN_API_KEY is set, else cloud-only."""
    if settings.nexus_mode == "auto":
        return "hybrid" if settings.baseten_api_key else "cloud"
    return settings.nexus_mode


def role_endpoint(settings: Settings, role: str) -> Literal["cloud", "open"]:
    """Hybrid keeps planner + reporter on Meta (text-only) and gives the
    screenshot-seeing executor + verifier to the open-weights endpoint; cloud-only runs every role on Meta."""
    if resolve_mode(settings) == "hybrid" and role in ("executor", "verifier"):
        return "open"
    return "cloud"


def build_models(settings: Settings, ledger: Ledger) -> Models:
    """One ChatOpenAI per role against its resolved endpoint.

    Every role gets a LedgerHandler counting what leaves the machine; planner
    and reporter handlers are ALWAYS text_only. All four roles share one
    endpoint budget (rate_limit_rpm) and `reasoning_effort` is only sent to the
    Meta endpoint (the open-weights Baseten model does not use it).
    """

    limiters = {
        endpoint: InMemoryRateLimiter(
            requests_per_second=settings.rate_limit_rpm / 60, check_every_n_seconds=0.05, max_bucket_size=1
        )
        for endpoint in ("cloud", "open")
    }

    def make(role: str) -> BaseChatModel:
        endpoint = role_endpoint(settings, role)
        meta = endpoint == "cloud"
        model = getattr(settings, f"{role}_model") if meta else BASETEN_MODEL
        return ChatOpenAI(
            model=model,
            base_url=META_BASE_URL if meta else BASETEN_BASE_URL,
            api_key=settings.model_api_key if meta else settings.baseten_api_key,
            max_tokens=getattr(settings, f"{role}_max_tokens"),
            reasoning_effort=getattr(settings, f"{role}_reasoning_effort") if meta else None,
            rate_limiter=limiters[endpoint],
            max_retries=1,
            stream_usage=True,
            callbacks=[LedgerHandler(ledger, role, endpoint, model=model, text_only=role in ("planner", "reporter"))],
        )

    return Models(
        planner=make("planner").with_structured_output(PlannerDecision, method=settings.structured_method, strict=False) | RunnableLambda(reject_none),
        executor=make("executor"),
        verifier=make("verifier").with_structured_output(VerificationResult, method=settings.structured_method, strict=False) | RunnableLambda(reject_none),
        reporter=make("reporter"),
    )


async def with_backoff(role: str, factory: Callable[[], Awaitable[Any]], writer: StreamWriter, settings: Settings) -> Any:
    def notify(state) -> None:
        error = state.outcome.exception()
        writer(
            {
                "type": "retry",
                "role": role,
                "attempt": state.attempt_number,
                "max": settings.llm_max_attempts,
                "error": f"{type(error).__name__}: {error}"[: settings.event_text_chars],
                "wait": round(state.next_action.sleep, 1),
            }
        )

    retrying = AsyncRetrying(
        stop=stop_after_attempt(settings.llm_max_attempts),
        wait=wait_exponential_jitter(initial=settings.retry_initial_seconds, max=settings.retry_max_seconds),
        before_sleep=notify,
        reraise=True,
    )
    async for attempt in retrying:
        with attempt:
            return await factory()


def serialized(browser: BrowserSession, fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
    async def run(**kwargs) -> str:
        async with browser.lock:
            return await fn(**kwargs)

    return run


def build_tools(browser: BrowserSession) -> list[StructuredTool]:
    registry = [
        ("navigate", NavigateArgs, browser.navigate, False),
        ("go_back", EmptyArgs, browser.go_back, False),
        ("click", ClickArgs, browser.click, False),
        ("type_text", TypeTextArgs, browser.type_text, False),
        ("press_key", PressKeyArgs, browser.press_key, False),
        ("select_option", SelectOptionArgs, browser.select_option, False),
        ("hover", HoverArgs, browser.hover, False),
        ("scroll", ScrollArgs, browser.scroll, False),
        ("scroll_to_text", ScrollToTextArgs, browser.scroll_to_text, False),
        ("get_page_text", GetPageTextArgs, browser.get_page_text, True),
        ("run_javascript", RunJavascriptArgs, browser.run_javascript, True),
        ("wait", WaitArgs, browser.wait, False),
        ("switch_tab", TabArgs, browser.switch_tab, False),
        ("new_tab", NewTabArgs, browser.new_tab, False),
        ("close_tab", TabArgs, browser.close_tab, False),
    ]
    if not browser.settings.allow_run_javascript:
        registry = [entry for entry in registry if entry[0] != "run_javascript"]
    return [
        StructuredTool.from_function(
            coroutine=serialized(browser, fn),
            name=name,
            description=PROMPTS["tools"][name],
            args_schema=schema,
            metadata={"produces_content": produces},
        )
        for name, schema, fn, produces in registry
    ]


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def render_log(messages: list, tools_by_name: dict[str, StructuredTool]) -> str:
    calls: dict[str, dict] = {}
    lines: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            calls.update({call["id"]: call for call in message.tool_calls})
        elif isinstance(message, ToolMessage):
            call = calls[message.tool_call_id]
            keeps_content = tools_by_name[call["name"]].metadata["produces_content"]
            content = message.content if keeps_content else clip(message.content, 300)
            lines.append(f"{len(lines) + 1}. {call['name']}({json.dumps(call['args'], ensure_ascii=False)}) -> [{message.status}] {content}")
    return "\n".join(lines) or PROMPTS["executor"]["empty_log"]


def collect_artifacts(messages: list, tools_by_name: dict[str, StructuredTool], limit: int) -> str:
    blocks = [
        message.content
        for message in messages
        if isinstance(message, ToolMessage) and message.status != "error" and tools_by_name[message.name].metadata["produces_content"]
    ]
    return "\n\n".join(blocks)[:limit]


def build_executor(settings: Settings, models: Models, browser: BrowserSession):
    prompts = PROMPTS["executor"]
    tools = build_tools(browser)
    tools_by_name = {tool.name: tool for tool in tools}
    tool_node = ToolNode(tools, handle_tool_errors=True)
    acting = models.executor.bind_tools(tools) | RunnableLambda(require_action)
    reporting = models.executor | RunnableLambda(require_report)

    async def observe(state: ExecutorState, writer: StreamWriter) -> dict:
        snapshot = await with_backoff("browser", browser.observe, writer, settings)
        writer(
            {
                "type": "observe",
                "iteration": state.get("iterations", 0),
                "url": snapshot.url,
                "title": snapshot.title,
                "shot": save_shot(state.get("run_id", "default"), snapshot.screenshot),
            }
        )
        return {"observation": snapshot.text, "screenshot": snapshot.screenshot}

    async def agent(state: ExecutorState, writer: StreamWriter) -> dict:
        used = state.get("iterations", 0)
        exhausted = used >= settings.max_step_iterations
        text = prompts["user"].format(
            step=state["current_step"],
            log=render_log(state.get("messages", []), tools_by_name),
            observation=state["observation"],
            used=used,
            budget=settings.max_step_iterations,
        )
        if exhausted:
            text += "\n\n" + prompts["budget_exhausted"]
        prompt = [
            SystemMessage(prompts["system"]),
            HumanMessage(
                content=[
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{state['screenshot']}"}},
                ]
            ),
        ]
        chain = reporting if exhausted else acting
        message = await with_backoff("executor", lambda: chain.ainvoke(prompt), writer, settings)
        if message.tool_calls:
            for call in message.tool_calls:
                writer({"type": "action", "iteration": used, "name": call["name"], "args": call["args"]})
            return {"messages": [message]}
        report = message.text.strip()
        writer({"type": "executor_report", "report": report})
        return {
            "messages": [message],
            "executor_report": report,
            # Give the verifier the DOM-extracted snapshot text as an evidence
            # source: it contains aria-labels/hrefs/value text that innerText lacks.
            "step_artifacts": collect_artifacts(state.get("messages", []), tools_by_name, settings.max_artifact_chars),
            "observation": state.get("observation", ""),
        }

    async def act(state: ExecutorState, writer: StreamWriter, config: RunnableConfig) -> dict:
        result = await tool_node.ainvoke({"messages": state["messages"]}, config)
        for message in result["messages"]:
            writer(
                {
                    "type": "action_result",
                    "name": message.name,
                    "ok": message.status != "error",
                    "content": clip(message.content, settings.event_text_chars),
                }
            )
        return {"messages": result["messages"], "iterations": state.get("iterations", 0) + 1}

    def route_after_agent(state: ExecutorState) -> str:
        return "act" if state["messages"][-1].tool_calls else END

    graph = StateGraph(ExecutorState, input_schema=ExecutorInput, output_schema=ExecutorOutput)
    graph.add_node("observe", observe)
    graph.add_node("agent", agent)
    graph.add_node("act", act)
    graph.add_edge(START, "observe")
    graph.add_edge("observe", "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"act": "act", END: END})
    graph.add_edge("act", "observe")
    return graph.compile(checkpointer=False, name="executor")


def render_history(history: list[dict]) -> str:
    prompts = PROMPTS["planner"]
    return "\n".join(
        prompts["history_item"].format(
            number=number,
            instruction=record["instruction"],
            verdict=prompts["verdict_complete"] if record["complete"] else prompts["verdict_incomplete"],
            assessment=record["assessment"],
            report=record["report"],
            evidence=" ".join((f"{e['id']}: " if e.get("id") else "") + e["summarized"] for e in record["evidences"]) or prompts["no_evidence"],
        )
        for number, record in enumerate(history, 1)
    )


def render_plan(plan: list[dict]) -> str:
    template = PROMPTS["planner"]["plan_item"]
    return "\n".join(
        template.format(number=number, instruction=step["instruction"], expected=step["expected_outcome"])
        for number, step in enumerate(plan, 1)
    )


def build_graph(settings: Settings, models: Models, browser: BrowserSession, checkpointer):
    executor = build_executor(settings, models, browser)

    async def planner(state: AgentState, writer: StreamWriter) -> Command[Literal["executor", "reporter"]]:
        prompts = PROMPTS["planner"]
        rounds = state.get("planner_rounds", 0)
        history = state.get("history", [])
        if rounds >= settings.max_planner_rounds:
            note = f"The planning budget of {settings.max_planner_rounds} rounds was used up before the goal was confirmed as achieved."
            writer({"type": "budget", "message": note})
            return Command(update={"status": "budget_exhausted", "final_assessment": note}, goto="reporter")
        if history:
            user = prompts["update"].format(
                goal=state["goal"],
                url=state.get("browser_url", ""),
                history=render_history(history),
                plan=render_plan(state.get("plan", [])),
            )
        else:
            user = prompts["initial"].format(goal=state["goal"])
        messages = [SystemMessage(prompts["system"]), HumanMessage(user)]
        decision: PlannerDecision = await with_backoff("planner", lambda: models.planner.ainvoke(messages), writer, settings)
        plan = [step.model_dump() for step in decision.plan]
        writer(
            {
                "type": "plan",
                "round": rounds + 1,
                "status": decision.status,
                "thought": decision.thought,
                "final_assessment": decision.final_assessment,
                "plan": plan,
            }
        )
        update = {"plan": plan, "planner_rounds": rounds + 1, "status": decision.status, "final_assessment": decision.final_assessment, "local_retries": 0}
        if decision.status == "continue":
            first = decision.plan[0]
            step_text = PROMPTS["executor"]["step"].format(instruction=first.instruction, expected=first.expected_outcome)
            if history and not history[-1]["complete"]:
                step_text += f"\nPrevious attempt was NOT complete: {history[-1]['assessment']}. Do not repeat failed actions; use an alternate approach."
            update["current_step"] = step_text
            return Command(update=update, goto="executor")
        return Command(update=update, goto="reporter")

    async def verifier(state: AgentState, writer: StreamWriter) -> dict:
        prompts = PROMPTS["verifier"]
        step = state["plan"][0]
        snapshot = await with_backoff("browser", lambda: browser.observe(marks=False), writer, settings)
        page_text = await with_backoff(
            "browser",
            lambda: browser.read_text(None, 0, False, settings.verifier_page_text_chars),
            writer,
            settings,
        )
        text = prompts["user"].format(
            goal=state["goal"],
            step=step["instruction"],
            expected=step["expected_outcome"],
            report=state["executor_report"],
            artifacts=state["step_artifacts"] or prompts["no_artifacts"],
            url=snapshot.url,
            title=snapshot.title,
            page_text=page_text,
        )
        messages = [
            SystemMessage(prompts["system"]),
            HumanMessage(
                content=[
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{snapshot.screenshot}"}},
                ]
            ),
        ]
        result: VerificationResult = await with_backoff("verifier", lambda: models.verifier.ainvoke(messages), writer, settings)

        # T3: deterministic evidence check -- the verifier never grades itself.
        # Sources: the DOM verbatim page text, the executor's artifacts, and the
        # DOM-extracted observation text (aria-labels/hrefs not in innerText).
        full_page_text = await with_backoff(
            "browser",
            lambda: browser.read_text(None, 0, False, settings.max_page_text_chars),
            writer,
            settings,
        )
        sources = [full_page_text, state.get("step_artifacts", ""), state.get("observation", "")]
        valid_evidences: list = []
        rejected_preview: list[str] = []
        for evidence in result.evidences:
            if evidence_is_real(evidence.original_text, *sources):
                valid_evidences.append(evidence)
            else:
                # First 80 characters make the rejection debuggable in the hub log.
                rejected_preview.append(evidence.original_text[:80])
        evidence_failed = len(result.evidences) - len(valid_evidences)
        writer({"type": "evidence_check", "ok": len(valid_evidences), "failed": evidence_failed, "rejected": rejected_preview})

        verdict = result.verdict
        assessment = result.assessment
        if verdict == "done" and (evidence_failed or not valid_evidences):
            verdict = "retry"
            assessment = "Evidence not found verbatim on the page: " + assessment
        local_retries = state.get("local_retries", 0)
        plan = state["plan"]
        current_step = None
        if verdict == "done":
            plan = plan[1:]
            if plan:
                current_step = PROMPTS["executor"]["step"].format(instruction=plan[0]["instruction"], expected=plan[0]["expected_outcome"])
            local_retries = 0
        elif verdict == "retry":
            local_retries += 1
            current_step = PROMPTS["executor"]["step"].format(instruction=step["instruction"], expected=step["expected_outcome"])
            current_step += f"\nPrevious attempt was NOT complete: {assessment}. Do not repeat failed actions; use an alternate approach."

        record_shot = save_shot(state.get("run_id", "default"), snapshot.screenshot)
        counter = state.get("evidence_counter", 0)
        evidences = []
        for evidence in valid_evidences:
            counter += 1
            evidences.append({**evidence.model_dump(), "id": f"E{counter}", "shot": record_shot})
        record = {
            "instruction": step["instruction"],
            "expected_outcome": step["expected_outcome"],
            "complete": verdict == "done",
            "verdict": verdict,
            "assessment": assessment,
            "report": state["executor_report"],
            "evidences": evidences,
            "shot": record_shot,
            "url": snapshot.url,
        }
        writer({"type": "verified", **record})
        if verdict == "replan" or (verdict == "retry" and local_retries > settings.max_local_retries) or (verdict == "done" and not plan):
            reason = "replan" if verdict == "replan" else ("retries_exhausted" if verdict == "retry" else "plan_empty")
            writer({"type": "escalation", "reason": reason})
        update = {
            "history": [record],
            "browser_url": snapshot.url,
            "local_retries": local_retries,
            "evidence_counter": counter,
            "plan": plan,
        }
        if current_step:
            update["current_step"] = current_step
        return update

    async def reporter(state: AgentState, writer: StreamWriter) -> dict:
        prompts = PROMPTS["reporter"]
        history = state.get("history", [])
        verdicts = PROMPTS["planner"]
        evidences = [evidence for record in history for evidence in record["evidences"]]
        evidence_text = "\n".join(
            prompts["evidence_item"].format(
                id=evidence.get("id") or f"E{number}",
                url=evidence["url"],
                summarized=evidence["summarized"],
                original_text=evidence["original_text"],
            )
            for number, evidence in enumerate(evidences, 1)
        )
        plan_text = "\n".join(
            prompts["plan_item"].format(
                number=number,
                verdict=verdicts["verdict_complete"] if record["complete"] else verdicts["verdict_incomplete"],
                instruction=record["instruction"],
            )
            for number, record in enumerate(history, 1)
        )
        user = prompts["user"].format(
            goal=state["goal"],
            outcome=state["status"],
            assessment=state.get("final_assessment", ""),
            plan=plan_text,
            evidence=evidence_text or prompts["no_evidence"],
        )
        messages = [SystemMessage(prompts["system"]), HumanMessage(user)]

        async def write_report() -> str:
            writer({"type": "report_reset"})
            parts: list[str] = []
            async for chunk in models.reporter.astream(messages):
                parts.append(chunk.text)
                writer({"type": "report_chunk", "text": chunk.text})
            report = "".join(parts)
            if not report.strip():
                raise ValueError("the model returned an empty report")
            return report

        report = await with_backoff("reporter", write_report, writer, settings)
        directory = Path(settings.reports_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"report_{state['run_id']}.md"
        path.write_text(report, encoding="utf-8")
        writer({"type": "report_done", "path": str(path)})
        writer({"type": "finished", "status": state["status"], "path": str(path)})
        return {"report_path": str(path)}

    def route_after_verifier(state: AgentState) -> Literal["executor", "planner"]:
        last = state["history"][-1]
        if last["verdict"] == "retry" and state.get("local_retries", 0) <= settings.max_local_retries:
            return "executor"
        if last["verdict"] == "done" and state["plan"]:
            return "executor"
        return "planner"

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_node("verifier", verifier)
    graph.add_node("reporter", reporter)
    graph.add_edge(START, "planner")
    graph.add_edge("executor", "verifier")
    graph.add_conditional_edges("verifier", route_after_verifier)
    graph.add_edge("reporter", END)
    return graph.compile(checkpointer=checkpointer, name="agentic_browser")