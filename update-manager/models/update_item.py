"""Modèles de données pour les mises à jour (système et services).

Deux natures de mises à jour coexistent dans l'Update Manager :
- les paquets système, fournis par PackageKit ;
- les services Fenix, comparés aux releases GitHub.
"""

from __future__ import annotations

from dataclasses import dataclass


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
        raise NotImplementedError
