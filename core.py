"""Pure logic for the taildrop-send Dolphin service menu.

No Qt, no side effects beyond explicit file writes (save_config, the zips
expand_paths makes, append_log), so this module is fully unit-testable.
"""

import datetime
import json
import os
import re
import shutil
import tempfile
from urllib.parse import unquote, urlparse

DEFAULTS = {"last_device": None}


# --- devices --------------------------------------------------------------

def parse_targets(text):
    """Parse `tailscale file cp --targets` output into device dicts.

    Each line is `<ip>\\t<name>[\\t<status>]`; a status, when present, starts
    with "offline" (e.g. "offline; last seen 44m0s ago"). Online devices come
    first, each group keeping tailscale's order.
    """
    online, offline = [], []
    for line in text.splitlines():
        fields = line.strip().split("\t")
        if len(fields) < 2 or not fields[0] or not fields[1]:
            continue
        ip, name = fields[0], fields[1]
        status = fields[2].strip() if len(fields) > 2 else ""
        if status.startswith("offline"):
            match = re.search(r"last seen (\S+) ago", status)
            note = f"offline {short_duration(match.group(1))}" if match else "offline"
            offline.append({"name": name, "ip": ip, "online": False, "note": note})
        else:
            online.append({"name": name, "ip": ip, "online": True, "note": status})
    return online + offline


def short_duration(text):
    """Turn a Go duration like "831h11m0s" into a short label like "34d"."""
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:[\d.]+s)?", text)
    if not match or not text:
        return text
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    if hours >= 48:
        return f"{hours // 24}d"
    if hours:
        return f"{hours}h"
    if minutes:
        return f"{minutes}m"
    return "now"


# --- sending --------------------------------------------------------------

def expand_paths(paths, tmpdir):
    """Return the files to send: files as-is, each folder zipped into tmpdir.

    Taildrop only sends files, so a folder becomes `<folder>.zip` with the
    folder itself as the zip's top level. Same-named folders get -2, -3, …
    """
    files = []
    used = set()
    for path in paths:
        path = path.rstrip("/") or path
        if not os.path.isdir(path):
            files.append(path)
            continue
        name = os.path.basename(path)
        stem, n = name, 2
        while stem in used:
            stem = f"{name}-{n}"
            n += 1
        used.add(stem)
        archive = shutil.make_archive(
            os.path.join(tmpdir, stem), "zip",
            root_dir=os.path.dirname(path), base_dir=name,
        )
        files.append(archive)
    return files


def send_command(tailscale_bin, files, device):
    if not files:
        raise ValueError("no files given")
    # The trailing colon is how tailscale tells a target from a file name.
    return [tailscale_bin, "file", "cp", *files, f"{device}:"]


def find_tailscale(which=shutil.which):
    return which("tailscale")


def explain_error(output):
    """A plain-language message for a failed tailscale command."""
    lowered = output.lower()
    if "access denied" in lowered:
        return (
            "Tailscale won't let your user send files yet. Run this once in a "
            "terminal, then try again:\n\n    sudo tailscale set --operator=$USER"
        )
    if "failed to connect to local tailscaled" in lowered or "doesn't appear to be running" in lowered:
        return (
            "Tailscale isn't running. Start it with:\n\n"
            "    sudo systemctl enable --now tailscaled"
        )
    if "logged out" in lowered or "needslogin" in lowered:
        return "Tailscale isn't logged in. Run `sudo tailscale up` and open the link it prints."
    return output.strip()


# --- config ---------------------------------------------------------------

def load_config(path):
    """Return the config dict; a missing or corrupt file yields defaults."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except (OSError, ValueError):
        data = {}
    last = data.get("last_device")
    return {"last_device": last if isinstance(last, str) else None}


def save_config(path, config):
    """Atomically write config as pretty JSON, creating parent dirs as needed."""
    path = os.fspath(path)
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- misc -----------------------------------------------------------------

def arg_to_path(arg):
    """Normalise a service-menu argument (plain path or file:// URL) to a path."""
    if arg.startswith("file://"):
        return unquote(urlparse(arg).path)
    return arg


def log_path():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "taildrop-send", "log")


def append_log(message, path=None):
    """Append a timestamped line to the log. Never raises."""
    path = os.fspath(path or log_path())
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {message}\n")
    except OSError:
        pass
