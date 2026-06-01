#!/usr/bin/env bash
#
# install.sh — installation de Fenix Server sur Debian 13 (Trixie).
#
# Vérifie les prérequis, installe KDE Plasma Wayland + SDDM, les dépendances
# système et Python, et la policy Polkit. À lancer en root :
#
#     sudo bootstrap/install.sh
#
# Interface 100 % ANSI pur (ni whiptail ni dialog) : couleurs, bannière ASCII,
# barres de progression Unicode et encadrés box-drawing. Tout est désactivé
# automatiquement si la sortie n'est pas un terminal interactif.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# --- présentation : couleurs et capacités terminal -------------------------

if [[ -t 1 ]]; then
    INTERACTIVE=1
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
    CYAN=$'\033[36m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
    INTERACTIVE=0
    RED=""; GREEN=""; YELLOW=""; CYAN=""; BOLD=""; DIM=""; RESET=""
fi

# tput n'est utilisé que pour la largeur et le curseur, et seulement en mode
# interactif avec un TERM défini.
TPUT_OK=0
if [[ $INTERACTIVE -eq 1 && -n "${TERM:-}" ]] && command -v tput > /dev/null 2>&1; then
    TPUT_OK=1
fi

term_cols() {
    if [[ $TPUT_OK -eq 1 ]]; then
        tput cols 2> /dev/null || printf '80'
    else
        printf '80'
    fi
}

cursor_hide() { [[ $TPUT_OK -eq 1 ]] && tput civis 2> /dev/null || true; }
cursor_show() { [[ $TPUT_OK -eq 1 ]] && tput cnorm 2> /dev/null || true; }

SUMMARY=()
FAILURES=0
WARNINGS=0

# --- bannière ASCII art ----------------------------------------------------

