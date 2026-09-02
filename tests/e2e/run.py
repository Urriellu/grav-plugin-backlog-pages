#!/usr/bin/env python3
"""End-to-end checks: boot a real Grav, serve the plugin, assert the HTML.

The plugin assembles all of its data in PHP and hands the templates arrays that
are already flattened, sorted and counted. That design is only worth anything if
the sorting and counting are right, and nothing but a running Grav can tell us
whether they are -- so this boots one and reads the markup that comes back.

It is also how the `compatibility:` block in blueprints.yaml earns its place.
Grav 1.7 runs Twig 1.44 and ships Quark; Grav 2.0 runs Twig 3 and ships Quark2.
Claiming both without rendering on both is a guess.

Usage:  run.py --grav /path/to/grav-install [--keep-server]

Assertions run against markup this plugin generates itself, so the regexes below
are reading a contract we control rather than parsing the web at large.
"""

from __future__ import annotations

import argparse
import http.client
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "pages"

# Files that belong to the repository but not to an installed plugin.
NOT_SHIPPED = shutil.ignore_patterns(".git", ".github", "tests", "*.pyc", "__pycache__")


class Failures:
    """Collects every failure so one run reports all of them, not just the first."""

    def __init__(self) -> None:
        self.items: list[str] = []
        self.checked = 0
        self.scenario = ""

    def check(self, what: str, got, want) -> None:
        self.checked += 1
        if got != want:
            self.items.append(f"[{self.scenario}] {what}\n     got:  {got!r}\n     want: {want!r}")

    def check_in(self, what: str, needle: str, haystack: str) -> None:
        self.checked += 1
        if needle not in haystack:
            self.items.append(f"[{self.scenario}] {what}\n     missing: {needle!r}")

    def check_not_in(self, what: str, needle: str, haystack: str) -> None:
        self.checked += 1
        if needle in haystack:
            self.items.append(f"[{self.scenario}] {what}\n     unexpectedly present: {needle!r}")


