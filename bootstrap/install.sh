#!/usr/bin/env bash
#
# install.sh — installation de Fenix Server sur Debian 13 (Trixie).
#
# Vérifie les prérequis, installe KDE Plasma Wayland + SDDM, les dépendances
# système et Python, et la policy Polkit. À lancer en root :
#
#     sudo bootstrap/install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# --- présentation ----------------------------------------------------------

if [[ -t 1 ]]; then
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
else
    RED=""; GREEN=""; YELLOW=""; BOLD=""; RESET=""
fi

SUMMARY=()
FAILURES=0

ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; SUMMARY+=("${GREEN}✓${RESET} $1"); }
ko()   { printf '  %s✗%s %s\n' "$RED" "$RESET" "$1"; SUMMARY+=("${RED}✗${RESET} $1"); FAILURES=$((FAILURES + 1)); }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$1"; SUMMARY+=("${YELLOW}!${RESET} $1"); }
step() { printf '\n%s== %s ==%s\n' "$BOLD" "$1" "$RESET"; }

require_root() {
    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        printf '%sCe script doit être lancé en root (sudo bootstrap/install.sh).%s\n' "$RED" "$RESET" >&2
        exit 1
    fi
}

# --- prérequis -------------------------------------------------------------

check_os() {
    if [[ ! -r /etc/os-release ]]; then
        ko "OS : /etc/os-release introuvable"
        return
    fi
    # shellcheck disable=SC1091
    . /etc/os-release
    if [[ ${ID:-} == "debian" && ${VERSION_ID:-} == "13" ]]; then
        ok "OS : Debian 13 (${PRETTY_NAME:-Debian 13})"
    else
        ko "OS : Debian 13 requis (détecté : ${PRETTY_NAME:-${ID:-inconnu} ${VERSION_ID:-?}})"
    fi
}

check_ram() {
    local mem_kb
    mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
    if [[ -n "$mem_kb" ]] && (( mem_kb >= 4000000 )); then
        ok "RAM : $((mem_kb / 1024)) MiB (≥ 4 GB)"
    else
        ko "RAM : ≥ 4 GB requis (détecté : $(( ${mem_kb:-0} / 1024 )) MiB)"
    fi
}

check_cpu() {
    local arch cores
    arch="$(uname -m)"
    if [[ "$arch" == "x86_64" ]]; then
        ok "CPU : architecture x86-64"
    else
        ko "CPU : architecture x86-64 requise (détectée : $arch)"
    fi

    cores="$(nproc)"
    if (( cores >= 2 )); then
        ok "CPU : $cores cœurs (≥ 2)"
    else
        ko "CPU : ≥ 2 cœurs requis (détecté : $cores)"
    fi
}

check_tpm() {
    if compgen -G "/sys/class/tpm/tpm*" > /dev/null; then
        ok "TPM 2.0 : détecté"
    else
        warn "TPM 2.0 : absent — le chiffrement TPM (LUKS/homed) sera indisponible (non bloquant)"
    fi
}

# --- installation ----------------------------------------------------------

install_kde() {
    export DEBIAN_FRONTEND=noninteractive
    if apt-get update -qq && apt-get install -y kde-plasma-desktop sddm; then
        ok "KDE Plasma + SDDM installés"
    else
        ko "Échec de l'installation de KDE Plasma / SDDM"
    fi
}

configure_sddm_wayland() {
    local conf="/etc/sddm.conf.d/wayland.conf"
    if mkdir -p /etc/sddm.conf.d && cat > "$conf" <<'EOF'
[General]
DisplayServer=wayland
EOF
    then
        ok "SDDM forcé en Wayland ($conf)"
    else
        ko "Échec de la configuration Wayland de SDDM"
    fi
}

install_system_deps() {
    export DEBIAN_FRONTEND=noninteractive
    if apt-get install -y python3-pip packagekit python3-dasbus; then
        ok "Dépendances système installées (python3-pip, packagekit, python3-dasbus)"
    else
        ko "Échec de l'installation des dépendances système"
    fi
}

install_python_deps() {
    local req="$PROJECT_ROOT/requirements.txt"
    if [[ ! -f "$req" ]]; then
        ko "requirements.txt introuvable ($req)"
        return
    fi
    # Debian 13 applique PEP 668 (environnement géré) : installation système
    # assumée pour un serveur dédié Fenix.
    if pip3 install --break-system-packages -r "$req"; then
        ok "Dépendances Python installées (requirements.txt)"
    else
        ko "Échec de l'installation des dépendances Python"
    fi
}

