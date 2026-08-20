"""Schema for the generic `computer_use` tool.

Model-agnostic. Any tool-calling model can drive this. The default capture
mode is `som` (screenshot + numbered element overlays): the model SEES the
screen and clicks elements by their visible index — much more reliable than
pixel coordinates, and essential on Windows/Linux where the accessibility
tree is often incomplete. `ax` (tree only, no screenshot) is an opt-in fast
path for apps with a known-good AX tree. Pixel coordinates remain supported
for models that were trained on them (e.g. Claude's computer-use RL).
"""

from __future__ import annotations

from typing import Any, Dict


# One consolidated tool with an `action` discriminator. Keeps the schema
# compact and the per-turn token cost low.
COMPUTER_USE_SCHEMA: Dict[str, Any] = {
    "name": "computer_use",
    "description": (
        "Drive the desktop in the background via cua-driver — screenshots, "
        "mouse, keyboard, scroll, drag — without stealing the user's cursor "
        "or keyboard focus. Supported on macOS, Windows, and Linux. "
        "Preferred workflow: call with "
        "action='capture' (mode='som' gives numbered element overlays), "
        "then click by `element` index for reliability. Pixel coordinates "
        "are supported for models trained on them. Image captures include a "
        "shareable `screenshot_path`; when the user asks to receive the image "
        "and the current surface supports attachments, deliver that file using "
        "the platform's native MEDIA attachment syntax. Do not automatically "
        "send screenshots used only for computer control. Works on any window — "
        "hidden, minimized, or behind another app. Requires cua-driver to "
        "be installed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "capture",
                    "click",
                    "double_click",
                    "right_click",
                    "middle_click",
                    "drag",
                    "scroll",
                    "page",
                    "type",
                    "key",
                    "set_value",
                    "wait",
                    "list_apps",
                    "list_windows",
                    "open_app",
                    "focus_app",
                    "focus_window",
                    "minimize",
                ],
                "description": (
                    "Which action to perform. `capture`, `list_apps`, "
                    "`list_windows`, `wait` are free (read-only). All other "
                    "actions require approval unless auto-approved. "
                    "`list_windows` enumerates ALL top-level windows (incl. "
                    "minimized) — call it first when multiple windows are "
                    "open or a window may be minimized. `open_app` launches "
                    "an application (optionally with a `url`) and returns its "
                    "pid + windows — ALWAYS prefer it over double-clicking "
                    "desktop icons or shelling out; for browsers it adds the "
                    "flags that enable the page tree and action='page'. "
                    "`focus_window` "
                    "restores/activates a window (by pid+window_id from "
                    "list_windows, or app=) so it can be captured and "
                    "controlled; `minimize` minimizes the target window. "
                    "Use `set_value` for select/popup elements and sliders — "
                    "it selects the matching option directly without opening "
                    "the native menu (no focus steal). `page` talks to the "
                    "BROWSER PAGE itself (Chrome/Edge/Brave/Safari/Electron): "
                    "see `page_action` — the preferred way to scroll and read "
                    "feeds/long pages, with exact scroll metrics back."
                ),
            },
            # ── capture ────────────────────────────────────────────
            "mode": {
                "type": "string",
                "enum": ["som", "vision", "ax"],
                "description": (
                    "Capture mode. `som` (DEFAULT) is a screenshot with "
                    "numbered overlays on every interactable element plus the "
                    "AX tree — you SEE the screen and click the numbered "
                    "element you want; the most reliable path on every "
                    "platform, and the only dependable one on Windows/Linux "
                    "where the AX tree is often incomplete. `ax` is the "
                    "accessibility tree only — NO screenshot, fast and cheap; "
                    "use it as a speed optimization for apps with a known-good "
                    "AX tree (browsers, native apps, IDEs) once you've "
                    "confirmed the elements are well-labeled. `vision` is a "
                    "plain screenshot (no overlays)."
                ),
            },
            "app": {
                "type": "string",
                "description": (
                    "Optional. Limit capture/action to a specific app "
                    "(by name, e.g. 'Safari', or bundle ID, "
                    "'com.apple.Safari'). If omitted, operates on the "
                    "frontmost app's window. Pass app='screen' (or "
                    "'desktop') to capture the OS desktop/shell surface — "
                    "e.g. to see the wallpaper or click the taskbar. Note: "
                    "capture is per-window; a single image cannot span "
                    "multiple monitors, so on a multi-screen setup capture "
                    "one window or display at a time."
                ),
            },
            "max_elements": {
                "type": "integer",
                "description": (
                    "Optional cap on the AX `elements` array returned by "
                    "`action='capture'`. Default 100, hard maximum 1000. "
                    "Dense UIs (Electron apps such as Obsidian or VS Code, "
                    "JetBrains IDEs) can publish 500+ AX nodes — capping "
                    "prevents a single capture from blowing session "
                    "context. When the cap trims the response, "
                    "`total_elements` and `truncated_elements` are "
                    "surfaced in the result so you can re-call with "
                    "`app=` to narrow scope or raise `max_elements` when "
                    "the full tree is required. Has no effect on "
                    "`mode='som'` / `mode='vision'` when a screenshot is "
                    "included in the response; only the rare image-"
                    "missing fallback returns an `elements` array and is "
                    "subject to the cap."
                ),
                "default": 100,
                "minimum": 1,
                "maximum": 1000,
            },
            # ── click / drag / scroll targeting ────────────────────
            "element": {
                "type": "integer",
                "description": (
                    "The 1-based SOM index returned by the last "
                    "`capture(mode='som')` call. Strongly preferred over "
                    "raw coordinates."
                ),
            },
            "coordinate": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
                "description": (
                    "Pixel coordinates [x, y] in logical screen space (as "
                    "returned by capture width/height). Only use this if "
                    "no element index is available."
                ),
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "description": "Mouse button. Defaults to left.",
            },
            "modifiers": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "cmd", "shift", "option", "alt", "ctrl", "fn",
                        "win", "windows", "super", "meta",
                    ],
                },
                "description": "Modifier keys held during the action.",
            },
            # ── drag ───────────────────────────────────────────────
            "from_element": {"type": "integer",
                              "description": "Source element index (drag)."},
            "to_element": {"type": "integer",
                            "description": "Target element index (drag)."},
            "from_coordinate": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2, "maxItems": 2,
                "description": "Source [x,y] (drag; use when no element available).",
            },
            "to_coordinate": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2, "maxItems": 2,
                "description": "Target [x,y] (drag; use when no element available).",
            },
            # ── scroll ─────────────────────────────────────────────
            "direction": {
                "type": "string",
                "enum": ["up", "down", "left", "right"],
                "description": "Scroll direction.",
            },
            "amount": {
                "type": "integer",
                "description": (
                    "Scroll wheel ticks (or pages when by='page'). Default 3."
                ),
            },
            "by": {
                "type": "string",
                "enum": ["line", "page"],
                "description": (
                    "Scroll unit for action='scroll'. Default 'line' (wheel "
                    "ticks); 'page' scrolls a full viewport per `amount` — "
                    "use it to traverse long forms/pages in fewer calls."
                ),
            },
            # ── page (browser) ─────────────────────────────────────
            "page_action": {
                "type": "string",
                "enum": ["scroll", "read", "query", "click", "js"],
                "description": (
                    "For action='page' — talk to the browser page in the "
                    "captured window directly. `scroll`: scroll the page (or "
                    "a `selector` container) by `amount_px` (default ~one "
                    "viewport) or to='top'/'bottom'; returns exact metrics "
                    "(scrolled_px, scroll_height, at_bottom, "
                    "content_below_px) so you always know whether more "
                    "content exists. `read`: extract the page's visible text "
                    "— read feeds/articles WITHOUT screenshots. `query`: "
                    "find elements by CSS `selector` (with `attributes`). "
                    "`click`: click the element matching `selector`. `js`: "
                    "run `javascript` and return its result. Needs a "
                    "browser; Chromium on Windows/Linux needs "
                    "--remote-debugging-port for scroll/click/js."
                ),
            },
            "selector": {
                "type": "string",
                "description": (
                    "CSS selector for page_action='query'/'click', or the "
                    "scroll container for page_action='scroll' (omit to "
                    "scroll the page itself)."
                ),
            },
            "javascript": {
                "type": "string",
                "description": "JavaScript to run for page_action='js'.",
            },
            "amount_px": {
                "type": "integer",
                "description": (
                    "Pixels to scroll for page_action='scroll'. Default: "
                    "~80% of the viewport height."
                ),
            },
            "to": {
                "type": "string",
                "enum": ["top", "bottom"],
                "description": (
                    "For page_action='scroll': jump straight to the top or "
                    "bottom instead of scrolling by amount_px."
                ),
            },
            "attributes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Element attributes to include in page_action='query' "
                    "results (e.g. ['href', 'aria-label'])."
                ),
            },
            "max_chars": {
                "type": "integer",
                "description": (
                    "Cap on text returned by page_action='read'/'query'/'js'. "
                    "Default 10000."
                ),
            },
            # ── set_value ──────────────────────────────────────────
            "value": {
                "type": "string",
                "description": (
                    "For action='set_value': the value to set on the element. "
                    "For AXPopUpButton / select dropdowns, pass the option's "
                    "display label (e.g. 'Blue'). For sliders and other "
                    "AXValue-settable elements, pass the numeric or string value."
                ),
            },
            # ── type / key / wait ──────────────────────────────────
            "text": {
                "type": "string",
                "description": "Text to type (respects the current layout).",
            },
            "keys": {
                "type": "string",
                "description": (
                    "Key combo, e.g. 'cmd+s', 'ctrl+alt+t', 'return', "
                    "'escape', 'tab'. Use '+' to combine."
                ),
            },
            "seconds": {
                "type": "number",
                "description": "Seconds to wait. Max 30.",
            },
            # ── open_app ───────────────────────────────────────────
            "url": {
                "type": "string",
                "description": (
                    "For action='open_app': URL(s) to open in the launched "
                    "app (e.g. a page for a browser)."
                ),
            },
            "browser_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "For action='open_app': extra command-line arguments. "
                    "Chromium-family browsers automatically get "
                    "--remote-debugging-port / --force-renderer-accessibility "
                    "(so captures see the page tree and action='page' works); "
                    "pass e.g. ['--profile-directory=Profile 1'] to pick a "
                    "browser profile."
                ),
            },
            "new_instance": {
                "type": "boolean",
                "description": (
                    "For action='open_app': force a NEW app instance even if "
                    "one is already running. Launch flags (e.g. the browser "
                    "automation flags) only apply to a fresh process — if the "
                    "app is already running without them, close it or set "
                    "this."
                ),
            },
            # ── focus_app ──────────────────────────────────────────
            "raise_window": {
                "type": "boolean",
                "description": (
                    "Only for action='focus_app'. If true, brings the "
                    "window to front (DISRUPTS the user). Default false "
                    "— input is routed to the app without raising, "
                    "matching the background co-work model."
                ),
            },
            "pid": {
                "type": "integer",
                "description": (
                    "Process id of a target window, as returned by "
                    "action='list_windows'. Used with `window_id` for "
                    "focus_window / minimize. Optional — omit to use the "
                    "active window (or pass `app`)."
                ),
            },
            "window_id": {
                "type": "integer",
                "description": (
                    "Window id of a target window, from action='list_windows'. "
                    "Used with `pid` for focus_window / minimize."
                ),
            },
            # ── return shape ───────────────────────────────────────
            "capture_after": {
                "type": "boolean",
                "description": (
                    "If true, take a follow-up capture after the action "
                    "and include it in the response. Saves a round-trip "
                    "when you need to verify an action's effect. The "
                    "follow-up uses the fast AX tree by default (no "
                    "screenshot) — see `capture_after_mode`."
                ),
            },
            "capture_after_mode": {
                "type": "string",
                "enum": ["som", "vision", "ax"],
                "description": (
                    "Mode for the `capture_after` follow-up. Defaults to "
                    "`ax` (fast, no screenshot) — enough to confirm most "
                    "state changes. Set to `som`/`vision` only when you need "
                    "to VISUALLY verify the result."
                ),
            },
        },
        "required": ["action"],
    },
}


def get_computer_use_schema() -> Dict[str, Any]:
    """Return the generic OpenAI function-calling schema."""
    return COMPUTER_USE_SCHEMA
