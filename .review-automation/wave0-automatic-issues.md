# Wave 0: automatic checks

Generated: 2026-04-27

## 1. Python Ruff (CI scope: app/web + app/processor/src)
 Container birdlense-redis  Running
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
All checks passed!
318 files already formatted

## 2. UI ESLint

> birdlense-ui@0.3.7 lint
> eslint . --quiet


## 3. UI TypeScript

> birdlense-ui@0.3.7 typecheck
> tsc -p tsconfig.app.json --noEmit


## 4. UI Prettier check
Checking formatting...
[warn] src/api/api.tsx
[warn] src/api/queryKeys.ts
[warn] src/App.routes.test.tsx
[warn] src/App.tsx
[warn] src/components/FeedCard.tsx
[warn] src/components/Navigation.tsx
[warn] src/components/VisitCard.tsx
[warn] src/contexts/ProtectedAreaContext.tsx
[warn] src/pages/Favorites/FavoritesPage.test.tsx
[warn] src/pages/Favorites/index.tsx
[warn] src/pages/FoodManagement/index.tsx
[warn] src/pages/Library/DatasetExportsCard.tsx
[warn] src/pages/Library/LibraryCardShell.tsx
[warn] src/pages/Settings/sections/CaptureFeederSection.tsx
[warn] src/pages/Settings/sections/GeneralSection.tsx
[warn] src/pages/Settings/sections/MotionLegacyMirrorBlock.tsx
[warn] src/pages/Settings/sections/NotificationsSection.tsx
[warn] src/pages/Settings/sections/processor/ProcessorBirdnetExtendedBlock.tsx
[warn] src/pages/Settings/sections/processor/ProcessorFrigateFusionBlock.tsx
[warn] src/pages/Settings/shared/scalesIntegrationFields.tsx
[warn] src/pages/SpeciesDirectory/index.tsx
[warn] src/pages/SpeciesDirectory/SpeciesDirectoryPage.test.tsx
[warn] src/pages/System/CatalogRepairCard.tsx
[warn] src/pages/System/ConfigAuditCard.tsx
[warn] src/pages/System/DatabaseMaintenanceCard.tsx
[warn] src/pages/System/ObservabilityCard.tsx
[warn] src/pages/System/ProcessorWeightsCard.tsx
[warn] src/pages/System/RecognitionImprovementCard.tsx
[warn] src/pages/System/RecordingsNasMirrorCard.tsx
[warn] src/pages/System/Retention/RetentionPolicy.tsx
[warn] src/pages/System/StorageOverview.tsx
[warn] src/pages/System/SystemHero.tsx
[warn] src/pages/System/SystemMonitor.tsx
[warn] src/pages/System/SystemReadinessCard.tsx
[warn] src/pages/Timeline/index.tsx
[warn] src/pages/Timeline/Timeline.test.tsx
[warn] src/pages/Timeline/TimelinePage.test.tsx
[warn] src/pages/Unknowns/index.tsx
[warn] src/pages/VideoDetails/DetectedSpecies.tsx
[warn] src/pages/VideoDetails/index.tsx
[warn] src/pages/VideoDetails/VideoInfo.tsx
[warn] Code style issues found in 41 files. Run Prettier with --write to fix.

## 5. Secret scan
gitleaks/trufflehog not installed; fallback rg scan
Command 'rg' not found, but can be installed with:
sudo snap install ripgrep  # version 12.1.0, or
sudo apt  install ripgrep  # version 14.0.3-1
See 'snap info ripgrep' for additional versions.

## 6. npm audit (UI)
1 vulnerabilities: 1 moderate
[lean-ctx: 89→6 tok, -93%]
[lean-ctx: full output -> /home/gfer/.lean-ctx/tee/2026-04-27_143127_npm_audit_--audit-level_moderate.log (redacted, 24h TTL)]

## 7. npm audit (E2E)
found 0 vulnerabilities

## 8. pip-audit (web + processor requirements)
 Container birdlense-redis  Running
WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
No known vulnerabilities found, 1 ignored
