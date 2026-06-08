#!/bin/bash

APP_NAME="Apeiron_Bridge"
EXEC_NAME="Apeiron_Bridge"
BUNDLE_DIR="Apeiron_Bridge" # Assumes PyInstaller built to dist/Apeiron_Bridge
INSTALL_DIR="$HOME/.local/opt/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_NAME="apeiron_bridge_icon.png"
ICON_SOURCE="resources/icon.png" # Path relative to install.sh
ICON_DEST="$HOME/.local/share/icons/hicolor/512x512/apps"

echo "========================================="
echo " Installing Apeiron Bridge"
echo "========================================="

# 1. Check if we are running in the correct directory (next to the bundle)
if [ ! -d "dist/$BUNDLE_DIR" ]; then
    echo "❌ Error: Could not find 'dist/$BUNDLE_DIR' directory."
    echo "Make sure you run this script from the same folder where you built the app, or place the 'dist/$BUNDLE_DIR' folder next to this script."
    exit 1
fi

# 1.5. Install and configure PostgreSQL database dependency
echo "Checking and installing PostgreSQL database service..."
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Enable PostgreSQL to start automatically on boot and start it now
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Verify it is running before proceeding
if ! sudo systemctl is-active --quiet postgresql; then
    echo "ERROR: PostgreSQL failed to start. Check: sudo journalctl -xe"
    exit 1
fi

# Configure the dedicated database role and database
echo "Configuring PostgreSQL user and database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='apeiron'" | grep -q 1 || sudo -u postgres psql -c "CREATE ROLE apeiron WITH LOGIN SUPERUSER PASSWORD 'apeiron_local';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='apeiron_bridge'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE apeiron_bridge OWNER apeiron;"

# Run the database setup script to apply migrations and seed the data
echo "Running database migrations and seed setup..."
if [ -f "venv/bin/python" ]; then
    PYTHONPATH=. venv/bin/python app/rate_analysis_comparison/db/setup.py
elif command -v python3 &>/dev/null; then
    PYTHONPATH=. python3 app/rate_analysis_comparison/db/setup.py
else
    echo "⚠️ Warning: Python environment not found. Skipped database migrations."
fi


# 2. Check for the icon
if [ ! -f "$ICON_SOURCE" ]; then
    echo "⚠️ Warning: Icon file '$ICON_SOURCE' not found. App will use a default icon."
fi

# 3. Create target directories
echo "Creating application directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DEST"

# 4. Copy the application files
echo "Copying application bundle to $INSTALL_DIR..."
# Ensure we cleanly overwrite old installs
rm -rf "$INSTALL_DIR"/*
cp -r "dist/$BUNDLE_DIR/"* "$INSTALL_DIR/"

# 5. Make it executable and link to bin
chmod +x "$INSTALL_DIR/$EXEC_NAME"
echo "Creating binary symlink in $BIN_DIR..."
ln -sf "$INSTALL_DIR/$EXEC_NAME" "$BIN_DIR/$EXEC_NAME"

# Add ~/.local/bin to PATH if not already there (only for current session warning)
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "⚠️ Notice: $HOME/.local/bin is not in your PATH."
    echo "You may need to log out and log back in, or add it to your ~/.bashrc"
fi

# 6. Install the icon
if [ -f "$ICON_SOURCE" ]; then
    echo "Installing icon..."
    cp "$ICON_SOURCE" "$ICON_DEST/$ICON_NAME"
    # Update icon cache
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
else
    ICON_NAME="" # Leave blank if not found
fi

# 7. Create the .desktop file
echo "Creating desktop shortcut..."
DESKTOP_FILE="$DESKTOP_DIR/$APP_NAME.desktop"

cat > "$DESKTOP_FILE" << EOL
[Desktop Entry]
Name=Apeiron Bridge
Comment=Standalone Application for Apeiron Bridge
Exec=$BIN_DIR/$EXEC_NAME
Icon=$ICON_NAME
Terminal=false
Type=Application
Categories=Office;Utility;
StartupNotify=true
EOL

chmod +x "$DESKTOP_FILE"

# 8. Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo ""
echo "✅ Installation Complete! ✅"
echo "You can now launch 'Apeiron Bridge' from your application menu."
echo "Or run '$EXEC_NAME' from your terminal."
echo "========================================="
