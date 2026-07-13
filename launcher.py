"""Friendly Windows launcher for the bundled Local PDF Toolbox."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import Button, Label, Tk, messagebox

from pdf_toolbox.config import (
    APP_ID,
    APP_NAME,
    APP_VERSION,
    LOOPBACK_HOST,
    LauncherConfig,
    load_launcher_config,
    resource_path,
    user_data_dir,
)
from pdf_toolbox.updater import (
    UpdateError,
    UpdateInfo,
    check_for_update,
    cleanup_downloaded_installers,
    download_installer,
    has_valid_authenticode_signature,
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """A per-user Windows mutex that prevents duplicate servers."""

    def __init__(self) -> None:
        self.handle: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        self.handle = kernel32.CreateMutexW(None, False, f"Local\\{APP_ID}")
        return bool(self.handle) and kernel32.GetLastError() != ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self.handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle(self.handle)  # type: ignore[attr-defined]
            self.handle = None


def find_available_port() -> int:
    """Reserve a loopback-selected port number for immediate server startup."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK_HOST, 0))
        return int(sock.getsockname()[1])


def server_command(port: int) -> list[str]:
    """Build a command that works in source and PyInstaller modes."""

    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-server", "--port", str(port)]
    return [sys.executable, str(Path(__file__).resolve()), "--run-server", "--port", str(port)]


def run_streamlit_server(port: int) -> int:
    """Run the blocking local Streamlit service in the launcher child process."""

    log_path = user_data_dir() / "launcher.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")

    try:
        from streamlit import config as streamlit_config
        from streamlit.web import bootstrap

        app_path = resource_path("app.py")
        options = {
            "global_developmentMode": False,
            "server_address": LOOPBACK_HOST,
            "server_port": port,
            "server_headless": True,
            "server_fileWatcherType": "none",
            "server_runOnSave": False,
            "browser_gatherUsageStats": False,
        }
        log(f"Starting server for {app_path} on {LOOPBACK_HOST}:{port}")
        bootstrap.load_config_options(options)
        log(
            "Config loaded: "
            f"address={streamlit_config.get_option('server.address')} "
            f"port={streamlit_config.get_option('server.port')}"
        )
        bootstrap.run(str(app_path), False, [], options)
        log("Server stopped normally")
        return 0
    except BaseException:
        log(traceback.format_exc())
        raise


