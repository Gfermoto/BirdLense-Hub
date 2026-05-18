# Labelling Guide

## Open `/labelling`

1. Open Hub UI.
2. Go to `http://<host>:8085/labelling`.
3. You should see queue cards with:
   - media preview (video tracklet),
   - `Main` and `Shadow` predictions,
   - actions: `Confirm Behavior`, `Reject Box`, `Tag Species`.

## If Queue Is Empty

Run one of:

```bash
# automatic miner
curl -X POST "http://<host>:8085/api/ui/labelling/cases/mine" -H "Content-Type: application/json" --cookie "<session_cookie>"
```

or seed from existing DB:

```bash
cd /path/to/BirdLense
python3 scripts/seed_labelling_queue.py --db app/data/db/birdlense.db
```

On production host:

```bash
cd /root/BirdLense
python3 scripts/seed_labelling_queue.py --db app/data/db/birdlense.db --max-video-cases 150 --max-runtime-cases 150
```

## Main vs Shadow

- `Main` — production decision used by current pipeline (`engine: meta` by default).
- `Shadow` — background Behavior v2 candidate. Logged for comparison, does not affect production decisions while shadow mode is active.
- Goal: collect operator feedback and compare `Main` vs `Shadow` before rollout switch.

## Recommended Operator Flow

1. Watch media preview.
2. Click `Confirm Behavior` with correct behavior tag.
3. If bbox is wrong, click `Reject Box`.
4. If species is wrong, apply `Tag Species`.
5. Export approved data from `/labelling` when enough reviewed cases accumulated.
