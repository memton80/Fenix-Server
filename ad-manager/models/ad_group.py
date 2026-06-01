"""Modèle de groupe Active Directory / Samba."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ADGroup:
    """Groupe du domaine, tel qu'exposé par l'annuaire LDAP.

    Attributes:
        name: Nom du groupe (``sAMAccountName`` / ``cn``).
        description: Description du groupe (``description``), vide si absente.
        dn: Distinguished Name complet de l'entrée LDAP.
        members: Noms des membres du groupe (``member``).
    """

    name: str
    description: str
    dn: str
    members: tuple[str, ...] = ()
