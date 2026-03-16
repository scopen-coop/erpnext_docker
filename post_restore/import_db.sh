#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT_SCRIPT="${ROOT_DIR}/client"
CLIENTS_DIR="${ROOT_DIR}/clients"
POST_RESTORE_DIR="${ROOT_DIR}/post_restore"

log_info() { echo "[INFO] $*"; }
log_ok() { echo "[OK] $*"; }
log_warn() { echo "[WARN] $*"; }
log_err() { echo "[ERROR] $*"; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || log_err "Commande requise introuvable: $1"
}

usage() {
  cat <<USAGE
Usage:
  ./post_restore/import_db.sh [client] [backup.sql.gz] [site_name]

Comportement:
  - si des arguments manquent, le script te propose des choix interactifs
  - appelle ./client restore <client> <backup> [site]
  - puis exécute (optionnellement) les commandes GreenMail générées par get_mail.sql
USAGE
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  grep -E "^${key}=" "$env_file" | tail -n1 | cut -d= -f2-
}

client_dir() {
  echo "${CLIENTS_DIR}/$1"
}

env_file() {
  echo "$(client_dir "$1")/.env"
}

compose_file() {
  echo "$(client_dir "$1")/docker-compose.yml"
}

ensure_client_exists() {
  local client="$1"
  [[ -f "$(env_file "$client")" && -f "$(compose_file "$client")" ]] || log_err "Client '${client}' introuvable."
}

dc() {
  local client="$1"
  shift
  local project
  project="$(read_env_value "$(env_file "$client")" PROJECT)"
  docker compose -f "$(compose_file "$client")" --env-file "$(env_file "$client")" -p "$project" "$@"
}

select_one() {
  local prompt="$1"
  shift
  local options=("$@")
  local choice

  echo
  echo "$prompt"
  echo
  select choice in "${options[@]}"; do
    if [[ -n "${choice:-}" ]]; then
      echo "$choice"
      return 0
    fi
    echo "Choix invalide"
  done
}

list_clients() {
  local out=()
  local d
  shopt -s nullglob
  for d in "${CLIENTS_DIR}"/*; do
    [[ -d "$d" && -f "$d/.env" && -f "$d/docker-compose.yml" ]] || continue
    out+=("$(basename "$d")")
  done
  shopt -u nullglob
  printf '%s\n' "${out[@]}"
}

list_sites_for_client() {
  local client="$1"
  local sites_dir
  local out=()
  local d

  sites_dir="$(client_dir "$client")/data/sites"
  [[ -d "$sites_dir" ]] || return 0

  shopt -s nullglob
  for d in "$sites_dir"/*; do
    [[ -d "$d" ]] || continue
    case "$(basename "$d")" in
      assets|logs)
        continue
        ;;
    esac
    out+=("$(basename "$d")")
  done
  shopt -u nullglob
  printf '%s\n' "${out[@]}"
}

main() {
  need_cmd docker
  need_cmd jq

  [[ -x "$CLIENT_SCRIPT" ]] || log_err "Script client introuvable ou non exécutable: $CLIENT_SCRIPT"

  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  local client="${1:-}"
  local backup_file="${2:-}"
  local site_name="${3:-}"

  if [[ -z "$client" ]]; then
    mapfile -t clients < <(list_clients)
    (( ${#clients[@]} > 0 )) || log_err "Aucun client trouvé dans ${CLIENTS_DIR}."
    client="$(select_one "Quel client restaurer ?" "${clients[@]}")"
  fi

  ensure_client_exists "$client"

  if [[ -z "$site_name" ]]; then
    site_name="$(read_env_value "$(env_file "$client")" SITE_NAME)"
    if [[ -z "$site_name" ]]; then
      mapfile -t sites < <(list_sites_for_client "$client")
      (( ${#sites[@]} > 0 )) || log_err "Aucun site trouvé pour ${client}."
      site_name="$(select_one "Quel site restaurer ?" "${sites[@]}")"
    fi
  fi

  if [[ -z "$backup_file" ]]; then
    mapfile -t backups < <(find . -maxdepth 1 -type f -name '*.sql.gz' -printf '%f\n' | sort)
    (( ${#backups[@]} > 0 )) || log_err "Aucun fichier .sql.gz trouvé dans $(pwd)."
    backup_file="$(select_one "Quel backup SQL utiliser ?" "${backups[@]}")"
  fi

  [[ -f "$backup_file" ]] || log_err "Backup introuvable: $backup_file"

  log_info "Restore du client '${client}' / site '${site_name}' avec '$backup_file'..."
  "$CLIENT_SCRIPT" restore "$client" "$backup_file" "$site_name"

  local site_cfg db_name db_root_password
  site_cfg="$(client_dir "$client")/data/sites/${site_name}/site_config.json"
  if [[ ! -f "$site_cfg" ]]; then
    log_warn "site_config.json introuvable, skip des étapes GreenMail"
    log_ok "Import terminé."
    exit 0
  fi

  db_name="$(jq -r '.db_name // empty' "$site_cfg")"
  db_root_password="$(read_env_value "$(env_file "$client")" DB_ROOT_PASSWORD)"

  if [[ -z "$db_name" || -z "$db_root_password" ]]; then
    log_warn "Infos DB incomplètes, skip des étapes GreenMail"
    log_ok "Import terminé."
    exit 0
  fi

  if [[ -f "${POST_RESTORE_DIR}/get_mail.sql" ]]; then
    log_info "Création/synchronisation des comptes GreenMail (si service dispo)..."
    while IFS= read -r cmd; do
      [[ -n "${cmd// }" ]] || continue
      bash -lc "$cmd" || true
    done < <(dc "$client" exec -T db sh -lc "mysql -uroot -p\"${db_root_password}\" --batch --skip-column-names \"${db_name}\"" < "${POST_RESTORE_DIR}/get_mail.sql")
  fi

  log_ok "Import terminé avec succès pour ${client}/${site_name}."
}

main "$@"
