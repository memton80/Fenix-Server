"""Modèles de données pour les mises à jour (système et services).

Deux natures de mises à jour coexistent dans l'Update Manager :
- les paquets système, fournis par PackageKit ;
- les services Fenix, comparés aux releases GitHub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Extrait les composantes numériques d'une version ("v1.10.0" -> (1, 10, 0)).
_VERSION_PART_RE = re.compile(r"\d+")


def _version_key(version: str) -> tuple[int, ...]:
    """Convertit une chaîne de version en tuple d'entiers comparable.

    Ignore tout préfixe non numérique (ex. ``"v"``) et compare composante par
    composante numériquement, de sorte que ``1.10.0 > 1.9.0``.

    Args:
        version: Version sous forme de chaîne (ex. ``"v1.10.0"``).

    Returns:
        Le tuple des composantes numériques.
    """
    return tuple(int(part) for part in _VERSION_PART_RE.findall(version))


@dataclass(frozen=True)
class SystemPackageUpdate:
    """Mise à jour d'un paquet système exposée par PackageKit.

    Attributes:
        package_id: Identifiant PackageKit complet (``"nom;version;arch;data"``).
        name: Nom du paquet.
        version: Version proposée par la mise à jour.
        summary: Résumé court du paquet.
    """

    package_id: str
    name: str
    version: str
    summary: str


@dataclass(frozen=True)
class ServiceUpdate:
    """Mise à jour potentielle d'un service Fenix, basée sur les releases GitHub.

    Attributes:
        service_id: Identifiant du service Fenix concerné.
        name: Nom affiché du service.
        current_version: Version actuellement installée.
        latest_version: Dernière version publiée sur GitHub.
        release_url: URL de la release GitHub correspondante.
    """

    service_id: str
    name: str
    current_version: str
    latest_version: str
    release_url: str

    @property
    def update_available(self) -> bool:
        """Indique si ``latest_version`` est plus récente que ``current_version``."""
        if not self.latest_version:
            return False
        return _version_key(self.latest_version) > _version_key(self.current_version)
