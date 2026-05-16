# Публичный / VPS-контур записей (единый чеклист)

Канонический контур для **вынесенного в интернет** BirdLense Hub: как файлы выходят из контейнера, что делает nginx и как **`/api/ui/videos/:id/stream`** сочетается с **`BIRDLENSE_STRICT_API_AUTH`**.

[English](../user/public-recordings.md)

---

## Два слоя отдачи

1. **Nginx (статика):** опциональный `location` для **`/data/recordings/`** → `alias` на диск. Если блок есть, URL вида `/data/recordings/YYYY/MM/DD/HHMMSS/video.mp4` работают **без** сессии Flask (только HTTP).
2. **Flask (политика в приложении):** **`GET /api/ui/videos/<id>/stream`** отдаёт те же файлы через **`send_file`**, с Range и опцией **`general.require_auth_for_video_stream`**.

Остальные **`/data/*`** (БД, датасет, кэш) статикой **не** отдаются — см. [SECURITY.ru.md §3](./security.ru.md).

---

## Рекомендуемый baseline (публичный VPS)

Совместно; соответствует [Roadmap #418 A2](https://github.com/Gfermoto/BirdLense-Hub/issues/423).

| Шаг | Настройка | Зачем |
|-----|-----------|--------|
| 1 | **`BIRDLENSE_HIDE_DIRECT_RECORDINGS=1`** в **`app/.env`** | Не добавляется nginx-`location` для **`/data/recordings/`** (см. [CONFIGURATION.ru.md](./configuration.ru.md)). Анонимный предсказуемый **`GET /data/recordings/...`** → **403**. Воспроизведение — **`/api/ui/videos/:id/stream`**. |
| 2 | **`BIRDLENSE_STRICT_API_AUTH=1`** + [прод-гейты](https://github.com/Gfermoto/BirdLense-Hub/blob/main/AGENTS.md#production-gates) | Закрывает изменяющие **`/api/ui/*`**; многие read-only GET дашборда остаются публичными по [ACCESS_CONTROL.ru.md](./access-control.ru.md). |
| 3 | *(Опционально)* **`general.require_auth_for_video_stream: true`** | В обработчике стрима нужны Contributor/Admin (или эквивалент), даже если strict-middleware пропускает префикс **`GET /api/ui/videos/*`** — если гостям нельзя забирать MP4 по API. |

Подстановка: **`BIRDLENSE_HIDE_DIRECT_RECORDINGS`** применяется при старте контейнера (`app/scripts/entrypoint.sh`, плейсхолдер **`__RECORDINGS_LOCATION_BLOCK__`** в `app/nginx/standalone.conf.template`).

---

## Альтернативы (не дефолтный чеклист)

- **LAN / лаборатория:** можно оставить прямую раздачу recordings (поведение по умолчанию).
- **Allowlist по IP для `/data/recordings/`:** `app/nginx/examples/recordings_allowlist.conf.snippet` — аккуратно с **`entrypoint.sh`** или внешним прокси.
- **Только внешний reverse proxy на `/api/…`**, **`auth_request`** — интеграция оператора, не образ «из коробки».

Угрозы и расширенные варианты — в [SECURITY.ru.md §3](./security.ru.md); **эта страница** — операторский SSOT «что включить».

---

## Проверка

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/recordings/2099/01/01/120000/video.mp4"
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/db/birdlense.db"
curl -sS -o /dev/null -w "%{http_code}\n" "http://YOUR_HOST:8085/data/../.env"
```

Поведение стрима — от **`require_auth_for_video_stream`** и сессии; проверяйте в браузере после входа.

---

## См. также

- [DEPLOY_SERVER.ru.md §8](./deploy-server.ru.md)  
- [CONFIGURATION.ru.md](./configuration.ru.md)  
- [ACCESS_CONTROL.ru.md](./access-control.ru.md)  
