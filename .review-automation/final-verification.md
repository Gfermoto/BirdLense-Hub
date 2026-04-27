# Final verification

## UI lint

> birdlense-ui@0.3.7 lint
> eslint . --quiet


## UI typecheck

> birdlense-ui@0.3.7 typecheck
> tsc -p tsconfig.app.json --noEmit


## UI tests
...(32 lines)
      Tests  33 passed (33)
   Start at  15:02:45
   Duration  8.57s (transform 3.16s, setup 5.19s, collect 23.03s, tests 7.51s, environment 12.22s, prepare 3.52s)
[lean-ctx: 588→75 tok, -87%]
...(6 lines)
stderr | src/components/Navigation.test.tsx > Navigation > shows species and recordings entry points for editable users
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.
[lean-ctx: 309→156 tok, -50%]

## UI build
...(65 lines)
precache  48 entries (2118.08 KiB)
files generated
  dist/sw.js
[lean-ctx: 1424→25 tok, -98%]

## UI audit
found 0 vulnerabilities

## UI coverage
...(210 lines)
 ui/src/utils      |   22.95 |    33.33 |      25 |   22.95 |
  timeUtils.ts     |   22.95 |    33.33 |      25 |   22.95 | ...24,39-68,72-81
-------------------|---------|----------|---------|---------|-------------------
[lean-ctx: 5621→84 tok, -99%]
...(6 lines)
stderr | src/components/Navigation.test.tsx > Navigation > shows species and recordings entry points for editable users
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.
[lean-ctx: 309→156 tok, -50%]

## Python Ruff
 Container birdlense-redis  Running
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
All checks passed!
318 files already formatted