class LauncherWindow:
    """Own the local service and present simple controls to non-technical users."""

    def __init__(self, instance: SingleInstance) -> None:
        self.instance = instance
        self.config: LauncherConfig = load_launcher_config()
        self.port = find_available_port()
        self.url = f"http://{LOOPBACK_HOST}:{self.port}"
        self.process: subprocess.Popen[bytes] | None = None
        self.closing = False
        self.data_dir = user_data_dir()
        self.runtime_path = self.data_dir / "runtime.json"
        self.update_state_path = self.data_dir / "update-state.json"

        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("430x220")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        Label(self.root, text=APP_NAME, font=("Segoe UI", 17, "bold")).pack(pady=(22, 4))
        self.status = Label(self.root, text="正在啟動本機服務...", font=("Segoe UI", 10))
        self.status.pack(pady=(0, 16))

        self.open_button = Button(
            self.root,
            text="開啟 PDF 工具箱",
            command=self.open_browser,
            state="disabled",
            width=24,
        )
        self.open_button.pack(pady=3)
        self.update_button = Button(
            self.root, text="檢查更新", command=self.check_updates_manually, width=24
        )
        self.update_button.pack(pady=3)
        Button(self.root, text="結束工具", command=self.shutdown, width=24).pack(pady=3)
        Label(self.root, text=f"版本 {APP_VERSION}", fg="#666666").pack(pady=(10, 0))

    def run(self) -> int:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        cleanup_downloaded_installers()
        threading.Thread(target=self._start_server, daemon=True).start()
        self.root.mainloop()
        return 0

    def _start_server(self) -> None:
        try:
            self.process = subprocess.Popen(
                server_command(self.port),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            deadline = time.monotonic() + 30
            health_url = f"{self.url}/_stcore/health"
            while time.monotonic() < deadline and not self.closing:
                if self.process.poll() is not None:
                    raise RuntimeError("本機服務提前結束。")
                try:
                    with urllib.request.urlopen(health_url, timeout=0.5) as response:
                        if response.status == 200:
                            self.root.after(0, self._server_ready)
                            return
                except Exception:
                    time.sleep(0.2)
            if not self.closing:
                raise RuntimeError("本機服務啟動逾時。")
        except Exception as exc:
            if not self.closing:
                detail = str(exc)
                self.root.after(0, lambda: self._server_failed(detail))

    def _server_ready(self) -> None:
        if self.closing or not self.process:
            return
        self.runtime_path.write_text(
            json.dumps({"url": self.url, "pid": self.process.pid}), encoding="utf-8"
        )
        self.status.config(text="工具已準備完成，可在瀏覽器中使用。")
        self.open_button.config(state="normal")
        self.open_browser()
        self.root.after(1200, self._check_updates_automatically)

    def _server_failed(self, detail: str) -> None:
        self.status.config(text="工具啟動失敗。")
        messagebox.showerror(APP_NAME, f"無法啟動 PDF 工具箱。\n\n{detail}")

    def open_browser(self) -> None:
        webbrowser.open(self.url, new=2)

    def _checked_today(self) -> bool:
        try:
            state = json.loads(self.update_state_path.read_text(encoding="utf-8"))
            return state.get("last_check") == date.today().isoformat()
        except (OSError, ValueError, TypeError):
            return False

    def _record_check(self) -> None:
        self.update_state_path.write_text(
            json.dumps({"last_check": date.today().isoformat()}), encoding="utf-8"
        )

    def _check_updates_automatically(self) -> None:
        if self.config.update_feed_url and not self._checked_today():
            self._start_update_check(show_no_update=False)

    def check_updates_manually(self) -> None:
        if not self.config.update_feed_url:
            messagebox.showinfo(APP_NAME, "此版本尚未設定更新來源。")
            return
        self._start_update_check(show_no_update=True)

    def _start_update_check(self, *, show_no_update: bool) -> None:
        self.update_button.config(state="disabled")
        self.status.config(text="正在檢查更新...")

        def worker() -> None:
            try:
                update = check_for_update(self.config.update_feed_url)
                self._record_check()
                self.root.after(0, lambda: self._update_check_finished(update, show_no_update))
            except UpdateError as exc:
                detail = str(exc)
                self.root.after(0, lambda: self._update_check_failed(detail, show_no_update))

        threading.Thread(target=worker, daemon=True).start()

    def _update_check_finished(self, update: UpdateInfo | None, show_no_update: bool) -> None:
        self.update_button.config(state="normal")
        self.status.config(text="工具已準備完成，可在瀏覽器中使用。")
        if update is None:
            if show_no_update:
                messagebox.showinfo(APP_NAME, "目前已是最新版本。")
            return

        notes = "\n".join(f"• {note}" for note in update.release_notes)
        message = f"發現新版本 {update.version}。"
        if notes:
            message += f"\n\n{notes}"
        message += "\n\n是否立即下載並安裝？"
        if messagebox.askyesno(f"{APP_NAME} 更新", message):
            self._download_update(update)

    def _update_check_failed(self, detail: str, show_error: bool) -> None:
        self.update_button.config(state="normal")
        self.status.config(text="工具已準備完成，可在瀏覽器中使用。")
        if show_error:
            messagebox.showwarning(APP_NAME, detail)

    def _download_update(self, update: UpdateInfo) -> None:
        self.update_button.config(state="disabled")
        self.status.config(text=f"正在下載版本 {update.version}...")

        def worker() -> None:
            try:
                installer = download_installer(update)
                if self.config.require_signed_updates and not has_valid_authenticode_signature(installer):
                    installer.unlink(missing_ok=True)
                    raise UpdateError("新版安裝程式沒有可信任的數位簽章，已取消更新。")
                self.root.after(0, lambda: self._install_update(installer))
            except UpdateError as exc:
                detail = str(exc)
                self.root.after(0, lambda: self._update_check_failed(detail, True))

        threading.Thread(target=worker, daemon=True).start()

    def _install_update(self, installer: Path) -> None:
        self._stop_server()
        subprocess.Popen(
            [str(installer), "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
            close_fds=True,
        )
        self.shutdown()

    def _stop_server(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def shutdown(self) -> None:
        if self.closing:
            return
        self.closing = True
        self._stop_server()
        self.runtime_path.unlink(missing_ok=True)
        self.instance.release()
        self.root.destroy()


def _open_existing_instance() -> None:
    runtime_path = user_data_dir() / "runtime.json"
    try:
        data = json.loads(runtime_path.read_text(encoding="utf-8"))
        url = str(data["url"])
        if url.startswith(f"http://{LOOPBACK_HOST}:"):
            webbrowser.open(url, new=2)
    except (OSError, ValueError, KeyError, TypeError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--run-server", action="store_true")
    parser.add_argument("--port", type=int)
    args, _ = parser.parse_known_args(argv)

    if args.run_server:
        if not args.port:
            return 2
        return run_streamlit_server(args.port)

    instance = SingleInstance()
    if not instance.acquire():
        _open_existing_instance()
        return 0
    return LauncherWindow(instance).run()


if __name__ == "__main__":
    raise SystemExit(main())
