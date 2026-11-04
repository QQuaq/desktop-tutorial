"""Chrome'u bulma, baslatma ve DevTools hedefine baglanma."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from .cdp import CDP, CDPError

WINDOWS_PATHS = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
)
MAC_PATHS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",)
NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")


def find_chrome(configured: str = "") -> str | None:
    if configured:
        return configured if shutil.which(configured) or os.path.isfile(configured) else None
    for name in NAMES:
        found = shutil.which(name)
        if found:
            return found
    system = platform.system()
    candidates = WINDOWS_PATHS if system == "Windows" else MAC_PATHS if system == "Darwin" else ()
    for pattern in candidates:
        path = os.path.expandvars(pattern)
        if os.path.isfile(path):
            return path
    return None


def build_args(chrome: str, profile_dir: str, headless: bool, width: int, height: int, start_url: str) -> list[str]:
    args = [
        chrome,
        "--remote-debugging-port=0",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
        "--disable-extensions",
    ]
    if headless:
        args.append("--headless=new")
    if platform.system() == "Linux" and (os.geteuid() == 0 or os.environ.get("PS5CHROME_NO_SANDBOX")):
        args.append("--no-sandbox")
    args.append(start_url)
    return args


class ChromeInstance:
    def __init__(self, chrome: str, width: int = 1280, height: int = 720,
                 headless: bool = True, start_url: str = "about:blank") -> None:
        self.width, self.height = width, height
        self.profile = tempfile.mkdtemp(prefix="ps5chrome-")
        self.proc = subprocess.Popen(
            build_args(chrome, self.profile, headless, width, height, start_url),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.port = self._wait_port()
        self.cdp = self._connect()

    def _wait_port(self, timeout: float = 20.0) -> int:
        path = Path(self.profile) / "DevToolsActivePort"
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                raise CDPError("Chrome beklenmedik sekilde kapandi")
            if path.exists():
                lines = path.read_text().splitlines()
                if lines and lines[0].isdigit():
                    return int(lines[0])
            time.sleep(0.1)
        raise CDPError("Chrome DevTools portu acilmadi")

    def targets(self) -> list[dict]:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=5) as r:
            return json.loads(r.read())

    def _connect(self) -> CDP:
        end = time.time() + 10
        while time.time() < end:
            pages = [t for t in self.targets() if t.get("type") == "page"]
            if pages:
                return CDP(pages[0]["webSocketDebuggerUrl"])
            time.sleep(0.2)
        raise CDPError("sayfa hedefi bulunamadi")

    def page_info(self) -> dict:
        pages = [t for t in self.targets() if t.get("type") == "page"]
        return {"url": pages[0].get("url", ""), "title": pages[0].get("title", "")} if pages else {}

    def close(self) -> None:
        try:
            self.cdp.close()
        except OSError:
            pass
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)
