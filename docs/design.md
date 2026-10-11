# taildrop-send — design

A Dolphin right-click entry, **Send via Taildrop…**, that sends the selected
files and folders to one of your own tailnet devices. The receive side
(files landing in `~/Downloads`) is a separate user service set up by
setup-tool's Tailscale recipe.

Modelled on `move-or-copy-to`: a service-menu `.desktop`, a PyQt6 dialog,
pure logic in `core.py` with unit tests, `install.sh` into `~/.local`.

## Devices

The list comes from `tailscale file cp --targets`, not `tailscale status`:
it only contains devices Taildrop can actually send to (your own devices,
not ones shared from other users). Lines are tab-separated:

    100.74.135.24	iphone
    100.79.126.117	mi	offline; last seen 44m0s ago

Online devices are listed first. Offline ones are shown greyed with a short
"offline 44m" / "offline 34d" note and can't be picked. The last device
sent to is remembered in `~/.config/taildrop-send/config.json` and
pre-selected.

## Sending

- Files are passed through as-is. Each folder is zipped to a temp dir as
  `<folder>.zip` (Taildrop only sends files). Temp zips are always removed
  when the dialog exits.
- One `tailscale file cp <files...> <device>:` runs via QProcess. No sudo:
  this relies on the Tailscale operator being set to the user.
- While sending, the dialog shows a busy bar and "Sending to <device>…";
  Cancel kills the transfer. Success closes the dialog and posts a desktop
  notification (`notify-send`); failure keeps the dialog open with the error.

## Errors explained in plain words

- `tailscale` missing, daemon not running, or not logged in.
- "access denied" → run `sudo tailscale set --operator=$USER`.
- A selected item no longer exists.

Every send is logged to `~/.local/state/taildrop-send/log`.

## Out of scope

A percentage progress bar (Tailscale's progress line is terminal-oriented)
and renaming files on send.
