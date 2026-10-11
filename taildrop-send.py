#!/usr/bin/env python3
"""Dolphin service-menu popup: pick one of your devices, send the files there.

Invoked as:  taildrop-send <path> [<path> ...]
Parsing, zipping and command building live in core.py; this file is just
the Qt window that drives it.
"""

import os
import shutil
import subprocess
import sys
import tempfile

from PyQt6.QtCore import QProcess, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

import core

# Keep in sync with the Icon= line in taildrop-send.desktop.
WINDOW_ICON = "document-send"
TITLE = "Send via Taildrop"


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "taildrop-send", "config.json")


class ZipThread(QThread):
    """Runs core.expand_paths off the UI thread - big folders take a while."""

    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, paths, tmpdir):
        super().__init__()
        self.paths = paths
        self.tmpdir = tmpdir

    def run(self):
        try:
            self.done.emit(core.expand_paths(self.paths, self.tmpdir))
        except OSError as exc:
            self.failed.emit(f"Couldn't zip a folder: {exc}")


class SendDialog(QDialog):
    def __init__(self, sources, tailscale, tmpdir):
        super().__init__()
        self.sources = sources
        self.tailscale = tailscale
        self.tmpdir = tmpdir
        self.cfg_path = config_path()
        self.process = None
        self.zip_thread = None
        self.device = None

        self.setWindowTitle(TITLE)
        self.resize(400, 380)

        layout = QVBoxLayout(self)

        count = len(sources)
        heading = QLabel(f"Send {count} item{'s' if count != 1 else ''} to:")
        heading.setToolTip("\n".join(os.path.basename(s.rstrip("/")) for s in sources))
        heading.setStyleSheet("font-weight: bold;")
        layout.addWidget(heading)

        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(lambda _item: self._send())
        self.device_list.currentItemChanged.connect(lambda *_: self._update_send_enabled())
        layout.addWidget(self.device_list, stretch=1)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status.hide()
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator
        self.progress.hide()
        layout.addWidget(self.progress)

        self.refresh_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Refresh")
        self.refresh_btn.clicked.connect(self._load_devices)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.send_btn = self.buttons.addButton("Send", QDialogButtonBox.ButtonRole.AcceptRole)
        self.send_btn.setIcon(QIcon.fromTheme(WINDOW_ICON))
        self.buttons.accepted.connect(self._send)
        self.buttons.rejected.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_btn)
        button_row.addStretch()
        button_row.addWidget(self.buttons)
        layout.addLayout(button_row)

        self._load_devices()

    # --- devices ---------------------------------------------------------

    def _load_devices(self):
        previous = self.device_list.currentItem()
        wanted = previous.data(Qt.ItemDataRole.UserRole) if previous else core.load_config(self.cfg_path)["last_device"]
        self.device_list.clear()

        result = subprocess.run(
            [self.tailscale, "file", "cp", "--targets"], capture_output=True, text=True
        )
        if result.returncode != 0:
            self._show_error(core.explain_error(result.stderr or result.stdout))
            self._update_send_enabled()
            return

        devices = core.parse_targets(result.stdout)
        if not devices:
            self._show_error("No devices to send to. Sign in to Tailscale on your phone or other computers first.")
        else:
            self.status.hide()

        first_online = None
        for dev in devices:
            text = dev["name"] if not dev["note"] else f"{dev['name']}    ({dev['note']})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dev["name"])
            item.setToolTip(dev["ip"])
            if dev["online"]:
                item.setIcon(QIcon.fromTheme("network-connect"))
                first_online = first_online or item
            else:
                item.setIcon(QIcon.fromTheme("network-disconnect"))
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # greyed, unselectable
            self.device_list.addItem(item)
            if dev["online"] and dev["name"] == wanted:
                self.device_list.setCurrentItem(item)

        if self.device_list.currentItem() is None and first_online is not None:
            self.device_list.setCurrentItem(first_online)
        self._update_send_enabled()

    def _update_send_enabled(self):
        self.send_btn.setEnabled(self.device_list.currentItem() is not None and self.process is None)

    def _show_error(self, text):
        self.status.setText(text)
        self.status.setStyleSheet("color: #da4453;")  # Breeze's negative text colour
        self.status.show()

    def _set_busy(self, text):
        busy = text is not None
        self.device_list.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.status.setStyleSheet("")
            self.status.setText(text)
            self.status.show()

    # --- sending ---------------------------------------------------------

    def _send(self):
        item = self.device_list.currentItem()
        if item is None or self.zip_thread is not None or self.process is not None:
            return
        self.device = item.data(Qt.ItemDataRole.UserRole)

        missing = [s for s in self.sources if not os.path.exists(s)]
        if missing:
            self._show_error("These items no longer exist:\n" + "\n".join(missing))
            return

        if any(os.path.isdir(s) for s in self.sources):
            self._set_busy("Zipping folders…")
        self.zip_thread = ZipThread(self.sources, self.tmpdir)
        self.zip_thread.done.connect(self._start_transfer)
        self.zip_thread.failed.connect(self._zip_failed)
        self.zip_thread.start()

    def _zip_failed(self, message):
        self.zip_thread = None
        self._set_busy(None)
        self._show_error(message)

    def _start_transfer(self, files):
        self.zip_thread = None
        cmd = core.send_command(self.tailscale, files, self.device)
        # No progress repaint: its carriage-return line is meant for a
        # terminal and would only clutter the error output we show.
        cmd[3:3] = ["--update-interval", "0"]
        self._set_busy(f"Sending to {self.device}…")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(lambda code, status: self._transfer_finished(code, status, files))
        self.process.start(cmd[0], cmd[1:])

    def _transfer_finished(self, code, status, files):
        output = bytes(self.process.readAll()).decode(errors="replace")
        self.process = None
        ok = status == QProcess.ExitStatus.NormalExit and code == 0
        names = ", ".join(os.path.basename(f) for f in files)

        if not ok:
            core.append_log(f"FAILED {len(files)} file(s) -> {self.device}: {output.strip()}")
            self._set_busy(None)
            self._show_error(core.explain_error(output) or f"Sending failed (exit code {code}).")
            return

        core.append_log(f"sent {len(files)} file(s) -> {self.device}: {names}")
        core.save_config(self.cfg_path, {"last_device": self.device})
        notify(f"Sent to {self.device}", names)
        self.accept()

    def reject(self):
        """Cancel/Esc/close: stop any transfer in flight before leaving."""
        if self.process is not None:
            self.process.finished.disconnect()
            self.process.kill()
            self.process.waitForFinished(2000)
            core.append_log(f"cancelled send -> {self.device}")
        if self.zip_thread is not None:
            # Can't interrupt make_archive; wait so the temp dir can be removed.
            self.zip_thread.wait()
        super().reject()


def notify(summary, body):
    if shutil.which("notify-send"):
        subprocess.Popen(
            ["notify-send", "-a", "Taildrop", "-i", WINDOW_ICON, summary, body],
            start_new_session=True,
        )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sources = [os.path.abspath(os.path.expanduser(core.arg_to_path(a))) for a in argv if a]
    if not sources:
        sys.stderr.write("usage: taildrop-send <path> [<path> ...]\n")
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("taildrop-send")
    app.setDesktopFileName("taildrop-send")
    app.setWindowIcon(QIcon.fromTheme(WINDOW_ICON))

    tailscale = core.find_tailscale()
    if not tailscale:
        QMessageBox.critical(None, TITLE, "Tailscale isn't installed (no `tailscale` command found).")
        return 1

    tmpdir = tempfile.mkdtemp(prefix="taildrop-send-")
    try:
        dialog = SendDialog(sources, tailscale, tmpdir)
        return 0 if dialog.exec() == QDialog.DialogCode.Accepted else 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
