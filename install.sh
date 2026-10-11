#!/usr/bin/env bash
# Install (or update) the "Send via Taildrop…" Dolphin service menu.
set -euo pipefail

src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

lib_dir="${XDG_DATA_HOME:-$HOME/.local/share}/taildrop-send"
bin_dir="$HOME/.local/bin"
menu_dir="${XDG_DATA_HOME:-$HOME/.local/share}/kio/servicemenus"

mkdir -p "$lib_dir" "$bin_dir" "$menu_dir"

install -m 0644 "$src_dir/core.py"          "$lib_dir/core.py"
install -m 0644 "$src_dir/taildrop-send.py" "$lib_dir/taildrop-send.py"

cat > "$bin_dir/taildrop-send" <<EOF
#!/usr/bin/env bash
exec python3 "$lib_dir/taildrop-send.py" "\$@"
EOF
chmod 0755 "$bin_dir/taildrop-send"

# Plasma 6 requires the service-menu file itself to be executable.
install -m 0755 "$src_dir/taildrop-send.desktop" "$menu_dir/taildrop-send.desktop"

echo "Installed:"
echo "  $bin_dir/taildrop-send"
echo "  $lib_dir/{core,taildrop-send}.py"
echo "  $menu_dir/taildrop-send.desktop"
echo
echo "Restart Dolphin (or run: kbuildsycoca6) to pick up the menu entry."
