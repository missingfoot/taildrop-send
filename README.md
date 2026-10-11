# taildrop-send

Taildrop for KDE, both ways:

- **Send:** a Dolphin right-click entry — **Send via Taildrop…** — opens a
  small popup listing your Tailscale devices. Pick one, hit **Send**, done.
- **Receive:** a user service, `taildrop.service`, saves files sent to this
  machine straight into `~/Downloads` (renaming on clashes) instead of
  leaving them in Tailscale's inbox. Turn it on once with
  `systemctl --user enable --now taildrop.service` (packaged install only).

## Features

- Devices come from `tailscale file cp --targets`, so only ones Taildrop can
  actually reach are listed. Offline devices are greyed out ("offline 44m").
- Folders are zipped (`<folder>.zip`) before sending; temp zips are cleaned up.
- Remembers the last device you sent to and pre-selects it.
- Busy bar while sending, Cancel stops the transfer, desktop notification
  when it's done, plain-language errors when it isn't.

## Requirements

- KDE Plasma 6 with Dolphin, `python-pyqt6`, `tailscale`
- Your user set as Tailscale operator (sends without sudo), once:

      sudo tailscale set --operator=$USER

## Install

As a package (system-wide, into `/usr`):

```bash
makepkg -si
```

Or just for your user, into `~/.local`:

```bash
./install.sh
kbuildsycoca6   # or just restart Dolphin
```

Use one or the other, not both, or the menu entry shows up twice.

`install.sh` puts:

| Path | What |
|---|---|
| `~/.local/share/taildrop-send/{core,taildrop-send}.py` | the app |
| `~/.local/bin/taildrop-send` | launcher |
| `~/.local/share/kio/servicemenus/taildrop-send.desktop` | the menu entry (must stay executable) |

## Data

- Last device: `~/.config/taildrop-send/config.json`
- Send log: `~/.local/state/taildrop-send/log`

## Development

Pure logic lives in `core.py`; `taildrop-send.py` is the PyQt6 window over it.
See `docs/design.md`.

```bash
python -m unittest test_core
```

## License

MIT
