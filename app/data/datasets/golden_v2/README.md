# Golden Dataset v2

- `manifest.synthetic.json` — CI Golden Gate (committed).
- `manifest.json` — generated on prod via `make generate-golden-v2` (not committed when empty).

```bash
python3 scripts/generate_golden_dataset_v2.py --db app/data/db/birdlense.db --days 7
make validate-pipeline-golden
```
