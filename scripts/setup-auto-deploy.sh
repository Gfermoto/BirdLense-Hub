#!/bin/bash
# Однократная настройка автодеплоя через GitHub Actions.
# Запустить на сервере BirdLense (192.168.1.11).
#
# Делает:
# 1. Клонирует репозиторий (если нет)
# 2. Устанавливает GitHub Actions runner
# 3. Регистрирует runner
#
# После настройки: push в main → автодеплой. Никаких ручных действий.

set -e

REPO="${REPO:-Gfermoto/BirdLense-Hub}"
DEPLOY_DIR="${DEPLOY_DIR:-/root/BirdLense}"
RUNNER_DIR="${RUNNER_DIR:-/root/actions-runner}"

echo "=== Настройка автодеплоя ==="
echo "Репозиторий: $REPO"
echo "Деплой в: $DEPLOY_DIR"
echo ""

# 1. Клонировать репозиторий
if [ ! -d "$DEPLOY_DIR/.git" ]; then
  echo "1. Клонирование репозитория..."
  mkdir -p "$(dirname "$DEPLOY_DIR")"
  git clone "https://github.com/${REPO}.git" "$DEPLOY_DIR"
  cd "$DEPLOY_DIR/app"
  [ -f .env ] || (echo "PROCESSOR_SECRET=$(openssl rand -hex 16)" > .env && echo "Создан app/.env с PROCESSOR_SECRET")
  make pull
  echo "   Готово. Первый запуск выполнен."
else
  echo "1. Репозиторий уже есть в $DEPLOY_DIR"
fi

# 2. Установить runner
if [ ! -f "$RUNNER_DIR/run.sh" ]; then
  echo ""
  echo "2. Установка GitHub Actions runner..."
  mkdir -p "$RUNNER_DIR"
  cd "$RUNNER_DIR"
  curl -sL https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz | tar xz
  echo "   Скачано."
else
  echo "2. Runner уже установлен"
fi

echo ""
echo "3. Регистрация runner"
echo "   Нужен токен: GitHub → Repo → Settings → Actions → Runners → New self-hosted runner"
echo "   Скопируй команду ./config.sh --url ... --token ..."
echo ""
read -p "Введи токен (или Enter чтобы пропустить): " TOKEN

if [ -n "$TOKEN" ]; then
  cd "$RUNNER_DIR"
  ./config.sh --url "https://github.com/${REPO}" --token "$TOKEN" --labels birdlense --work _work
  ./svc.sh install
  ./svc.sh start
  echo "   Runner установлен как сервис."
else
  echo "   Запусти вручную:"
  echo "   cd $RUNNER_DIR"
  echo "   ./config.sh --url https://github.com/${REPO} --token <TOKEN> --labels birdlense"
  echo "   ./svc.sh install && ./svc.sh start"
fi

echo ""
echo "=== Готово ==="
echo "Push в main → автодеплой."
echo "Ручной запуск: GitHub → Actions → Deploy → Run workflow"
