# Architecture — Fenix Server

## Vue d'ensemble

```
┌─────────────────────────────────────────────┐
│              KDE Plasma (Wayland)            │
│                                             │
│  ┌───────────────┐  ┌──────────────────┐   │
│  │ server-manager│  │   ad-manager     │   │
│  │  (dashboard + │  │ (users, groupes, │   │
│  │  rôles)       │  │  domaine)        │   │
│  └──────┬────────┘  └────────┬─────────┘   │
│         │                    │              │
│  ┌──────┴────────────────────┴──────────┐  │
│  │         core/ (lib partagée)         │  │
│  │  ThemeManager | PolkitClient         │  │
│  │  DBusHelper   | RoleRegistry         │  │
│  └──────┬────────────────────┬──────────┘  │
└─────────┼────────────────────┼─────────────┘
          │ D-Bus               │ D-Bus
          ▼                     ▼
   ┌─────────────┐       ┌─────────────────┐
   │   Polkit    │       │   Services      │
   │  (auth)     │       │  Samba / Kea    │
   └─────────────┘       │  PackageKit     │
                         │  systemd        │
                         └─────────────────┘
```

## core/ — lib partagée

### PolkitClient (core/polkit.py)
Wrapper autour de `org.freedesktop.PolicyKit1.Authority`.
```python
# Usage type dans une app
from core.polkit import PolkitClient

polkit = PolkitClient()
if polkit.check_authorization("org.fenixserver.ad.create-user"):
    # faire l'action privilégiée
```

### DBusHelper (core/dbus_helper.py)
Connexion aux services système via dasbus.
```python
from core.dbus_helper import get_system_bus

bus = get_system_bus()
packagekit = bus.get_proxy("org.freedesktop.PackageKit", "/org/freedesktop/PackageKit")
```

### ThemeManager (core/theme.py)
Thème Fenix Server : dark/light, couleurs, icônes.
Toutes les apps importent uniquement depuis ThemeManager — jamais de styles hardcodés.

### RoleRegistry (core/roles.py)
Registre des rôles disponibles/actifs.
Chaque rôle est défini dans un fichier JSON : `roles/<role>.json`

## Patterns D-Bus/Polkit

### Pattern standard pour une action privilégiée
```python
# 1. Vérifier Polkit AVANT toute action
# 2. Obtenir le bus système
# 3. Appeler le service D-Bus
# 4. Gérer les erreurs D-Bus proprement

def create_ad_user(self, username: str) -> bool:
    if not self.polkit.check_authorization("org.fenixserver.ad.create-user"):
        raise PermissionError("Action refusée par Polkit")
    
    try:
        result = self.samba_dbus.CreateUser(username)
        return result
    except DBusError as e:
        logger.error(f"D-Bus error: {e}")
        return False
```

### Actions Polkit — nomenclature
```
org.fenixserver.<module>.<action>
ex:
  org.fenixserver.ad.create-user
  org.fenixserver.ad.delete-user
  org.fenixserver.update.install-system
  org.fenixserver.update.install-service
```

## Backends des services

| App | Service Linux | Interface D-Bus |
|---|---|---|
| AD Manager | Samba 4 | `samba-tool` wrappé + LDAP |
| Update Manager (système) | PackageKit | `org.freedesktop.PackageKit` |
| Update Manager (services) | GitHub API + systemd | REST + `org.freedesktop.systemd1` |
| Bootstrap (LUKS) | systemd-cryptenroll | `systemd-cryptenroll` CLI |
| Bootstrap (homes) | systemd-homed | `org.freedesktop.home1` |

## Bootstrap — flux d'installation

```
1. Vérification prérequis
   ├── OS : Debian 13 (lecture /etc/os-release)
   ├── CPU : x86-64, ≥2 cœurs
   ├── RAM : ≥4 GB
   ├── Disque : ≥20 GB libre
   └── TPM 2.0 : optionnel (tpm2-tools)

2. Installation KDE Wayland
   apt install kde-plasma-desktop sddm
   (forcé Wayland via /etc/sddm.conf.d/)

3. Installation des dépendances Fenix
   pip install -r requirements.txt
   apt install samba packagekit python3-dasbus

4. Activation systemd-homed (si TPM détecté)
   systemctl enable --now systemd-homed
```
