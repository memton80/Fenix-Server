#!/usr/bin/env bash
#
# dev-run.sh — lance update-manager depuis le dépôt, sans installation complète.
#
# Pratique pour tester rapidement sur une VM disposant déjà d'un bureau.
# Ne touche pas au système : ajoute simplement la racine du projet au
# PYTHONPATH (pour que `core` soit importable) puis lance l'app.
#
#     bootstrap/dev-run.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_DIR="$PROJECT_ROOT/update-manager"

# Rend la lib partagée `core` importable depuis l'app.
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Wayland uniquement (surchargeable via l'environnement si besoin).
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

if ! python3 -c "import PySide6" 2> /dev/null; then
    echo "PySide6 introuvable. Installe les dépendances :" >&2
    echo "    pip install -r \"$PROJECT_ROOT/requirements.txt\"" >&2
    exit 1
fi

cd "$APP_DIR"
exec python3 main.py
