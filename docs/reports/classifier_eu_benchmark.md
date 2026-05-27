# Сравнительный бенчмарк классификаторов (EU)

**Дата:** 2026-05-27 · **Клип:** `storm_bird.mp4` · **Кропов:** 20

| Engine | Backend | ms/crop | top1 | conf | EU-релевантность |
|--------|---------|---------|------|------|----------------|
| **birder_eu** | openvino | **91** | Unknown Bird | 0.05 | 707 EU, есть Eurasian jay в таксономии |
| birder_eu | torch | 113 | Unknown Bird | 0.05 | то же |
| efficientnet_b2 | openvino | 24 | LAUGHING GULL | 0.98 | **не EU** (ложная уверенность) |
| efficientnet_b2 | torch | 42 | LAUGHING GULL | 0.98 | **не EU** |

**Вывод:** для европейской кормушки Birder — правильный выбор по таксономии; EfficientNet на том же кропе даёт американскую чайку с 98% — типичный провал global-525.

Полный JSON: `classifier_eu_benchmark.json`
