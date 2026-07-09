# BirdLense Hub (Orin)

[Русский](./README.ru.md)

Один контейнер для Jetson Orin. Подключается к Go2RTC (отдельно или в Frigate), MQTT (BirdNET, Frigate).

**Модели (ONNX GPU):** Trapper AI детектор, Birder ConvNeXt классификатор, Ornimetrics ReID + Welfare. Весь инференс — ONNX Runtime CUDA EP / TensorRT EP.

## Быстрый старт

```bash
cd app
cp .env.example .env           # отредактировать токены
make build && make start
```

## Makefile

| Команда | Описание |
|---------|----------|
| `make build` | Сборка Docker образа |
| `make start` | Запуск стека |
| `make stop` | Остановка |
| `make logs` | Логи |
| `make verify` | Health check |

Подробнее: [`docs/QUICKSTART.md`](../docs/QUICKSTART.md) · [`docs/INSTALL.md`](../docs/INSTALL.md)

## Структура

```
app/
├── web/            # Flask API (OpenAPI)
├── processor/      # ONNX GPU инференс
├── ui/             # React 19 + MUI (Node 22)
├── data/           # recordings/, db/
└── app_config/     # user_config.yaml
```

## Важно

- UI сборка перед Docker: `cd app/ui && npm run build && cd ..`
- Node.js 22 (см. `app/ui/.nvmrc`)
- NVIDIA runtime обязателен

См. [`docs/`](../docs/index.md).