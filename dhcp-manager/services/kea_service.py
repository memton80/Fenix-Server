"""Opérations DHCP du DHCP Manager via l'API REST du Kea Control Agent.

Les baux et les réservations passent par l'API REST du Kea Control Agent,
écoutant en local sur le port 8000 (accès via la stdlib ``urllib``, même approche
que ``github_service``). Chaque appel envoie une commande JSON
``{"command": ..., "service": ["dhcp4"], "arguments": {...}}`` et lit la réponse.

Les plages (subnets) sont en revanche lues et écrites directement dans
``/etc/kea/kea-dhcp4.conf`` via ``pkexec`` (``cat`` puis ``tee``), suivi d'un
redémarrage de ``kea-dhcp4-server`` : seul le hook ``lease_cmds`` est chargé,
``subnet_cmds`` ne l'est pas.

L'API REST est protégée par authentification HTTP basic : le mot de passe est
généré à l'installation et stocké dans ``/etc/kea/kea-api-password`` en
``600 root:root`` (cf. ``bootstrap/install.sh``). Comme ce fichier n'est lisible
que par root, le DHCP Manager le lit au démarrage via ``pkexec cat`` (pas besoin
d'ajouter l'utilisateur au groupe ``_kea``) et envoie le mot de passe dans
l'en-tête ``Authorization`` de chaque requête.

Le contrôle du service système (démarrer / arrêter / redémarrer ``kea-dhcp4``)
est délégué à ``systemctl`` exécuté via ``pkexec`` (même approche que
``role_service``) : l'élévation et l'autorisation sont gérées par pkexec/Polkit.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import urllib.error
import urllib.request

from models.dhcp_lease import DhcpLease
from models.dhcp_reservation import DhcpReservation
from models.dhcp_subnet import DhcpSubnet

logger = logging.getLogger(__name__)

# Control Agent Kea en écoute locale.
KEA_API_URL = "http://127.0.0.1:8000/"
# Service DHCPv4 ciblé par les commandes de l'API.
KEA_SERVICE = "dhcp4"
# Unité systemd du serveur DHCPv4.
KEA_UNIT = "kea-dhcp4-server"
# Fichier de configuration du serveur DHCPv4 (les plages y sont gérées en direct).
KEA_DHCP4_CONFIG = "/etc/kea/kea-dhcp4.conf"
# Identité utilisée pour l'authentification HTTP basic de l'API REST.
KEA_API_USER = "fenix"
# Fichier contenant le mot de passe de l'API (partagé avec le Control Agent).
KEA_API_PASSWORD_FILE = "/etc/kea/kea-api-password"

_REQUEST_TIMEOUT = 10  # secondes
_CONTENT_TYPE = "application/json"

# Résultat « succès » d'une commande Kea (champ ``result`` de la réponse).
_KEA_SUCCESS = 0
# Actions systemctl autorisées pour le service Kea.
_SERVICE_ACTIONS = ("start", "stop", "restart")


class KeaService:
    """Expose les opérations DHCP (baux, plages, réservations, contrôle service)."""

    def __init__(
        self,
        api_url: str = KEA_API_URL,
        *,
        username: str = KEA_API_USER,
        password: str | None = None,
        password_file: str = KEA_API_PASSWORD_FILE,
    ) -> None:
        """Initialise le service Kea.

        Args:
            api_url: URL du Kea Control Agent (port 8000 local par défaut).
            username: Utilisateur de l'authentification HTTP basic.
            password: Mot de passe de l'API. Si ``None``, il est lu depuis
                ``password_file``.
            password_file: Fichier contenant le mot de passe partagé avec le
                Control Agent (utilisé seulement si ``password`` est ``None``).
        """
        self._api_url = api_url
        self._username = username
        self._password = password if password is not None else self._read_password(password_file)

    @staticmethod
    def _read_password(path: str) -> str:
        """Lit le mot de passe de l'API via ``pkexec cat <path>`` (best-effort).

        Le fichier est en ``600 root:root`` : ``pkexec`` élève les privilèges le
        temps de le lire, sans relâcher ses permissions ni exiger que l'utilisateur
        appartienne au groupe ``_kea``.

        Args:
            path: Chemin du fichier de mot de passe.

        Returns:
            Le mot de passe (espaces/sauts de ligne retirés), ou une chaîne vide
            si la lecture échoue (l'API sera alors appelée sans authentification).
        """
        try:
            result = subprocess.run(
                ["pkexec", "cat", path],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.warning("Lecture du mot de passe API Kea échouée (%s): %s", path, exc)
            return ""
        return result.stdout.strip()

    def _auth_headers(self) -> dict[str, str]:
        """Construit l'en-tête ``Authorization`` (HTTP basic) si possible.

        Returns:
            Un mapping contenant ``Authorization`` si un mot de passe est
            disponible, sinon un mapping vide.
        """
        if not self._password:
            return {}
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode("ascii")
        return {"Authorization": f"Basic {token}"}

    def _command(self, command: str, arguments: dict[str, object] | None = None) -> dict:
        """Envoie une commande à l'API Kea et retourne ses ``arguments``.

        Args:
            command: Nom de la commande Kea (ex. ``"lease4-get-all"``).
            arguments: Arguments de la commande, ou ``None``.

        Returns:
            Le bloc ``arguments`` de la réponse (vide si absent).

        Raises:
            RuntimeError: si l'appel HTTP échoue ou si Kea renvoie une erreur.
        """
        payload: dict[str, object] = {"command": command, "service": [KEA_SERVICE]}
        if arguments is not None:
            payload["arguments"] = arguments
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": _CONTENT_TYPE, **self._auth_headers()}
        request = urllib.request.Request(self._api_url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            logger.error("Appel API Kea '%s' échoué: %s", command, exc)
            raise RuntimeError(f"API Kea injoignable: {command}") from exc

        # L'API renvoie une liste de réponses (une par service ciblé).
        entry = body[0] if isinstance(body, list) and body else body
        if entry.get("result", _KEA_SUCCESS) != _KEA_SUCCESS:
            message = entry.get("text", "erreur inconnue")
            logger.error("Commande Kea '%s' rejetée: %s", command, message)
            raise RuntimeError(f"Commande Kea rejetée: {message}")
        return entry.get("arguments", {})

    # --- baux -------------------------------------------------------------

    def list_leases(self) -> list[DhcpLease]:
        """Retourne les baux DHCP actifs (``lease4-get-all``).

        Returns:
            Les :class:`DhcpLease` connus du serveur.

        Raises:
            RuntimeError: en cas d'erreur d'API.
        """
        arguments = self._command("lease4-get-all")
        leases = arguments.get("leases", [])
        return [DhcpLease.from_kea(lease) for lease in leases]

    # --- plages (gérées dans /etc/kea/kea-dhcp4.conf) ---------------------

    def _read_config(self) -> dict:
        """Lit et parse ``kea-dhcp4.conf`` via ``pkexec cat`` (privilégié).

        Returns:
            La configuration Kea désérialisée (dictionnaire racine).

        Raises:
            RuntimeError: si la lecture ou le parsing JSON échoue.
        """
        try:
            result = subprocess.run(
                ["pkexec", "cat", KEA_DHCP4_CONFIG],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.error("Lecture de %s échouée: %s", KEA_DHCP4_CONFIG, exc)
            raise RuntimeError(f"Lecture de {KEA_DHCP4_CONFIG} échouée") from exc
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            logger.error("JSON invalide dans %s: %s", KEA_DHCP4_CONFIG, exc)
            raise RuntimeError(f"Configuration Kea illisible: {KEA_DHCP4_CONFIG}") from exc

    def _write_config(self, config: dict) -> None:
        """Écrit ``config`` dans ``kea-dhcp4.conf`` puis redémarre le serveur.

        L'écriture passe par ``pkexec tee`` (le contenu est fourni sur l'entrée
        standard), suivie d'un ``pkexec systemctl restart kea-dhcp4-server`` pour
        recharger la configuration.

        Args:
            config: Configuration Kea complète à sérialiser.

        Raises:
            RuntimeError: si l'écriture ou le redémarrage échoue.
        """
        payload = json.dumps(config, indent=2)
        try:
            subprocess.run(
                ["pkexec", "tee", KEA_DHCP4_CONFIG],
                input=payload,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.error("Écriture de %s échouée: %s", KEA_DHCP4_CONFIG, exc)
            raise RuntimeError(f"Écriture de {KEA_DHCP4_CONFIG} échouée") from exc
        self.control_service("restart")

    def list_subnets(self) -> list[DhcpSubnet]:
        """Retourne les plages (subnets) lues dans ``kea-dhcp4.conf``.

        Returns:
            Les :class:`DhcpSubnet` déclarées dans la configuration du serveur.

        Raises:
            RuntimeError: si la lecture du fichier échoue.
        """
        dhcp4 = self._read_config().get("Dhcp4", {})
        subnets = dhcp4.get("subnet4", []) if isinstance(dhcp4, dict) else []
        return [DhcpSubnet.from_kea(subnet) for subnet in subnets]

    def set_subnet(self, subnet: str, pool: str, *, subnet_id: int) -> DhcpSubnet:
        """Crée ou modifie une plage DHCP dans ``kea-dhcp4.conf``.

        La plage existante de même ``subnet_id`` est mise à jour sur place (ses
        autres clés, dont d'éventuelles ``reservations``, sont conservées) ;
        sinon une nouvelle entrée est ajoutée. Le fichier est ensuite réécrit et
        ``kea-dhcp4-server`` redémarré.

        Args:
            subnet: Réseau au format CIDR (ex. ``192.168.1.0/24``).
            pool: Plage d'attribution (ex. ``192.168.1.100-192.168.1.200``).
            subnet_id: Identifiant du subnet à créer ou remplacer.

        Returns:
            La plage telle qu'enregistrée.

        Raises:
            RuntimeError: si la lecture, l'écriture ou le redémarrage échoue.
        """
        config = self._read_config()
        dhcp4 = config.setdefault("Dhcp4", {})
        subnets: list[dict] = dhcp4.setdefault("subnet4", [])
        pools = [{"pool": pool}] if pool else []

        for entry in subnets:
            if int(entry.get("id", 0)) == subnet_id:
                entry["subnet"] = subnet
                entry["pools"] = pools
                break
        else:
            subnets.append({"id": subnet_id, "subnet": subnet, "pools": pools})

        self._write_config(config)
        return DhcpSubnet.from_kea({"id": subnet_id, "subnet": subnet, "pools": pools})

    # --- réservations -----------------------------------------------------

    def list_reservations(self, subnet_id: int) -> list[DhcpReservation]:
        """Retourne les réservations d'un subnet (depuis ``config-get``).

        Args:
            subnet_id: Identifiant du subnet à inspecter.

        Returns:
            Les :class:`DhcpReservation` du subnet.

        Raises:
            RuntimeError: en cas d'erreur d'API.
        """
        arguments = self._command("config-get")
        config = arguments.get("Dhcp4", {})
        subnets = config.get("subnet4", []) if isinstance(config, dict) else []
        for subnet in subnets:
            if int(subnet.get("id", 0)) != subnet_id:
                continue
            return [
                DhcpReservation.from_kea(item, subnet_id)
                for item in subnet.get("reservations", [])
            ]
        return []

    def add_reservation(self, reservation: DhcpReservation) -> DhcpReservation:
        """Ajoute une réservation MAC → IP (``reservation-add``).

        Args:
            reservation: Réservation à enregistrer.

        Returns:
            La réservation enregistrée.

        Raises:
            RuntimeError: en cas d'erreur d'API.
        """
        payload = reservation.to_kea()
        payload["subnet-id"] = reservation.subnet_id
        self._command("reservation-add", {"reservation": payload})
        return reservation

    # --- contrôle du service ---------------------------------------------

    def control_service(self, action: str) -> None:
        """Contrôle l'unité systemd Kea via ``pkexec systemctl`` (privilégié).

        L'élévation et l'autorisation sont assurées par ``pkexec`` (Polkit) ;
        aucune vérification Polkit explicite n'est faite ici.

        Args:
            action: Action systemctl (``start``, ``stop`` ou ``restart``).

        Raises:
            ValueError: si l'action n'est pas supportée.
            RuntimeError: si la commande ``systemctl`` échoue.
        """
        if action not in _SERVICE_ACTIONS:
            raise ValueError(f"Action de service non supportée: {action}")
        command = ["pkexec", "systemctl", action, KEA_UNIT]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "systemctl %s %s a échoué: code=%s stderr=%s",
                action,
                KEA_UNIT,
                exc.returncode,
                exc.stderr,
            )
            raise RuntimeError(f"Commande systemctl échouée (code {exc.returncode})") from exc
