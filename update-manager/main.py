"""Point d'entrée de l'Update Manager (QApplication).

Lancement en dev :
    cd update-manager/ && python main.py
"""

from __future__ import annotations

import sys

from main_window import UpdateManagerWindow
from PySide6.QtWidgets import QApplication

from core.theme import ThemeManager


def main() -> int:
    """Crée la ``QApplication``, applique le thème, ouvre la fenêtre principale.

    Returns:
        Le code de sortie de la boucle d'événements Qt.
    """
    app = QApplication(sys.argv)
    theme = ThemeManager.from_system()
    theme.apply(app)
    window = UpdateManagerWindow(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
