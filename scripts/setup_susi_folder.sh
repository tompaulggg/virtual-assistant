#!/bin/bash
# Setup ~/Susi/ folder with symlinks to relevant directories

SUSI_DIR="$HOME/Susi"

echo "Setting up Susi folder at $SUSI_DIR..."

mkdir -p "$SUSI_DIR/persoenlich"

# Symlink known directories (only if target exists)
if [ -d "$HOME/Documents/Businessplan" ]; then
    ln -sfn "$HOME/Documents/Businessplan" "$SUSI_DIR/businessplan"
    echo "  Linked: businessplan → ~/Documents/Businessplan"
fi

if [ -d "$HOME/Documents/BotProjects/docs" ]; then
    ln -sfn "$HOME/Documents/BotProjects/docs" "$SUSI_DIR/specs"
    echo "  Linked: specs → ~/Documents/BotProjects/docs"
fi

if [ -d "$HOME/Documents/BotProjects/sops" ]; then
    ln -sfn "$HOME/Documents/BotProjects/sops" "$SUSI_DIR/sops"
    echo "  Linked: sops → ~/Documents/BotProjects/sops"
fi

echo ""
echo "Susi folder ready at $SUSI_DIR"
echo "Lege Dateien in $SUSI_DIR ab die Susi kennen soll."
ls -la "$SUSI_DIR"
