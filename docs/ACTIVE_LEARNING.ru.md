# Active learning и hard negatives (#369)

[English](./ACTIVE_LEARNING.md)

Фаза 1 — экспорт кандидатов + JSONL манифест + воспроизводимость; UI очереди — фаза 2.

Схема строки манифеста: `scripts/active_learning/pool_entry_v1.schema.json`.  
Шаблон: `scripts/active_learning/emit_pool_template.py`.

Точка измерения неопределённости — классификатор в `_classify_crop`; пороги фиксируйте в доке при выборе значений.
