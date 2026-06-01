"""Modèle d'enregistrement DNS Samba AD."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Types d'enregistrements gérés par le DNS Manager.
RECORD_TYPES = ("A", "AAAA", "CNAME", "PTR")

# Ligne « Name=<nom>, Records=... » d'un bloc de la sortie ``samba-tool dns query``.
_NAME_RE = re.compile(r"^\s*Name=(?P<name>[^,]*),")
# Ligne « <TYPE>: <data> (flags=..., ...) » d'un enregistrement.
_RECORD_RE = re.compile(r"^\s*(?P<rtype>[A-Z]+):\s+(?P<data>\S+)")


@dataclass(frozen=True)
class DnsRecord:
    """Enregistrement DNS d'une zone.

    Attributes:
        name: Nom relatif de l'enregistrement dans la zone (``@`` pour la
            racine de la zone).
        record_type: Type d'enregistrement (``A``, ``AAAA``, ``CNAME``, ``PTR``).
        data: Donnée de l'enregistrement (adresse IP, nom cible, ...).
        zone: Nom de la zone à laquelle l'enregistrement appartient.
    """

    name: str
    record_type: str
    data: str
    zone: str

    @classmethod
    def parse_query(cls, output: str, zone: str) -> list[DnsRecord]:
        """Parse la sortie de ``samba-tool dns query`` pour une zone.

        Args:
            output: Sortie standard de la commande ``dns query``.
            zone: Nom de la zone interrogée (rattaché à chaque enregistrement).

        Returns:
            Les enregistrements des types gérés (cf. :data:`RECORD_TYPES`).
        """
        records: list[DnsRecord] = []
        current = "@"
        for line in output.splitlines():
            name_match = _NAME_RE.match(line)
            if name_match is not None:
                current = name_match.group("name") or "@"
                continue
            record_match = _RECORD_RE.match(line)
            if record_match is None:
                continue
            rtype = record_match.group("rtype")
            if rtype not in RECORD_TYPES:
                continue
            records.append(
                cls(
                    name=current,
                    record_type=rtype,
                    data=record_match.group("data"),
                    zone=zone,
                )
            )
        return records
