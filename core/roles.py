"""Registre des rôles Fenix Server.

Un « rôle » est un service Linux exposé via une app KDE dédiée. Chaque rôle est
décrit par un fichier JSON ``roles/<role>.json``. Le :class:`RoleRegistry`
charge ces définitions et expose l'état (disponible / actif) des rôles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Role:
    """Définition d'un rôle, chargée depuis ``roles/<role>.json``.

    Attributes:
        id: Identifiant unique du rôle, ex. ``"ad"``, ``"updates"``.
        name: Nom affiché du rôle.
        description: Description courte du rôle.
        service_name: Nom du service système associé (unité systemd ou nom bus
            D-Bus), ex. ``"smbd"`` ou ``"org.freedesktop.PackageKit"``.
        app: Répertoire de l'app KDE qui gère le rôle, ex. ``"ad-manager"``.
    """

    id: str
    name: str
    description: str
    service_name: str
    app: str


class RoleRegistry:
    """Charge et expose les rôles définis dans le dossier ``roles/``."""

    def __init__(self, roles_dir: Path) -> None:
        """Initialise le registre.

        Args:
            roles_dir: Dossier contenant les fichiers ``<role>.json``.
        """
        raise NotImplementedError

    def load(self) -> None:
        """Charge (ou recharge) toutes les définitions de rôles depuis le disque.

        Raises:
            FileNotFoundError: si le dossier des rôles est introuvable.
            ValueError: si un fichier JSON de rôle est invalide.
        """
        raise NotImplementedError

    def all_roles(self) -> list[Role]:
        """Retourne tous les rôles connus (disponibles), triés par nom."""
        raise NotImplementedError

    def get(self, role_id: str) -> Role:
        """Retourne un rôle par son identifiant.

        Args:
            role_id: Identifiant du rôle.

        Returns:
            Le rôle correspondant.

        Raises:
            KeyError: si aucun rôle ne porte cet identifiant.
        """
        raise NotImplementedError

    def is_active(self, role_id: str) -> bool:
        """Indique si le rôle est actuellement actif (service en cours d'exécution).

        Args:
            role_id: Identifiant du rôle.

        Returns:
            ``True`` si le service associé est actif, ``False`` sinon.
        """
        raise NotImplementedError

    def active_roles(self) -> list[Role]:
        """Retourne la liste des rôles actuellement actifs."""
        raise NotImplementedError
