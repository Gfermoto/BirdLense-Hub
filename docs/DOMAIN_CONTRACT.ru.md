# Доменный контракт BirdLense Hub

[English](./DOMAIN_CONTRACT.md)

---

Этот документ фиксирует минимальные инварианты продукта, без которых BirdLense нельзя считать воспроизводимым инструментом для наблюдений и гражданской науки.

## Главные сущности

| Сущность | Смысл | Источник правды |
|----------|-------|-----------------|
| `motion event` | Событие, которое будит цикл записи | processor motion detector / MQTT |
| `recording session` | Один цикл `motion -> capture -> finalize` | `app/processor/src/recording_session.py` |
| `clip` / `Video` | Физический файл записи + строка в БД | `video.mp4` + `Video` |
| `VideoSpecies` | Нормализованная детекция внутри конкретного клипа | `app/web/models.py` |
| `SpeciesVisit` | Логическое присутствие вида во времени, возможно поверх нескольких клипов | `app/web/services/visit_processor.py` |
| `review-only detection` | Детекция, которую можно показать человеку, но нельзя считать визитом | `visit_eligible = false` |
| `SpeciesTaxon` | Каноническая запись вида | `species_taxon` |
| `SpeciesAlias` | Любое историческое/локализованное имя, ведущее к taxon | `species_alias` |

## Временные уровни

BirdLense различает три времени:

1. `trigger-time` — когда сработал motion source и началась запись.
2. `clip-time` — физические границы файла `video.mp4`.
3. `visit-time` — окно логического присутствия вида после дедупликации.

Эти уровни **не обязаны совпадать**, но должны быть объяснимы.

## Инварианты записи и визитов

- Один `Video` может содержать несколько `VideoSpecies`.
- Один `SpeciesVisit` может объединять детекции из нескольких `Video`.
- `review-only detection` **не создаёт** `SpeciesVisit`.
- `VideoSpecies.species_visit_id is NULL` для review-only строки — это ожидаемое состояние, а не ошибка.
- Осиротевший `SpeciesVisit` без связанных `VideoSpecies` — это нарушение инварианта и кандидат на repair.
- Если два клипа одного вида идут почти без разрыва, это считается кандидатом на проверку раздробления записи.

## Инварианты auto-decision

Каждая финальная гипотеза после processor pipeline обязана иметь:

- `decision_kind`
- `decision_reason`
- `accepted`
- `visit_eligible`
- `notification_eligible`
- `trust_band`
- объяснение cross-source evidence (`audio_evidence`, arbitration / fusion markers при наличии)

Результат обязан попадать в один из трёх классов:

- `auto-accept` — допустим для визита и статистики;
- `review-only` — видим человеку, но не считается визитом;
- `reject` — остаётся только в trace/логике, не должен молча превращаться в визит.

Если перекрывающиеся species-гипотезы остаются в сильном конфликте и победитель не доказан
multi-source consensus, pipeline обязан понизить их до одной `review-only` generic bird строки,
а не тихо оставлять несколько конкурирующих `visit_eligible` видов.

## Инварианты каталога видов

- `Species` — UI-строка и историческая совместимость.
- `SpeciesTaxon` — каноническая сущность.
- `SpeciesAlias` — слой нормализации.
- Два разных UI-имени могут существовать только если это осознанно разные сущности, а не случайная локализация/исторический хвост.
- Любое новое неразрешённое имя попадает в `SpeciesUnresolvedName`.

## Базовые quality metrics

Срез доступен через `GET /api/ui/system/domain-health`:

- `orphaned_visits`
- `visit_species_mismatches`
- `duplicate_name_group_count`
- `large_gap_visits`
- `review_only_video_detections`
- `unresolved_species_names`
- `duplicate_clip_candidates_24h`

Это не «косметика», а рабочий baseline для стабилизации продукта.

## Что считается нормой

- review-only строки есть, но они объяснимы и не попадают в визиты;
- unresolved names редки и triage-пригодны;
- duplicate clip candidates существуют только как явные edge-cases, а не как массовый паттерн;
- любой спорный кейс можно восстановить через `decision_trace` и системные health-срезы.