class Grav:
    """A Grav install with the plugin deployed into it, and a server in front."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.plugin = root / "user" / "plugins" / "backlog-pages"
        self.pages = root / "user" / "pages"
        self.config = root / "user" / "config" / "plugins" / "backlog-pages.yaml"
        self.log = root / "e2e-server.log"
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.last: tuple[str, int, str] = ("(none)", 0, "")

    # -- setup ------------------------------------------------------------

    def deploy_plugin(self) -> None:
        shutil.rmtree(self.plugin, ignore_errors=True)
        shutil.copytree(REPO, self.plugin, ignore=NOT_SHIPPED)

    def load_pages(self, namespace: str = "backlog") -> None:
        """Install the fixture backlog, optionally under a different front-matter key.

        Rewriting `backlog:` to something else is the only honest way to test the
        `namespace` setting: the point of that setting is that a site keeps its own
        conventions, so the pages have to actually use a different one.
        """
        for page in ("10.backlog", "11.plan", "12.who", "13.team", "14.bogus"):
            shutil.rmtree(self.pages / page, ignore_errors=True)
        shutil.copytree(FIXTURES, self.pages, dirs_exist_ok=True)

        if namespace != "backlog":
            rewritten_files = 0
            for md in self.pages.rglob("default.md"):
                text = md.read_text()
                # Tolerate trailing whitespace so a stray \r cannot silently turn
                # this into a no-op that only shows up as a missing backlog.
                rewritten = re.sub(r"^backlog:[ \t\r]*$", f"{namespace}:", text, flags=re.M)
                if rewritten != text:
                    md.write_text(rewritten)
                    rewritten_files += 1
            if not rewritten_files:
                sys.exit("namespace rewrite changed nothing -- the fixtures are not what "
                         "this expects, so every later check would be meaningless")

    def configure(self, **settings) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        if not settings:
            self.config.unlink(missing_ok=True)
        else:
            body = "".join(
                f"{k}: {'true' if v is True else 'false' if v is False else v}\n"
                for k, v in settings.items()
            )
            self.config.write_text(body)
        self.clear_cache()

    def clear_cache(self) -> None:
        """Empty Grav's cache, and be sure it is actually empty.

        Every scenario changes configuration or pages under a server that is
        already running, so a cache that quietly refused to clear would serve
        the previous scenario's site and the failure would land somewhere else
        entirely -- which is exactly the kind of bug that gets blamed on the
        plugin. Swallowing errors here is how that stays hidden.
        """
        cache = self.root / "cache"
        for attempt in range(3):
            for child in cache.glob("*"):
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=attempt < 2)
                else:
                    child.unlink(missing_ok=True)
            leftover = list(cache.glob("*"))
            if not leftover:
                return
        sys.exit(f"could not empty {cache}; still holds {[p.name for p in leftover]}")

    # -- server -----------------------------------------------------------

    def start(self) -> None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.log.write_text("")
        self.proc = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{self.port}", "system/router.php"],
            cwd=self.root,
            stdout=self.log.open("a"),
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.proc.poll() is not None:
                sys.exit(f"php -S died on startup:\n{self.log.read_text()}")
            try:
                self.get("/")
                return
            except (OSError, http.client.HTTPException):
                time.sleep(0.2)
        sys.exit(f"php -S never became ready:\n{self.log.read_text()}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)

    def get(self, route: str) -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request("GET", route)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", "replace")
            self.last = (route, resp.status, body)
            return resp.status, body
        finally:
            conn.close()

    def state_report(self) -> str:
        """What the site actually looked like, for when a failure makes no sense.

        Every check here runs against a site this script just assembled, so a
        surprising result is as likely to be a broken setup as a broken plugin.
        """
        lines = ["", "--- state at the end of the run ---"]
        cfg = self.config.read_text() if self.config.exists() else "(no user config)"
        lines.append(f"user/config/plugins/backlog-pages.yaml:\n{cfg.rstrip()}")

        view = self.pages / "11.plan" / "default.md"
        head = "".join(view.read_text().splitlines(keepends=True)[:6]) if view.exists() else "(absent)"
        lines.append(f"user/pages/11.plan/default.md:\n{head.rstrip()}")

        installed = self.plugin / "backlog-pages.php"
        lines.append(f"plugin deployed: {installed.exists()}")
        lines.append(f"pages present: {sorted(p.name for p in self.pages.iterdir())}")

        route, status, body = getattr(self, "last", ("(none)", 0, ""))
        lines.append(f"last request: {route} -> {status}, "
                     f"{'has' if 'backlog-toolbar' in body else 'no'} toolbar, "
                     f"{body.count('data-story')} story rows")
        return "\n".join(lines)

    def php_complaints(self) -> list[str]:
        """PHP notices/warnings the server emitted. A clean plugin emits none."""
        pattern = re.compile(r"(PHP )?(Warning|Deprecated|Notice|Fatal error|Parse error):.*")
        return sorted({m.group(0) for m in pattern.finditer(self.log.read_text())})


# -- reading our own markup back ------------------------------------------

KEY = re.compile(r'class="backlog-key">([^<]*)<')


def epic_blocks(html: str) -> list[str]:
    return html.split('<details class="backlog-epic"')[1:]


def epics(html: str) -> list[dict]:
    out = []
    for block in epic_blocks(html):
        summary = block.split("</summary>")[0]
        percent = re.search(r'<i style="width:(\d+)%', summary)
        counts = re.search(r"(\d+) of (\d+) closed", summary)
        out.append(
            {
                "key": KEY.search(summary).group(1),
                "percent": int(percent.group(1)) if percent else None,
                "closed": int(counts.group(1)) if counts else None,
                "total": int(counts.group(2)) if counts else None,
                "stories": [KEY.search(s).group(1) for s in story_divs(block)],
            }
        )
    return out


# A story row ends where the next one begins, or where the epic's own trailing
# markup starts. Matching the closing </div> instead would need a real parser,
# because the row contains nested spans.
STORY = re.compile(
    r'<div class="backlog-story\b'
    r'.*?(?=<div class="backlog-story|<p class="backlog-empty"|</details>)',
    re.S,
)


def story_divs(html: str) -> list[str]:
    return STORY.findall(html)


def story_attrs(html: str) -> dict[str, dict]:
    """Every story row on the page, keyed by its backlog key."""
    out = {}
    for chunk in story_divs(html):
        key = KEY.search(chunk).group(1)
        out[key] = {
            "status": attr(chunk, "data-status"),
            "closed": attr(chunk, "data-closed"),
            "labels": attr(chunk, "data-labels"),
            "chunk": chunk,
        }
    return out


def attr(html: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', html)
    return m.group(1) if m else None


def person_rows(html: str) -> list[tuple[str, str]]:
    """(rank, key) for each row of the priority-by-person list, in document order."""
    return re.findall(
        r'<span class="backlog-rank">([^<]*)</span>\s*<span class="backlog-key">([^<]*)</span>', html
    )


def options(html: str, select_name: str) -> list[str]:
    block = re.search(rf'<select name="{select_name}".*?</select>', html, re.S)
    return re.findall(r'<option value="([^"]*)"', block.group(0)) if block else []


# -- the scenarios --------------------------------------------------------


def scenario_default(g: Grav, f: Failures) -> None:
    """The whole feature, on a backlog whose folder order disagrees with its ranks."""
    f.scenario = "default"
    g.load_pages()
    g.configure()

    status, plan = g.get("/plan")
    f.check("/plan status", status, 200)

    got = epics(plan)
    # E-02 ranks 5 and E-01 ranks 10, but the folders are 01.epic-alpha (E-01)
    # and 02.epic-beta (E-02). Rank has to win, or the view is just a file listing.
    f.check("epic order is by rank, not folder", [e["key"] for e in got], ["E-02", "E-01"])
    f.check("E-02 stories in rank order", got[0]["stories"], ["S-201", "S-202"])
    # S-100 and S-101 both rank 40; the README promises the key breaks the tie.
    f.check("E-01 stories in rank order, ties by key", got[1]["stories"],
            ["S-102", "S-103", "S-100", "S-101"])
    f.check("E-02 closed/total", (got[0]["closed"], got[0]["total"]), (1, 2))
    f.check("E-01 closed/total", (got[1]["closed"], got[1]["total"]), (1, 4))
    f.check("E-02 progress percent", got[0]["percent"], 50)
    f.check("E-01 progress percent", got[1]["percent"], 25)

    rows = story_attrs(plan)
    f.check("every story rendered once", sorted(rows), ["S-100", "S-101", "S-102", "S-103", "S-201", "S-202"])
    f.check("in-progress story status attribute", rows["S-103"]["status"], "in-progress")
    f.check("in-progress story is not closed", rows["S-103"]["closed"], "0")
    f.check("labels are pipe-delimited for the filter", rows["S-103"]["labels"], "|hardware|software|")
    f.check("done counts as closed", rows["S-102"]["closed"], "1")
    f.check("cancelled counts as closed", rows["S-202"]["closed"], "1")
    f.check_in("depends_on renders", "after S-102", rows["S-103"]["chunk"])
    f.check_in("traces_to renders", "ADR-0001", rows["S-103"]["chunk"])
    f.check_in("owner renders", "alex", rows["S-103"]["chunk"])

    # A child of the backlog without doc_type: epic, and a child of an epic
    # without doc_type: story, are ordinary pages and must stay out of the view.
    f.check("non-epic child excluded", [e for e in got if "Just a page" in str(e)], [])
    f.check("non-story child excluded",
            [k for k, v in rows.items() if "Just a sub-page" in v["chunk"]], [])

    f.check("label filter lists every label, sorted", options(plan, "label"),
            ["", "hardware", "research", "software"])
    f.check("status filter lists every status", options(plan, "status"),
            ["", "to-do", "in-progress", "done", "cancelled"])
    f.check_in("page body still renders above the view",
               "Body text of the hierarchy view page.", plan)

    status, who = g.get("/who")
    f.check("/who status", status, 200)
    # Open stories only, in one global rank order that ignores epic boundaries.
    f.check("person view: open stories in global rank order", person_rows(who),
            [("20", "S-201"), ("30", "S-103"), ("40", "S-100"), ("40", "S-101")])
    f.check("person view excludes closed stories",
            [k for _, k in person_rows(who) if k in ("S-102", "S-202")], [])
    f.check("roster read from the team page's front matter",
            re.findall(r'value="([^"]*)"\s*data-can="([^"]*)"', who),
            [("alex", "|software|hardware|"), ("sam", "|research|"), ("nobody", "||")])

    # A view name the plugin does not implement must fall through to an ordinary
    # page rather than 500 on a template that is not there.
    status, bogus = g.get("/bogus")
    f.check("unknown view name still returns 200", status, 200)
    f.check_not_in("unknown view name renders no toolbar", "backlog-toolbar", bogus)
    f.check_in("unknown view name renders the page body",
               "Body text of a page asking for a view that does not exist.", bogus)

    status, container = g.get("/backlog")
    f.check("the backlog container is an ordinary page", status, 200)
    f.check_not_in("the backlog container renders no view", "backlog-toolbar", container)


def scenario_disabled(g: Grav, f: Failures) -> None:
    """The headline promise: switching the plugin off degrades, it does not break."""
    f.scenario = "plugin disabled"
    g.load_pages()
    g.configure(enabled=False)

    for route, body in (("/plan", "Body text of the hierarchy view page."),
                        ("/who", "Body text of the person view page.")):
        status, html = g.get(route)
        f.check(f"{route} still returns 200 with the plugin off", status, 200)
        f.check_not_in(f"{route} renders no view with the plugin off", "backlog-toolbar", html)
        f.check_in(f"{route} falls back to its own body text", body, html)


def scenario_namespace(g: Grav, f: Failures) -> None:
    """A site that already uses its own front-matter key should not have to move."""
    f.scenario = "namespace: work"
    g.load_pages(namespace="work")
    g.configure(namespace="work")

    status, plan = g.get("/plan")
    f.check("/plan status under a renamed namespace", status, 200)
    f.check("epics still found and ordered", [e["key"] for e in epics(plan)], ["E-02", "E-01"])
    status, who = g.get("/who")
    f.check("roster still found", [k for _, k in person_rows(who)],
            ["S-201", "S-103", "S-100", "S-101"])

    # The namespace is global: pages left on `backlog:` must now be invisible,
    # which is what makes the setting a rename rather than an alias.
    f.scenario = "namespace mismatch"
    g.load_pages(namespace="backlog")
    g.configure(namespace="work")
    status, plan = g.get("/plan")
    f.check("mismatched namespace does not error", status, 200)
    f.check_not_in("mismatched namespace renders no view", "backlog-toolbar", plan)


def scenario_missing_routes(g: Grav, f: Failures) -> None:
    """Empty states have to name the route that was actually looked at."""
    f.scenario = "routes point nowhere"
    g.load_pages()

    g.configure(backlog_route="/does-not-exist")
    status, plan = g.get("/plan")
    f.check("missing backlog route does not error", status, 200)
    f.check_in("empty state names the configured route, not the default",
               "No epics found under <code>/does-not-exist</code>", plan)
    f.check_not_in("empty state does not name the default route",
                   "No epics found under <code>/backlog</code>", plan)

    g.configure(roster_route="/no-team")
    status, who = g.get("/who")
    f.check("missing roster route does not error", status, 200)
    f.check_in("roster empty state appears", "No roster found", who)
    f.check_in("roster empty state links the configured route", 'href="/no-team"', who)


def scenario_hide_closed(g: Grav, f: Failures) -> None:
    """The toggle's default is a setting, and the checkbox has to reflect it."""
    f.scenario = "hide_closed_by_default"
    g.load_pages()

    g.configure(hide_closed_by_default=True)
    _, plan = g.get("/plan")
    box = re.search(r'<input type="checkbox" name="closed"[^>]*>', plan).group(0)
    f.check("hiding closed by default leaves the box unchecked", "checked" in box, False)

    g.configure(hide_closed_by_default=False)
    _, plan = g.get("/plan")
    box = re.search(r'<input type="checkbox" name="closed"[^>]*>', plan).group(0)
    f.check("showing closed by default ticks the box", "checked" in box, True)


