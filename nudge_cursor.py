#!/usr/bin/env python3
"""Injects a synthetic mouse-move into Chromium via CDP so it re-runs its
cursor hit-test and hides the pointer per the page's `cursor: none` CSS.

A real hardware mouse move does this naturally, but on boot no such event
has ever fired, so the pointer stays visible until you physically touch
the mouse once. Wayland virtual-pointer tools (wlrctl/ydotool) move the
compositor's own cursor sprite but don't necessarily deliver the same
enter/motion sequence to Chromium's surface, so they don't reliably
trigger this. Dispatching the event straight into Blink via CDP -- the
same mechanism Puppeteer/Playwright use -- goes through the real input
pipeline and does trigger it.
"""
import json
import sys
import time
import urllib.request

import websocket

CDP_PORT = 9222


def get_page_target(timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json") as r:
                targets = json.loads(r.read())
            for t in targets:
                if t.get("type") == "page":
                    return t
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Timed out waiting for a Chromium page target on CDP")


def main():
    target = get_page_target()
    ws = websocket.create_connection(target["webSocketDebuggerUrl"])

    call_id = [0]

    def send(method, params=None):
        call_id[0] += 1
        ws.send(json.dumps({"id": call_id[0], "method": method, "params": params or {}}))
        return json.loads(ws.recv())

    deadline = time.time() + 15
    while time.time() < deadline:
        result = send("Runtime.evaluate", {"expression": "document.readyState"})
        if result.get("result", {}).get("result", {}).get("value") == "complete":
            break
        time.sleep(0.3)

    for x in (400, 500, 600, 500):
        send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": 300, "button": "none",
        })
        time.sleep(0.3)
    ws.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"nudge_cursor.py: {e}", file=sys.stderr)
        sys.exit(1)
