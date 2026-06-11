#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/share/wallpaper-changer"
VENV_DIR="$INSTALL_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
SERVICE_DIR="$HOME/.config/systemd/user"

echo "=== Wallpaper Changer Installer ==="

# Create directories
mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$SERVICE_DIR"

# Copy source
echo "Copying files..."
cp -r src/ "$INSTALL_DIR/"
cp pyproject.toml "$INSTALL_DIR/"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -e "$INSTALL_DIR" 2>/dev/null

# Create launcher script
echo "Creating launcher..."
cat > "$BIN_DIR/wallpaper-changer-gui" << 'EOF'
#!/bin/bash
source "$HOME/.local/share/wallpaper-changer/.venv/bin/activate"
exec python3 -m wallpaper_changer.gui "$@"
EOF
chmod +x "$BIN_DIR/wallpaper-changer-gui"

cat > "$BIN_DIR/wallpaper-changer" << 'EOF'
#!/bin/bash
source "$HOME/.local/share/wallpaper-changer/.venv/bin/activate"
exec python3 -m wallpaper_changer.cli "$@"
EOF
chmod +x "$BIN_DIR/wallpaper-changer"

# Install desktop entry
echo "Installing desktop entry..."
cp data/io.github.alatzr.WallpaperChanger.desktop "$DESKTOP_DIR/"
sed -i "s|Exec=wallpaper-changer-gui|Exec=$BIN_DIR/wallpaper-changer-gui|" "$DESKTOP_DIR/io.github.alatzr.WallpaperChanger.desktop"
sed -i "s|Icon=io.github.alatzr.WallpaperChanger|Icon=$ICON_DIR/io.github.alatzr.WallpaperChanger.svg|" "$DESKTOP_DIR/io.github.alatzr.WallpaperChanger.desktop"

# Install icon
cp data/io.github.alatzr.WallpaperChanger.svg "$ICON_DIR/"

# Create systemd service
echo "Creating systemd service..."
cat > "$SERVICE_DIR/wallpaper-changer.service" << EOF
[Unit]
Description=Wallpaper Changer
After=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/wallpaper-changer start
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=default.target
EOF

# Copy system hicolor index if needed for icon cache
if [ ! -f "$HOME/.local/share/icons/hicolor/index.theme" ] && [ -f "/usr/share/icons/hicolor/index.theme" ]; then
    cp /usr/share/icons/hicolor/index.theme "$HOME/.local/share/icons/hicolor/"
fi

# Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Run:  wallpaper-changer-gui"
echo "Or:   wallpaper-changer --help"
echo ""
echo "To enable autostart:"
echo "  systemctl --user enable wallpaper-changer"
echo "  systemctl --user start wallpaper-changer"
