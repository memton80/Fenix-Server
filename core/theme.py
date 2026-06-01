"""Thème Fenix Server : couleurs, polices, styles Qt et icônes.

Toutes les apps importent leurs styles depuis :class:`ThemeManager`. Aucune
couleur ni police ne doit être hardcodée dans les widgets (voir les règles de
style du projet).

La préférence de thème de l'utilisateur (clair / sombre) est lue depuis KDE
Plasma via le portail XDG ``org.freedesktop.portal.Settings`` (clé
``org.freedesktop.appearance / color-scheme``), qui est le mécanisme exposé par
Plasma et partagé par les autres environnements.

Note : ce portail est un service **de session** (préférence par utilisateur),
on s'y connecte donc via le bus de session — exception justifiée à la règle
« system bus uniquement », qui ne vise que les services *système*.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from dasbus.error import DBusError

from core.dbus_helper import get_session_bus

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon

logger = logging.getLogger(__name__)

# Portail XDG Settings — lecture de la préférence d'apparence.
PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT = "/org/freedesktop/portal/desktop"
APPEARANCE_NAMESPACE = "org.freedesktop.appearance"
COLOR_SCHEME_KEY = "color-scheme"

# Valeurs de la clé color-scheme du portail XDG.
_SCHEME_NO_PREFERENCE = 0
_SCHEME_PREFER_DARK = 1
_SCHEME_PREFER_LIGHT = 2


class ThemeMode(Enum):
    """Mode de thème supporté par Fenix Server."""

    DARK = "dark"
    LIGHT = "light"


# Palettes par mode. Chaque mode expose exactement les mêmes tokens.
_PALETTES: dict[ThemeMode, dict[str, str]] = {
    ThemeMode.DARK: {
        "background": "#1e1e1e",
        "surface": "#2b2b2b",
        "text": "#f0f0f0",
        "text_muted": "#a0a0a0",
        "accent": "#2a9d8f",
        "accent_hover": "#3cb4a4",
        "border": "#3c3c3c",
        "error": "#e76f51",
        "warning": "#e9c46a",
        "success": "#2a9d8f",
    },
    ThemeMode.LIGHT: {
        "background": "#f5f5f5",
        "surface": "#ffffff",
        "text": "#1e1e1e",
        "text_muted": "#5c5c5c",
        "accent": "#2a9d8f",
        "accent_hover": "#21867a",
        "border": "#d0d0d0",
        "error": "#d84a30",
        "warning": "#c79a2e",
        "success": "#2a9d8f",
    },
}


def _unwrap_int(value: object) -> int | None:
    """Extrait un entier d'une valeur de portail éventuellement enveloppée en variant.

    Le portail renvoie un ``v`` parfois doublement enveloppé selon les
    implémentations ; on déballe jusqu'à obtenir un entier.
    """
    depth = 0
    while hasattr(value, "unpack") and depth < 5:
        value = value.unpack()
        depth += 1
    return value if isinstance(value, int) else None


def _read_color_scheme() -> int | None:
    """Lit la clé ``color-scheme`` via le portail XDG sur le bus de session.

    Returns:
        L'entier de préférence (0/1/2) ou ``None`` si indisponible/illisible.
    """
    try:
        portal = get_session_bus().get_proxy(PORTAL_SERVICE, PORTAL_OBJECT)
        raw = portal.Read(APPEARANCE_NAMESPACE, COLOR_SCHEME_KEY)
    except (DBusError, RuntimeError) as exc:
        logger.warning("Lecture de la préférence de thème KDE échouée: %s", exc)
        return None
    return _unwrap_int(raw)


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
        self._mode = mode

    @classmethod
    def detect_system_mode(cls) -> ThemeMode | None:
        """Détecte la préférence de thème de KDE Plasma via le portail XDG.

        Returns:
            :attr:`ThemeMode.DARK` ou :attr:`ThemeMode.LIGHT` selon la
            préférence utilisateur, ou ``None`` si aucune préférence n'est
            exprimée ou si le portail est indisponible.
        """
        value = _read_color_scheme()
        if value == _SCHEME_PREFER_DARK:
            return ThemeMode.DARK
        if value == _SCHEME_PREFER_LIGHT:
            return ThemeMode.LIGHT
        return None

    @classmethod
    def from_system(cls, fallback: ThemeMode = ThemeMode.DARK) -> ThemeManager:
        """Crée un gestionnaire initialisé sur la préférence système.

        Args:
            fallback: Mode utilisé si aucune préférence n'est détectable.

        Returns:
            Un :class:`ThemeManager` dans le mode détecté ou de repli.
        """
        detected = cls.detect_system_mode()
        return cls(detected if detected is not None else fallback)

    @property
    def mode(self) -> ThemeMode:
        """Mode de thème actuellement actif."""
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        """Bascule le thème vers un autre mode.

        Args:
            mode: Nouveau mode à appliquer.
        """
        self._mode = mode

    def sync_with_system(self) -> bool:
        """Aligne le mode courant sur la préférence système si elle est détectable.

        Returns:
            ``True`` si un mode système a été détecté et appliqué, ``False`` si
            le mode courant a été conservé (aucune préférence détectée).
        """
        detected = self.detect_system_mode()
        if detected is None:
            return False
        self._mode = detected
        return True

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
        return _PALETTES[self._mode][token]

    def global_style(self) -> str:
        """Retourne la feuille de style Qt globale de l'application."""
        return (
            f"QWidget {{ background-color: {self.color('background')};"
            f" color: {self.color('text')}; }}"
            f" QWidget:disabled {{ color: {self.color('text_muted')}; }}"
        )

    def apply(self, app: object) -> None:
        """Applique le thème global à une ``QApplication``.

        Args:
            app: L'instance ``QApplication`` à styliser.
        """
        app.setStyleSheet(self.global_style())

    def label_style(self) -> str:
        """Retourne la feuille de style Qt pour un libellé standard."""
        return f"color: {self.color('text')};"

    def button_style(self) -> str:
        """Retourne la feuille de style Qt pour un bouton standard."""
        return (
            f"QPushButton {{ background-color: {self.color('accent')};"
            f" color: {self.color('background')}; border: none; border-radius: 4px;"
            f" padding: 6px 14px; }}"
            f" QPushButton:hover {{ background-color: {self.color('accent_hover')}; }}"
            f" QPushButton:disabled {{ background-color: {self.color('border')}; }}"
        )

    def icon(self, name: str) -> QIcon:
        """Retourne une icône du thème par son nom logique.

        Utilise le thème d'icônes courant (KDE/freedesktop) via
        ``QIcon.fromTheme``.

        Args:
            name: Nom logique de l'icône, ex. ``"role-active"``, ``"warning"``.

        Returns:
            L'icône Qt correspondante.
        """
        from PySide6.QtGui import QIcon

        return QIcon.fromTheme(name)
