"""Modèle de zone DNS Samba AD."""

from __future__ import annotations

from dataclasses import dataclass

# Préfixe des lignes « pszZoneName » dans la sortie de ``samba-tool dns zonelist``.
_ZONE_NAME_PREFIX = "pszZoneName"


@dataclass(frozen=True)
class DnsZone:
    """Zone DNS hébergée par le contrôleur de domaine.

    Attributes:
        name: Nom de la zone (ex. ``example.lan`` ou ``1.168.192.in-addr.arpa``).
        reverse: ``True`` si la zone est une zone inverse (``in-addr.arpa`` /
            ``ip6.arpa``).
    """

    name: str
    reverse: bool = False

    @classmethod
    def from_name(cls, name: str) -> DnsZone:
        """Construit une :class:`DnsZone` depuis son nom.

        Args:
            name: Nom de la zone.

        Returns:
            La zone, avec ``reverse`` déduit du suffixe du nom.
        """
        lowered = name.lower()
        reverse = lowered.endswith(".in-addr.arpa") or lowered.endswith(".ip6.arpa")
        return cls(name=name, reverse=reverse)

    @classmethod
    def parse_zonelist(cls, output: str) -> list[DnsZone]:
        """Parse la sortie de ``samba-tool dns zonelist``.

        La sortie liste chaque zone par bloc, dont une ligne ``pszZoneName``.

        Args:
            output: Sortie standard de la commande ``dns zonelist``.

        Returns:
            Les zones trouvées, dans l'ordre d'apparition.
        """
        zones: list[DnsZone] = []
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped.startswith(_ZONE_NAME_PREFIX):
                continue
            _, _, value = stripped.partition(":")
            name = value.strip()
            if name:
                zones.append(cls.from_name(name))
        return zones
