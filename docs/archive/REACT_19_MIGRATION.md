# Миграция на React 19 — анализ рисков и план

**Дата:** 16 марта 2026  
**Текущая версия:** React 18.3.1  
**Целевая:** React 19.x

---

## 1. Анализ зависимостей

| Пакет | Текущая | React 19 | Риск |
|-------|---------|----------|------|
| **MUI** (material, x-charts, x-date-pickers, x-tree-view) | 6.x | ✅ Поддержка с Dec 2024 | Низкий |
| **@tanstack/react-query** | 5.61 | ✅ Полная поддержка | Низкий |
| **@vitejs/plugin-react** | 4.3.1 | ✅ Поддержка | Низкий |
| **react-i18next** | 15.1 | ✅ v15.2+ исправлены типы | Низкий |
| **react-router-dom** | 6.22 | ✅ Без известных проблем | Низкий |
| **@emotion/react, styled** | 11.13 | ✅ Совместимы | Низкий |

---

## 2. Аудит кодовой базы

### 2.1 Паттерны, требующие внимания

| Паттерн | Найдено | React 19 | Действие |
|---------|---------|----------|----------|
| `React.FC` | 14 компонентов | ✅ Работает | Без изменений |
| `forwardRef` | 0 | — | — |
| `PropTypes` / `defaultProps` | 0 | Удалены в R19 | — |
| Legacy Context | 0 | Удалён | — |
| `createRoot` | 1 (main.tsx) | API без изменений | — |
| `<Trans components={}>` | 0 | Key warning в i18next | — |

### 2.2 Структура (47 .tsx файлов)

- Контексты: `ProtectedAreaContext`, `QueryClientProvider`
- Роутинг: React Router v6
- Формы: @tanstack/react-form
- UI: MUI 6, Emotion

---

## 3. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Ошибки типов TypeScript** | Средняя | Низкое | Обновить @types/react@^19 |
| **HMR useEffect** не перезапускается при hot reload | Низкая | Только dev | Известный баг, не влияет на prod |
| **MUI ref/forwardRef** | Низкая | MUI обновлён | — |
| **Ошибки в Error Boundary** | Низкая | Логирование | R19 не re-throw, использовать onUncaughtError при необходимости |
| **Регрессии в редких сценариях** | Низкая | Среднее | E2E после миграции |

---

## 4. План миграции

1. **Подготовка:** создать ветку, бэкап package-lock
2. **Зависимости:** `react@^19`, `react-dom@^19`, `@types/react@^19`, `@types/react-dom@^19`
3. **Сборка:** `npm run build` — проверить ошибки
4. **Линтер:** `npm run lint`
5. **Dev-сервер:** `npm run dev` — ручная проверка
6. **E2E:** `cd app/e2e && npx playwright test` (если есть)
7. **Docker build:** `make build` в app/

---

## 5. Откат

При критических проблемах:
```bash
git checkout app/ui/package.json app/ui/package-lock.json
cd app/ui && npm install
```

---

## 6. Результат миграции (16.03.2026)

| Проверка | Статус |
|----------|--------|
| npm install | ✅ (legacy-peer-deps для @mui/lab) |
| npm run build | ✅ |
| npx tsc --noEmit | ✅ |
| npm run dev | ✅ |
| make build (Docker) | ✅ |

**Установлено:** react@19.2.4, react-dom@19.2.4, @types/react@^19, @types/react-dom@^19

**Изменения:**
- `app/ui/package.json` — react, react-dom, @types
- `app/Dockerfile` — `npm install --legacy-peer-deps`
- `app/ui/.npmrc` — `legacy-peer-deps=true`

---

## 7. Ссылки

- [React 19 Upgrade Guide](https://react.dev/blog/2024/04/25/react-19-upgrade-guide)
- [MUI React 19 Update](https://mui.com/blog/react-19-update)
- [TanStack Query React 19](https://github.com/TanStack/query/pull/8405)
