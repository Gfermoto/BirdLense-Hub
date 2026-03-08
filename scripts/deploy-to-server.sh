#!/bin/bash
# Deploy BirdLense to remote server
set -e

HOST="${DEPLOY_HOST:-192.168.1.11}"
USER="${DEPLOY_USER:-root}"
REMOTE_DIR="/opt/birdlense"
LOCAL_APP="/home/gfer/BirdLense/app"

# SSH/rsync options
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
RSYNC_EXCLUDE="--exclude=node_modules --exclude=__pycache__ --exclude=.git --exclude=data/recordings"

# Get password if SSHPASS not set
if [ -z "$SSHPASS" ]; then
    echo "SSHPASS not set. Enter SSH password for ${USER}@${HOST}:"
    read -s SSHPASS
    export SSHPASS
fi

echo "=== 1. Syncing app to ${USER}@${HOST}:${REMOTE_DIR} ==="
sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "mkdir -p ${REMOTE_DIR}"
(cd "${LOCAL_APP}" && tar czf - . --exclude=node_modules --exclude='*__pycache__*' --exclude=.git --exclude=data/recordings 2>/dev/null) | \
  sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "cd ${REMOTE_DIR} && tar xzf -"

echo "=== 2. Building on server ==="
sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "cd ${REMOTE_DIR} && docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -f docker-compose.server.yml build"

echo "=== 3. Starting containers ==="
sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "cd ${REMOTE_DIR} && cp -f configs/env.server .env 2>/dev/null || true"
sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "cd ${REMOTE_DIR} && docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -f docker-compose.server.yml up -d"

echo "=== 4. Verifying ==="
sleep 5
sshpass -e ssh $SSH_OPTS ${USER}@${HOST} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'birdlense|NAMES'"
echo ""
echo "UI: http://${HOST}:8085"
curl -s -o /dev/null -w "HTTP %{http_code}" "http://${HOST}:8085" && echo " - UI accessible" || echo " - UI check failed"
