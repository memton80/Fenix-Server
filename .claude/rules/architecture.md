# Règles d'architecture — Fenix Server

## Isolation des apps
- Chaque app (ad-manager, update-manager, server-manager) est **standalone**
- Les apps n'importent JAMAIS entre elles
- Seul `core/` est importable par toutes les apps
- Si du code est utilisé par 2+ apps → il va dans `core/`

## D-Bus — règles strictes
- Utiliser `dasbus` uniquement (pas dbus-python, pas gi.repository.Gio pour D-Bus)
- Toujours se connecter au **system bus** (pas session bus) pour les services système
- Toujours vérifier la disponibilité du service avant d'appeler
```python
# BIEN
from core.dbus_helper import get_system_bus, service_available

if not service_available("org.freedesktop.PackageKit"):
    raise RuntimeError("PackageKit non disponible")
bus = get_system_bus()

# INTERDIT
import subprocess
subprocess.run(["apt", "install", ...])  # JAMAIS
```

## Polkit — règles strictes
- Toute action qui modifie le système DOIT passer par Polkit
- La vérification Polkit se fait AVANT toute action, jamais après
- Les fichiers `.policy` sont dans `<app>/polkit/org.fenixserver.<module>.policy`
- Format de l'action ID : `org.fenixserver.<module>.<verb>-<objet>`

## systemd-homed et TPM
- Vérifier la présence du TPM avant toute opération TPM
- Les opérations homed passent par `org.freedesktop.home1` D-Bus
- LUKS/TPM via `systemd-cryptenroll` appelé en subprocess (cas exceptionnel autorisé)
- Toujours traiter le TPM comme optionnel — l'app doit fonctionner sans

## Samba / AD
- Ne jamais parser la sortie de `samba-tool` — utiliser LDAP direct (python-ldap)
- Connexion LDAP via `ldap3` (pas python-ldap)
- Le domaine et l'IP du DC sont lus depuis `/etc/samba/smb.conf`

## Wayland
- Pas de `QX11EmbedContainer` ni d'appels xcb
- Pas de `DISPLAY` env var dans le code
- Utiliser `QPA_PLATFORM=wayland` si besoin de forcer en dev
