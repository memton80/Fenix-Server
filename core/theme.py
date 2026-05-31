"""Thème Fenix Server : couleurs, polices, styles Qt et icônes.

Toutes les apps importent leurs styles depuis :class:`ThemeManager`. Aucune
couleur ni police ne doit être hardcodée dans les widgets (voir les règles de
style du projet).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon


class ThemeMode(Enum):
    """Mode de thème supporté par Fenix Server."""

    DARK = "dark"
    LIGHT = "light"


class ThemeManager:
    """Fournit les styles, couleurs et icônes du thème Fenix Server.

    Point d'entrée unique pour le style des apps. Les méthodes renvoyant des
    feuilles de style Qt sont prévues pour ``widget.setStyleSheet(...)``.
    """

    def __init__(self, mode: ThemeMode = ThemeMode.DARK) -> None:
        """Initialise le gestionnaire de thème.

        Args:
            mode: Mode initial du thème (sombre par défaut).
        """
        raise NotImplementedError

    @property
    def mode(self) -> ThemeMode:
        """Mode de thème actuellement actif."""
        raise NotImplementedError

    def set_mode(self, mode: ThemeMode) -> None:
        """Bascule le thème vers un autre mode.

        Args:
            mode: Nouveau mode à appliquer.
        """
        raise NotImplementedError

    def color(self, token: str) -> str:
        """Retourne une couleur du thème sous forme hexadécimale.

        Args:
            token: Nom logique de la couleur, ex. ``"accent"``, ``"background"``,
                ``"error"``.

        Returns:
            La couleur au format ``"#rrggbb"``.

        Raises:
            KeyError: si le token n'existe pas dans le thème.
        """
        raise NotImplementedError

    def apply(self, app: object) -> None:
        """Applique le thème global à une ``QApplication``.

        Args:
            app: L'instance ``QApplication`` à styliser.
        """
        raise NotImplementedError

    def label_style(self) -> str:
        """Retourne la feuille de style Qt pour un libellé standard."""
        raise NotImplementedError

    def button_style(self) -> str:
        """Retourne la feuille de style Qt pour un bouton standard."""
        raise NotImplementedError

    def icon(self, name: str) -> "QIcon":
        """Retourne une icône du thème par son nom logique.

        Args:
            name: Nom logique de l'icône, ex. ``"role-active"``, ``"warning"``.

        Returns:
            L'icône Qt correspondante.
        """
        raise NotImplementedError