SCENARIOS = [
    scenario_default,
    scenario_disabled,
    scenario_namespace,
    scenario_missing_routes,
    scenario_hide_closed,
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grav", required=True, type=Path, help="root of a Grav install")
    ap.add_argument("--keep-server", action="store_true", help="leave php -S running afterwards")
    ap.add_argument("--serve", action="store_true",
                    help="deploy the fixtures and serve them in the foreground, without asserting "
                         "anything -- this is how the browser tests get a site to drive")
    ap.add_argument("--port", type=int, default=8765, help="port for --serve")
    args = ap.parse_args()

    if not (args.grav / "system" / "router.php").is_file():
        sys.exit(f"{args.grav} does not look like a Grav install")

    version = "unknown"
    defines = (args.grav / "system" / "defines.php").read_text()
    # 1.7 writes the define with single quotes, 2.0 with double.
    m = re.search(r"""GRAV_VERSION["'],\s*["']([^"']+)["']""", defines)
    if m:
        version = m.group(1)

    g = Grav(args.grav)
    g.deploy_plugin()

    if args.serve:
        # The browser tests need the same site these checks build, so they get it
        # from the same code rather than a second, drifting copy of the setup.
        g.load_pages()
        g.configure()
        print(f"Grav {version} serving {args.grav} on 127.0.0.1:{args.port}", flush=True)
        os.chdir(args.grav)
        os.execvp("php", ["php", "-S", f"127.0.0.1:{args.port}", "system/router.php"])

    f = Failures()

    print(f"Grav {version} on PHP {subprocess.run(['php', '-r', 'echo PHP_VERSION;'], capture_output=True, text=True).stdout}")
    g.start()
    print(f"serving {args.grav} on 127.0.0.1:{g.port}\n")
    try:
        for scenario in SCENARIOS:
            g.clear_cache()
            scenario(g, f)
            print(f"  ran {scenario.__name__}")
    finally:
        if not args.keep_server:
            g.stop()

    complaints = g.php_complaints()
    for c in complaints:
        f.items.append(f"[php] server emitted a diagnostic\n     {c}")
    f.checked += 1

    print()
    if f.items:
        print(f"FAILED — {len(f.items)} of {f.checked} checks, Grav {version}\n")
        for item in f.items:
            print(f"  {item}\n")
        print(g.state_report())
        return 1
    print(f"OK — {f.checked} checks passed against Grav {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