print_banner() {
    local cols centered pad line
    cols="$(term_cols)"

    # "FENIX" en police bloc (ANSI Shadow), largeur 37 colonnes par ligne.
    local -a art=(
        '███████╗███████╗███╗   ██╗██╗██╗  ██╗'
        '██╔════╝██╔════╝████╗  ██║██║╚██╗██╔╝'
        '█████╗  █████╗  ██╔██╗ ██║██║ ╚███╔╝ '
        '██╔══╝  ██╔══╝  ██║╚██╗██║██║ ██╔██╗ '
        '██║     ███████╗██║ ╚████║██║██╔╝ ██╗'
        '╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝'
    )
    local art_width=37

    pad=$(( (cols - art_width) / 2 ))
    (( pad < 0 )) && pad=0
    printf -v centered '%*s' "$pad" ''

    printf '\n'
    for line in "${art[@]}"; do
        printf '%s%s%s%s\n' "$centered" "$BOLD$CYAN" "$line" "$RESET"
    done

    # Sous-titre "S E R V E R" centré sous la bannière.
    local subtitle='S E R V E R'
    pad=$(( (cols - ${#subtitle}) / 2 ))
    (( pad < 0 )) && pad=0
    printf -v centered '%*s' "$pad" ''
    printf '%s%s%s%s\n' "$centered" "$DIM" "$subtitle" "$RESET"

    local tagline='Installation — Debian 13 · KDE Plasma Wayland'
    pad=$(( (cols - ${#tagline}) / 2 ))
    (( pad < 0 )) && pad=0
    printf -v centered '%*s' "$pad" ''
    printf '%s%s%s%s\n\n' "$centered" "$DIM" "$tagline" "$RESET"
}

# --- encadrés box-drawing pour les sections --------------------------------

INNER_WIDTH=56

box_line() {
    # Construit une ligne d'INNER_WIDTH fois le caractère passé en argument.
    local ch="$1" i out=''
    for ((i = 0; i < INNER_WIDTH; i++)); do out+="$ch"; done
    printf '%s' "$out"
}

step() {
    local title="$1" clen pad spaces top
    top="$(box_line '═')"

    # ${#title} compte les caractères (locale UTF-8) : padding fiable même
    # avec des accents, contrairement à %-*s qui compte les octets.
    clen=${#title}
    pad=$(( INNER_WIDTH - 2 - clen ))
    (( pad < 0 )) && pad=0
    printf -v spaces '%*s' "$pad" ''

    printf '\n%s╔%s╗%s\n' "$BOLD$CYAN" "$top" "$RESET"
    printf '%s║%s %s%s%s%s %s║%s\n' \
        "$BOLD$CYAN" "$RESET" "$BOLD" "$title" "$RESET" "$spaces" "$BOLD$CYAN" "$RESET"
    printf '%s╚%s╝%s\n' "$BOLD$CYAN" "$top" "$RESET"
}

# --- comptes rendus d'étape ------------------------------------------------

ok()   { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; SUMMARY+=("${GREEN}✓${RESET} $1"); }
ko()   { printf '  %s✗%s %s\n' "$RED" "$RESET" "$1"; SUMMARY+=("${RED}✗${RESET} $1"); FAILURES=$((FAILURES + 1)); }
warn() { printf '  %s⚠%s %s\n' "$YELLOW" "$RESET" "$1"; SUMMARY+=("${YELLOW}⚠${RESET} $1"); WARNINGS=$((WARNINGS + 1)); }

# --- barre de progression --------------------------------------------------

PROGRESS_WIDTH=42

draw_progress() {
    # draw_progress <label> <pourcentage>
    local label="$1" pct="$2" filled empty bar='' i
    filled=$(( pct * PROGRESS_WIDTH / 100 ))
    (( filled > PROGRESS_WIDTH )) && filled=$PROGRESS_WIDTH
    empty=$(( PROGRESS_WIDTH - filled ))
    for ((i = 0; i < filled; i++)); do bar+='█'; done
    for ((i = 0; i < empty; i++)); do bar+='░'; done
    printf '\r  %s%s%s [%s%s%s] %3d%%' \
        "$CYAN" "$label" "$RESET" "$GREEN" "$bar" "$RESET" "$pct"
}

# run_with_progress <label> <commande...>
# Exécute la commande en tâche de fond et anime une barre qui se remplit en
# temps réel. En l'absence de progression réelle (apt/pip), la barre tend
# progressivement vers 95 %, puis saute à 100 % au succès. Retourne le code
# de sortie de la commande. En cas d'échec, affiche les dernières lignes de log.
run_with_progress() {
    local label="$1"; shift
    local logf rc=0
    logf="$(mktemp)"

    # Sans terminal interactif : exécution simple, sans animation.
    if [[ $INTERACTIVE -eq 0 ]]; then
        "$@" > "$logf" 2>&1 || rc=$?
        if (( rc != 0 )); then
            sed 's/^/      /' "$logf" | tail -n 10
        fi
        rm -f "$logf"
        return $rc
    fi

    "$@" > "$logf" 2>&1 &
    local pid=$!

    cursor_hide
    local pct=0
    while kill -0 "$pid" 2> /dev/null; do
        # Approche asymptotique de 95 % : remplissage visible et continu.
        (( pct < 95 )) && pct=$(( pct + (95 - pct + 9) / 10 ))
        draw_progress "$label" "$pct"
        sleep 0.2
    done
    wait "$pid" || rc=$?

    if (( rc == 0 )); then
        draw_progress "$label" 100
    fi
    printf '\n'
    cursor_show

    if (( rc != 0 )); then
        printf '  %s── détail de l'\''erreur ──%s\n' "$DIM" "$RESET"
        sed 's/^/      /' "$logf" | tail -n 10
    fi
    rm -f "$logf"
    return $rc
}

require_root() {
    if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
        printf '%s✗ Ce script doit être lancé en root (sudo bootstrap/install.sh).%s\n' \
            "$RED$BOLD" "$RESET" >&2
        exit 1
    fi
}

# --- saisie masquée de mot de passe ----------------------------------------

# read_password <prompt> <nom_variable>
# Lit un mot de passe en affichant un '*' par caractère, gère le retour arrière.
read_password() {
    local prompt="$1" __var="$2" pass='' char
    printf '%s' "$prompt"
    while IFS= read -r -s -n1 char; do
        # Entrée (chaîne vide) → fin de saisie.
        [[ -z "$char" ]] && break
        if [[ "$char" == $'\177' || "$char" == $'\b' ]]; then
            if [[ -n "$pass" ]]; then
                pass="${pass%?}"
                printf '\b \b'
            fi
        else
            pass+="$char"
            printf '*'
        fi
    done
    printf '\n'
    printf -v "$__var" '%s' "$pass"
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
    if run_with_progress "KDE Plasma + SDDM" \
        bash -c 'apt-get update -qq && apt-get install -y kde-plasma-desktop sddm'; then
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
    # Sur Debian 13, policykit-1 est obsolète : remplacé par polkitd + pkexec.
    if run_with_progress "Dépendances système" \
        apt-get install -y python3-pip packagekit python3-dasbus polkitd pkexec; then
        ok "Dépendances système installées (python3-pip, packagekit, python3-dasbus, polkitd, pkexec)"
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
    if run_with_progress "Paquets Python (pip)" \
        pip3 install --break-system-packages -r "$req"; then
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
            printf '     %s→%s %s\n' "$DIM" "$RESET" "$(basename "$policy")"
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

    # Policy Polkit de l'AD Manager (create/modify/delete user & group).
    local ad_policy="$PROJECT_ROOT/ad-manager/polkit/org.fenixserver.ad.policy"
    local polkit_dir="/usr/share/polkit-1/actions"
    mkdir -p "$polkit_dir"
    if [[ -f "$ad_policy" ]] && cp "$ad_policy" "$polkit_dir/"; then
        ok "Policy Polkit AD Manager installée ($polkit_dir/$(basename "$ad_policy"))"
    else
        ko "Échec de l'installation de la policy Polkit AD Manager"
    fi
}

# --- configuration du domaine AD (Samba) -----------------------------------

install_samba() {
    export DEBIAN_FRONTEND=noninteractive
    if run_with_progress "Samba (AD DC)" \
        apt-get install -y samba samba-common-bin smbclient; then
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
        read_password "    Mot de passe administrateur : " adminpass
        read_password "    Confirmer le mot de passe : " adminpass_confirm
        if [[ "$adminpass" == "$adminpass_confirm" ]]; then
            break
        fi
        warn "Les mots de passe ne correspondent pas — nouvelle saisie"
    done

    # samba-tool refuse d'écraser un smb.conf existant : on le sauvegarde.
    if [[ -f /etc/samba/smb.conf ]]; then
        mv /etc/samba/smb.conf "/etc/samba/smb.conf.bak.$(date +%Y%m%d%H%M%S)"
    fi

    if run_with_progress "Provisionnement du domaine AD" \
        samba-tool domain provision \
            --use-rfc2307 \
            --realm="$realm" \
            --domain="$domain" \
            --adminpass="$adminpass"; then
        ok "Domaine AD provisionné (realm $realm, domaine $domain)"
    else
        ko "Échec du provisionnement du domaine AD"
        return
    fi

    # Séquence recommandée Samba pour un DC : les services membres entrent en
    # conflit avec samba-ad-dc (mêmes ports), il faut les désactiver et démasquer
    # samba-ad-dc avant de l'activer.
    systemctl disable --now smbd nmbd winbind 2> /dev/null || true
    systemctl unmask samba-ad-dc 2> /dev/null || true

    if systemctl enable --now samba-ad-dc; then
        ok "Service samba-ad-dc activé et démarré"
    else
        ko "Échec de l'activation de samba-ad-dc"
    fi

    # Bind LDAP simple sans TLS (utilisé localement par l'AD Manager) : on relâche
    # l'exigence d'authentification forte, puis on redémarre le DC pour l'appliquer.
    if sed -i '/^\[global\]/a\	ldap server require strong auth = no' /etc/samba/smb.conf \
        && systemctl restart samba-ad-dc; then
        ok "smb.conf : 'ldap server require strong auth = no' ajouté + samba-ad-dc redémarré"
    else
        ko "Échec de la configuration 'ldap server require strong auth = no'"
    fi
}

# --- résumé ----------------------------------------------------------------

print_summary() {
    local top line
    top="$(box_line '═')"

    printf '\n%s╔%s╗%s\n' "$BOLD$CYAN" "$top" "$RESET"
    local title="Résumé de l'installation"
    local clen=${#title} pad spaces
    pad=$(( INNER_WIDTH - 2 - clen )); (( pad < 0 )) && pad=0
    printf -v spaces '%*s' "$pad" ''
    printf '%s║%s %s%s%s%s %s║%s\n' \
        "$BOLD$CYAN" "$RESET" "$BOLD" "$title" "$RESET" "$spaces" "$BOLD$CYAN" "$RESET"
    printf '%s╚%s╝%s\n' "$BOLD$CYAN" "$top" "$RESET"

    for line in "${SUMMARY[@]}"; do
        printf '  %s\n' "$line"
    done

    printf '\n'
    local ok_count=$(( ${#SUMMARY[@]} - FAILURES - WARNINGS ))
    printf '  %s✓ %d réussie(s)%s   %s⚠ %d avertissement(s)%s   %s✗ %d échec(s)%s\n\n' \
        "$GREEN" "$ok_count" "$RESET" \
        "$YELLOW" "$WARNINGS" "$RESET" \
        "$RED" "$FAILURES" "$RESET"

    if (( FAILURES > 0 )); then
        printf '%s✗ Installation incomplète : %d étape(s) en échec.%s\n' \
            "$RED$BOLD" "$FAILURES" "$RESET"
    else
        printf '%s✓ Installation terminée avec succès. Redémarrez pour démarrer sous SDDM/Wayland.%s\n' \
            "$GREEN$BOLD" "$RESET"
    fi
}

# --- enchaînement ----------------------------------------------------------

# Restaure le curseur si le script est interrompu pendant une barre de progression.
trap cursor_show EXIT INT TERM

main() {
    require_root

    print_banner

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
