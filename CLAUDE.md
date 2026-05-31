# Fenix Server

Suite de gestion serveur Linux avec l'UX de Windows Server, tournant sur Debian 13 + KDE Wayland.

## Concept
Chaque "rôle" (service Linux) a une app KDE dédiée.
Un Server Manager central active/désactive les rôles.
Les apps parlent aux services système via D-Bus + Polkit. Jamais en root direct.

## Stack technique
- **Language** : Python 3.12+ avec PySide6 (Qt 6)
- **IPC** : D-Bus (dasbus) + Polkit pour les opérations privilégiées
- **OS cible** : Debian 13 (Trixie) uniquement, KDE Plasma Wayland
- **Services** :
  - Samba 4 → AD Manager
  - PackageKit (D-Bus) → Update Manager (MAJ système)
  - GitHub Releases API → Update Manager (MAJ services)
- **Chiffrement** : systemd-cryptenroll (LUKS+TPM) + systemd-homed (homes chiffrés)

## Structure du projet
```
fenix-server/
├── core/            # lib PySide6 partagée (thème, D-Bus helpers, Polkit wrappers)
├── server-manager/  # app principale : dashboard + activation des rôles
├── ad-manager/      # gestion AD/Samba (users, groupes, domaine)
├── update-manager/  # MAJ système (PackageKit) + MAJ services (GitHub)
└── bootstrap/       # script d'install (vérif prérequis + KDE)
```

## Commandes clés
```bash
# Lancer une app en dev
cd <app>/ && python main.py

# Installer les dépendances
pip install -r requirements.txt

# Lancer les tests
pytest tests/ -v

# Vérifier le style
ruff check .
```

## Règles absolues
- JAMAIS subprocess pour appeler apt — utiliser l'API D-Bus PackageKit
- TOUTES les opérations privilégiées passent par Polkit (voir core/polkit.py)
- Wayland uniquement — zéro code de fallback X11
- Chaque app est standalone — pas d'import croisé entre apps (core/ seulement)
- Les opérations TPM passent par systemd-cryptenroll ou systemd-homed uniquement
- Voir ARCHITECTURE.md pour les patterns D-Bus/Polkit à respecter
