"""Modèle de groupe Active Directory / Samba."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ldap3.abstract.entry import Entry


def _first(attrs: dict[str, list[object]], name: str, default: str = "") -> str:
    """Retourne la première valeur d'un attribut LDAP multivalué, sous forme de str.

    Args:
        attrs: Attributs de l'entrée (``attribut -> liste de valeurs``).
        name: Nom de l'attribut recherché.
        default: Valeur retournée si l'attribut est absent ou vide.

    Returns:
        La première valeur convertie en ``str``, ou ``default``.
    """
    values = attrs.get(name) or []
    return str(values[0]) if values else default


@dataclass(frozen=True)
class ADGroup:
    """Groupe du domaine, tel qu'exposé par l'annuaire LDAP.

    Attributes:
        name: Nom du groupe (``sAMAccountName`` / ``cn``).
        description: Description du groupe (``description``), vide si absente.
        dn: Distinguished Name complet de l'entrée LDAP.
        members: DN des membres du groupe (``member``).
    """

    name: str
    description: str
    dn: str
    members: tuple[str, ...] = ()

    @classmethod
    def from_ldap_entry(cls, entry: Entry) -> ADGroup:
        """Construit un :class:`ADGroup` depuis une entrée ``ldap3``.

        Args:
            entry: Entrée ``ldap3`` exposant ``entry_dn`` et
                ``entry_attributes_as_dict``.

        Returns:
            Le groupe correspondant.
        """
        attrs: dict[str, list[object]] = dict(entry.entry_attributes_as_dict)
        return cls(
            name=_first(attrs, "sAMAccountName") or _first(attrs, "cn"),
            description=_first(attrs, "description"),
            dn=str(entry.entry_dn),
            members=tuple(str(member) for member in attrs.get("member") or ()),
        )
