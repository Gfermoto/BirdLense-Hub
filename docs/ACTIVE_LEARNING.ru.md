# Active learning и hard negatives (#369)

[English](./ACTIVE_LEARNING.md)

Фаза 1 — экспорт кандидатов + JSONL манифест + воспроизводимость; UI очереди — фаза 2.

Схема строки манифеста: `scripts/active_learning/pool_entry_v1.schema.json`.  
Шаблон: `scripts/active_learning/emit_pool_template.py`.

Энтропия и margin считаются в `_classify_crop`; агрегаты по треку и флаг `classifier_needs_review` — в `decision_maker` и `decision_trace` при заданных `processor.classifier_uncertainty_entropy_ge` / `processor.classifier_uncertainty_margin_le`. Пороги фиксируйте в доке при выборе значений.

Экспорт JSON `decision_trace` → строки манифеста пула: `scripts/active_learning/decision_trace_to_pool_manifest.py` (кропы — заглушки `_pending/…` до офлайн-экспорта файлов).
