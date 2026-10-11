# Maintainer: James <claude@jamessparkes.com>
pkgname=taildrop-send
pkgver=1.0.1
pkgrel=1
pkgdesc="Taildrop for KDE: right-click \"Send via Taildrop…\" in Dolphin, and received files saved to ~/Downloads"
arch=('any')
url="https://github.com/missingfoot/taildrop-send"
license=('MIT')
depends=('python-pyqt6' 'tailscale' 'kio')
optdepends=('libnotify: desktop notification when a send finishes')
source=('core.py' 'taildrop-send.py' 'taildrop-send.desktop' 'taildrop.service' 'LICENSE')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    install -Dm644 "$srcdir/core.py" "$pkgdir/usr/lib/taildrop-send/core.py"
    install -Dm644 "$srcdir/taildrop-send.py" "$pkgdir/usr/lib/taildrop-send/taildrop-send.py"

    install -d "$pkgdir/usr/bin"
    cat > "$pkgdir/usr/bin/taildrop-send" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/lib/taildrop-send/taildrop-send.py "$@"
LAUNCHER
    chmod 755 "$pkgdir/usr/bin/taildrop-send"

    # Receive side, per user: `systemctl --user enable --now taildrop.service`
    # saves incoming files to ~/Downloads (needs the Tailscale operator set).
    install -Dm644 "$srcdir/taildrop.service" "$pkgdir/usr/lib/systemd/user/taildrop.service"

    install -Dm755 "$srcdir/taildrop-send.desktop" "$pkgdir/usr/share/kio/servicemenus/taildrop-send.desktop"
    install -Dm644 "$srcdir/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
