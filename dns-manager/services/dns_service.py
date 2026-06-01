"""Opérations DNS du DNS Manager via ``samba-tool dns``.

Toutes les opérations (lecture des zones/enregistrements comme ajout/suppression)
sont déléguées à ``samba-tool dns`` exécuté via ``pkexec`` (même approche que
``ad_service`` avec ``samba-tool user`` / ``role_service`` avec ``systemctl``) :
l'élévation et l'autorisation sont gérées par pkexec/Polkit, sans vérification
Polkit explicite dans le code.

Le serveur visé est le contrôleur de domaine local (``127.0.0.1``). L'authentification
auprès de ``samba-tool`` se fait avec les identifiants saisis au démarrage
(``LoginDialog``), injectés dans chaque commande via ``-U <user>%<password>``.

Conformément aux règles d'architecture, la sortie de ``samba-tool`` n'est pas
parsée pour l'AD/LDAP ; ici le parsing concerne uniquement ``dns zonelist`` /
``dns query``, pour lesquels ``samba-tool dns`` est le backend imposé (pas
d'équivalent LDAP direct exploitable simplement).
"""

from __future__ import annotations

import logging
import subprocess

from models.dns_record import DnsRecord
from models.dns_zone import DnsZone

logger = logging.getLogger(__name__)

# Contrôleur de domaine local visé par samba-tool dns.
DNS_SERVER = "127.0.0.1"

# Pseudo-nom désignant la racine d'une zone.
_ZONE_ROOT = "@"


class DnsService:
    """Expose les opérations DNS (zones, enregistrements A/CNAME/PTR)."""

    def __init__(
        self, server: str = DNS_SERVER, *, username: str = "", password: str = ""
    ) -> None:
        """Initialise le service DNS.

        Args:
            server: Adresse du serveur DNS Samba visé (DC local par défaut).
            username: Utilisateur AD pour l'authentification ``samba-tool``
                (option ``-U``). Vide pour s'appuyer sur l'authentification par
                défaut (compte machine / Kerberos).
            password: Mot de passe associé à ``username``.
        """
        self._server = server
        self._username = username
        self._password = password

    def _credentials_args(self) -> list[str]:
        """Construit les arguments d'authentification ``samba-tool`` (``-U``).

        Returns:
            ``["-U", "<user>%<password>"]`` si un utilisateur est défini, sinon
            une liste vide (authentification par défaut).
        """
        if not self._username:
            return []
        return ["-U", f"{self._username}%{self._password}"]

    def _run_samba_dns(self, *args: str) -> str:
        """Exécute ``pkexec samba-tool dns <args>`` (opération privilégiée).

        L'élévation et l'autorisation sont assurées par ``pkexec`` (Polkit) ;
        aucune vérification Polkit explicite n'est faite ici.

        Args:
            args: Arguments passés à ``samba-tool dns`` (ex.
                ``("zonelist", server)``).

        Returns:
            La sortie standard de la commande.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        command = ["pkexec", "samba-tool", "dns", *args, *self._credentials_args()]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            # On ne journalise que la sous-commande (args[:2]) : les identifiants
            # passés via -U ne sont jamais inclus dans le log.
            operation = " ".join(args[:2])
            logger.error(
                "samba-tool dns %s a échoué: code=%s stderr=%s",
                operation,
                exc.returncode,
                exc.stderr,
            )
            raise RuntimeError(f"Commande samba-tool dns échouée: {operation}") from exc
        return result.stdout

    # --- zones ------------------------------------------------------------

    def list_zones(self) -> list[DnsZone]:
        """Retourne la liste des zones DNS hébergées par le DC.

        Returns:
            Les :class:`DnsZone` déclarées sur le serveur.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        output = self._run_samba_dns("zonelist", self._server)
        return DnsZone.parse_zonelist(output)

    # --- enregistrements --------------------------------------------------

    def list_records(self, zone: str) -> list[DnsRecord]:
        """Retourne les enregistrements gérés d'une zone.

        Args:
            zone: Nom de la zone à interroger.

        Returns:
            Les :class:`DnsRecord` de type A/AAAA/CNAME/PTR de la zone.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        output = self._run_samba_dns("query", self._server, zone, _ZONE_ROOT, "ALL")
        return DnsRecord.parse_query(output, zone)

    def add_record(self, zone: str, name: str, record_type: str, data: str) -> DnsRecord:
        """Ajoute un enregistrement à une zone via ``samba-tool dns add``.

        Args:
            zone: Nom de la zone cible.
            name: Nom relatif de l'enregistrement (``@`` pour la racine).
            record_type: Type d'enregistrement (``A``, ``CNAME``, ``PTR``, ...).
            data: Donnée de l'enregistrement (IP, nom cible, ...).

        Returns:
            L'enregistrement créé.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        self._run_samba_dns("add", self._server, zone, name, record_type, data)
        return DnsRecord(name=name, record_type=record_type, data=data, zone=zone)

    def delete_record(self, zone: str, name: str, record_type: str, data: str) -> None:
        """Supprime un enregistrement d'une zone via ``samba-tool dns delete``.

        Args:
            zone: Nom de la zone cible.
            name: Nom relatif de l'enregistrement.
            record_type: Type d'enregistrement (``A``, ``CNAME``, ``PTR``, ...).
            data: Donnée de l'enregistrement à supprimer.

        Raises:
            RuntimeError: si la commande ``samba-tool`` échoue.
        """
        self._run_samba_dns("delete", self._server, zone, name, record_type, data)
