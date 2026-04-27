# Wave 2: tests

## UI vitest
...(31 lines)
      Tests  33 passed (33)
   Start at  14:43:23
   Duration  10.32s (transform 3.27s, setup 6.43s, collect 28.80s, tests 8.32s, environment 13.95s, prepare 3.77s)
[lean-ctx: 569→75 tok, -87%]
...(6 lines)
stderr | src/components/Navigation.test.tsx > Navigation > shows species and recordings entry points for editable users
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.
[lean-ctx: 309→156 tok, -50%]

## Web API pytest (Docker)
docker compose run --rm -v $(pwd):/app -v $(pwd)/..:/workspace birdlense \
	bash -c 'if [ "$TEST_WEB_VERBOSE" = 1 ]; then exec python -m pytest web/tests/ -v; else exec python -m pytest web/tests/ -q --tb=short; fi'
 Container birdlense-redis  Running
........................................................................ [ 14%]
........................................................................ [ 28%]
........................................................................ [ 42%]
........................................................................ [ 56%]
........................................................................ [ 70%]
........................................................................ [ 85%]
........................................................................ [ 99%]
....                                                                     [100%]
508 passed in 110.38s (0:01:50)

## Processor light tests (Docker)
docker compose run --rm -e SKIP_HEAVY_PROCESSOR_TESTS=1 -v $(pwd):/app -v $(pwd)/..:/workspace birdlense \
	bash -c 'export PYTHONPATH=/app:/app/web:/app/processor/src SKIP_HEAVY_PROCESSOR_TESTS=1 && \
	python -m pytest processor/tests/ -q --tb=short -m "not heavy"'
 Container birdlense-redis  Running
.................................................................s.....s [ 29%]
........................................................................ [ 59%]
........................................................................ [ 89%]
..........................                                               [100%]
240 passed, 2 skipped in 19.64s
