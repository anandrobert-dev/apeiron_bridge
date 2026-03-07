#!/bin/bash

APP_NAME="Apeiron_Bridge"
EXEC_NAME="Apeiron_Bridge"
INSTALL_DIR="$HOME/.local/opt/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_NAME="apeiron_bridge_icon.png"
ICON_DEST="$HOME/.local/share/icons/hicolor/512x512/apps"

echo "========================================="
echo " Uninstalling Apeiron Bridge..."
echo "========================================="

# 1. Remove the installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "🗑️ Removing application files from $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
else
    echo "ℹ️ Application bundle directory not found. Skipping."
fi

# 2. Remove the binary symlink
if [ -L "$BIN_DIR/$EXEC_NAME" ] || [ -f "$BIN_DIR/$EXEC_NAME" ]; then
    echo "🗑️ Removing executable link from $BIN_DIR..."
    rm -f "$BIN_DIR/$EXEC_NAME"
else
    echo "ℹ️ Executable link not found. Skipping."
fi

# 3. Remove the desktop file
if [ -f "$DESKTOP_DIR/$APP_NAME.desktop" ]; then
    echo "🗑️ Removing desktop shortcut from $DESKTOP_DIR..."
    rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
    # Update desktop database
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
else
    echo "ℹ️ Desktop shortcut not found. Skipping."
fi

# 4. Remove the icon
if [ -f "$ICON_DEST/$ICON_NAME" ]; then
    echo "🗑️ Removing icon from $ICON_DEST..."
    rm -f "$ICON_DEST/$ICON_NAME"
    # Update icon cache
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
else
    echo "ℹ️ Icon file not found. Skipping."
fi

echo ""
echo "✅ Uninstallation Complete!"
echo "All Apeiron Bridge app files have been removed from your local profile."
echo "========================================="
