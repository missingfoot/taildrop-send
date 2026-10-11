# Maintainer: James <claude@jamessparkes.com>
pkgname=taildrop-send
pkgver=1.0.0
pkgrel=1
pkgdesc="Dolphin right-click \"Send via Taildrop…\" popup for sending files to your Tailscale devices"
arch=('any')
url="https://github.com/missingfoot/taildrop-send"
license=('MIT')
depends=('python-pyqt6' 'tailscale' 'kio')
optdepends=('libnotify: desktop notification when a send finishes')
source=('core.py' 'taildrop-send.py' 'taildrop-send.desktop' 'LICENSE')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    install -Dm644 "$srcdir/core.py" "$pkgdir/usr/lib/taildrop-send/core.py"
    install -Dm644 "$srcdir/taildrop-send.py" "$pkgdir/usr/lib/taildrop-send/taildrop-send.py"

    install -d "$pkgdir/usr/bin"
    cat > "$pkgdir/usr/bin/taildrop-send" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/lib/taildrop-send/taildrop-send.py "$@"
LAUNCHER
    chmod 755 "$pkgdir/usr/bin/taildrop-send"

    install -Dm755 "$srcdir/taildrop-send.desktop" "$pkgdir/usr/share/kio/servicemenus/taildrop-send.desktop"
    install -Dm644 "$srcdir/LICENSE" "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