install_polkit_policies() {
    local dest="/usr/share/polkit-1/actions"
    local count=0
    mkdir -p "$dest"
    shopt -s nullglob
    local policy
    for policy in "$PROJECT_ROOT"/*/polkit/org.fenixserver.*.policy; do
        if cp "$policy" "$dest/"; then
            count=$((count + 1))
            printf '     → %s\n' "$(basename "$policy")"
        fi
    done
    shopt -u nullglob
    if (( count > 0 )); then
        ok "Policy Polkit installée(s) : $count fichier(s) vers $dest"
    else
        ko "Aucune policy Polkit trouvée à installer"
    fi
}

# Installe l'entrée de menu .desktop d'une app et son lanceur dédié.
# Args : <dossier_app> <fichier.desktop> <nom_lanceur>
install_one_desktop_entry() {
    local app="$1" desktop_file="$2" launcher_name="$3"
    local app_dir="$PROJECT_ROOT/$app"
    local src="$app_dir/$desktop_file"
    local launcher="/usr/local/bin/$launcher_name"
    local dest_dir="/usr/share/applications"
    local dest="$dest_dir/$desktop_file"
    if [[ ! -f "$src" ]]; then
        ko "Fichier .desktop introuvable ($src)"
        return
    fi

    # Lanceur dédié : le dépôt n'est pas packagé, on porte ici le cwd de l'app
    # et le PYTHONPATH vers la racine (pour importer `core`). Évite les
    # caractères réservés interdits dans la clé Exec d'un .desktop.
    if cat > "$launcher" <<EOF
#!/usr/bin/env bash
cd "$app_dir" || exit 1
exec env PYTHONPATH="$PROJECT_ROOT" python3 main.py
EOF
    then
        chmod 755 "$launcher"
    else
        ko "Échec de la création du lanceur ($launcher)"
        return
    fi

    mkdir -p "$dest_dir"
    if cp "$src" "$dest"; then
        chmod 644 "$dest"
        ok "Entrée de menu installée ($dest) + lanceur ($launcher)"
    else
        ko "Échec de l'installation de l'entrée de menu ($desktop_file)"
    fi
}

install_desktop_entries() {
    install_one_desktop_entry "update-manager" "fenix-update-manager.desktop" "fenix-update-manager"
    install_one_desktop_entry "server-manager" "fenix-server-manager.desktop" "fenix-server-manager"
    install_one_desktop_entry "ad-manager" "fenix-ad-manager.desktop" "fenix-ad-manager"
}

# --- configuration du domaine AD (Samba) -----------------------------------

install_samba() {
    export DEBIAN_FRONTEND=noninteractive
    if apt-get install -y samba samba-common-bin smbclient; then
        ok "Samba installé (samba, samba-common-bin, smbclient)"
    else
        ko "Échec de l'installation de Samba"
    fi
}

# Demande interactivement le domaine, le realm et le mot de passe admin (deux
# fois), provisionne le domaine AD puis active le service samba-ad-dc.
provision_samba_ad() {
    if ! command -v samba-tool > /dev/null 2>&1; then
        ko "Provisionnement AD ignoré : samba-tool introuvable (Samba non installé)"
        return
    fi

    local domain realm adminpass adminpass_confirm
    read -r -p "    Nom de domaine court (ex: FENIX) : " domain
    read -r -p "    Realm FQDN (ex: FENIX.LOCAL) : " realm
    while true; do
        read -r -s -p "    Mot de passe administrateur : " adminpass
        printf '\n'
        read -r -s -p "    Confirmer le mot de passe : " adminpass_confirm
        printf '\n'
        if [[ "$adminpass" == "$adminpass_confirm" ]]; then
            break
        fi
        warn "Les mots de passe ne correspondent pas — nouvelle saisie"
    done

    # samba-tool refuse d'écraser un smb.conf existant : on le sauvegarde.
    if [[ -f /etc/samba/smb.conf ]]; then
        mv /etc/samba/smb.conf "/etc/samba/smb.conf.bak.$(date +%Y%m%d%H%M%S)"
    fi

    if samba-tool domain provision \
        --use-rfc2307 \
        --realm="$realm" \
        --domain="$domain" \
        --adminpass="$adminpass"; then
        ok "Domaine AD provisionné (realm $realm, domaine $domain)"
    else
        ko "Échec du provisionnement du domaine AD"
        return
    fi

    if systemctl enable --now samba-ad-dc; then
        ok "Service samba-ad-dc activé et démarré"
    else
        ko "Échec de l'activation de samba-ad-dc"
    fi
}

# --- résumé ----------------------------------------------------------------

print_summary() {
    step "Résumé"
    local line
    for line in "${SUMMARY[@]}"; do
        printf '  %s\n' "$line"
    done
    printf '\n'
    if (( FAILURES > 0 )); then
        printf '%sInstallation incomplète : %d étape(s) en échec.%s\n' "$RED" "$FAILURES" "$RESET"
    else
        printf '%sInstallation terminée avec succès. Redémarrez pour démarrer sous SDDM/Wayland.%s\n' \
            "$GREEN" "$RESET"
    fi
}

# --- enchaînement ----------------------------------------------------------

main() {
    require_root

    printf '%sFenix Server — installation%s\n' "$BOLD" "$RESET"

    step "Vérification des prérequis"
    check_os
    check_ram
    check_cpu
    check_tpm

    if (( FAILURES > 0 )); then
        print_summary
        exit 1
    fi

    step "Installation de KDE Plasma Wayland + SDDM"
    install_kde
    configure_sddm_wayland

    step "Installation des dépendances système"
    install_system_deps

    step "Installation des dépendances Python"
    install_python_deps

    step "Installation de la policy Polkit"
    install_polkit_policies

    step "Installation des entrées de menu (.desktop)"
    install_desktop_entries

    step "Configuration du domaine AD"
    install_samba
    provision_samba_ad

    print_summary
    (( FAILURES == 0 ))
}

main "$@"
