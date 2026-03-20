# Участие в разработке BirdLense Hub

Спасибо за интерес к проекту BirdLense Hub.

## Как участвовать

1. **Сделайте fork** репозитория и создайте ветку от `dev`.
2. **Вносите изменения** — следуйте существующему стилю кода.
3. **Тестируйте** — перед отправкой выполните `make test-web` в `app/`.
4. **Отправьте Pull Request** в ветку `dev`.

**Вторая пара глаз:** для защищённых веток желательно одобрение другого человека. См. [docs/GOVERNANCE.ru.md](docs/GOVERNANCE.ru.md) — как добавить наблюдателя на GitHub и почему ИИ не может принять приглашение collaborator.

## Настройка окружения

```bash
git clone https://github.com/YOUR_USER/BirdLense-Hub.git
cd BirdLense-Hub/app
make build
make start
```

Подробнее: [docs/LOCAL_DEV.ru.md](docs/LOCAL_DEV.ru.md).

## Документация

- **Индекс:** [docs/README.ru.md](docs/README.ru.md) — структура (запуск / интеграции / разработка).
- **Текст для читателей и статей:** [docs/OVERVIEW.ru.md](docs/OVERVIEW.ru.md).
- **Правила оформления:** [docs/Documentation.ru.md](docs/Documentation.ru.md). **Термины:** [docs/GLOSSARY.ru.md](docs/GLOSSARY.ru.md).
- Изменение поведения для пользователя → обновить соответствующий гайд и [CHANGELOG.md](CHANGELOG.md).

## Стиль кода

- **Python:** PEP 8, по возможности type hints.
- **TypeScript/React:** ESLint, Prettier (конфиг проекта).
- **Документация:** Markdown, короткие блоки и таблицы; placeholders (`YOUR_HOST`, `your-token`) вместо реальных значений.

## Требования к Pull Request

- Один PR — одна фича или исправление.
- Добавляйте тесты для новых API и логики процессора.
- Обновляйте документацию при изменении поведения.
- `make test-web` должен проходить.

## Сообщение об ошибках

- Используйте GitHub Issues.
- Уязвимости безопасности: [SECURITY.md](SECURITY.md).

## Вопросы

**[GitHub Discussions](https://github.com/Gfermoto/BirdLense-Hub/discussions)** — для вопросов и идей; **Issues** — для багов и конкретных задач.

## Good first issue

Ищите задачи с меткой **`good first issue`**. Мейнтейнерам: в таком issue укажите файлы, критерии готовности и ссылки на `docs/LOCAL_DEV.ru.md` / `docs/TESTING.ru.md`.

## Сообщество

- **Discussions:** https://github.com/Gfermoto/BirdLense-Hub/discussions  
- **Безопасность:** только по [SECURITY.md](SECURITY.md), не в открытых тредах.
