"""Modèle d'utilisateur Active Directory / Samba."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ldap3.abstract.entry import Entry

# Bit ADS_UF_ACCOUNTDISABLE de l'attribut userAccountControl.
_UF_ACCOUNTDISABLE = 0x2


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
class ADUser:
    """Utilisateur du domaine, tel qu'exposé par l'annuaire LDAP.

    Attributes:
        username: Identifiant de connexion (``sAMAccountName``).
        display_name: Nom affiché de l'utilisateur (``displayName`` / ``cn``).
        email: Adresse e-mail principale (``mail``), vide si absente.
        enabled: ``True`` si le compte est activé (non désactivé dans AD).
        dn: Distinguished Name complet de l'entrée LDAP.
        groups: Noms des groupes dont l'utilisateur est membre (``memberOf``).
    """

    username: str
    display_name: str
    email: str
    enabled: bool
    dn: str
    groups: tuple[str, ...] = ()

    @classmethod
    def from_ldap_entry(cls, entry: Entry) -> ADUser:
        """Construit un :class:`ADUser` depuis une entrée ``ldap3``.

        Args:
            entry: Entrée ``ldap3`` exposant ``entry_dn`` et
                ``entry_attributes_as_dict``.

        Returns:
            L'utilisateur correspondant.
        """
        attrs: dict[str, list[object]] = dict(entry.entry_attributes_as_dict)
        uac = _first(attrs, "userAccountControl", "0")
        try:
            enabled = not (int(uac) & _UF_ACCOUNTDISABLE)
        except ValueError:
            enabled = True
        return cls(
            username=_first(attrs, "sAMAccountName"),
            display_name=_first(attrs, "displayName") or _first(attrs, "cn"),
            email=_first(attrs, "mail"),
            enabled=enabled,
            dn=str(entry.entry_dn),
            groups=tuple(str(group) for group in attrs.get("memberOf") or ()),
        )
