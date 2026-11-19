#!/usr/bin/env bash
# Sobe a stack de desenvolvimento inteira num terminal só: `make dev`.
# Infra no Docker (Postgres, Redis) + API, worker e frontend no host, com os logs
# prefixados ([api], [worker], [front]). Ctrl+C derruba os três (a infra continua:
# `make down` para parar).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

command -v uv >/dev/null || { echo "uv não encontrado: veja 'Dependência obrigatória: uv' no README"; exit 1; }
command -v npm >/dev/null || { echo "npm não encontrado: instale o Node.js"; exit 1; }
[ -f .env ] || { echo "falta o .env: cp .env.example .env"; exit 1; }

set -a; . ./.env; set +a  # portas (API_PORT...) iguais às que a API vai usar
API_PORT="${API_PORT:-8010}"
for porta in "$API_PORT" 5173; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$porta") 2>/dev/null; then
    echo "a porta $porta já está em uso (outra API/frontend rodando?): pare antes de rodar make dev"
    exit 1
  fi
done

[ -d frontend/node_modules ] || (cd frontend && npm install)
docker compose up -d --wait db redis
uv run interiores banco atualizar

cor() { printf '\033[%sm[%s]\033[0m' "$1" "$2"; }
rodar() {  # rodar <nome> <cor> <comando...>
  local nome=$1 c=$2; shift 2
  local prefixo; prefixo="$(cor "$c" "$nome") "
  ( "$@" 2>&1 | while IFS= read -r linha; do printf '%s%s\n' "$prefixo" "$linha"; done ) &
}

parar() {
  trap '' INT TERM EXIT  # ignora o próprio sinal do kill 0 abaixo
  echo; echo "parando api, worker e frontend..."
  kill 0 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap parar INT TERM EXIT
rodar api 36 uv run interiores-api
rodar worker 35 uv run interiores-worker
rodar front 32 bash -c 'cd frontend && exec npx vite --port 5173'

echo "$(cor 1 dev) API http://localhost:$API_PORT/docs · tela http://localhost:5173 · Ctrl+C para parar"
wait -n  # se um cair, derruba os outros (o trap do EXIT)
