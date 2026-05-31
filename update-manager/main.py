"""Point d'entrée de l'Update Manager (QApplication).

Lancement en dev :
    cd update-manager/ && python main.py
"""

from __future__ import annotations


def main() -> int:
    """Crée la ``QApplication``, applique le thème, ouvre la fenêtre principale.

    Returns:
        Le code de sortie de la boucle d'événements Qt.
    """
    raise NotImplementedError


if __name__ == "__main__":
    import sys

    sys.exit(main())
