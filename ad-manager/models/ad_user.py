"""Modèle d'utilisateur Active Directory / Samba."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ADUser:
    """Utilisateur du domaine, tel qu'exposé par l'annuaire LDAP.

    Attributes:
        username: Identifiant de connexion (``sAMAccountName``).
        display_name: Nom affiché de l'utilisateur (``displayName`` / ``cn``).
        email: Adresse e-mail principale (``mail``), vide si absente.
        enabled: ``True`` si le compte est activé (non désactivé dans AD).
        dn: Distinguished Name complet de l'entrée LDAP.
        groups: Noms des groupes dont l'utilisateur est membre.
    """

    username: str
    display_name: str
    email: str
    enabled: bool
    dn: str
    groups: tuple[str, ...] = ()
