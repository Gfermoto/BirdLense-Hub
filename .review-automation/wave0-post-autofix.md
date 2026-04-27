# Wave 0 post-autofix verification

## Prettier check
Checking formatting...
All matched files use Prettier code style!

## npm audit UI
found 0 vulnerabilities

## git diff stat after autofix
 app/ui/package-lock.json                           |  4 +-
 app/ui/src/App.routes.test.tsx                     | 16 +++-
 app/ui/src/App.tsx                                 |  5 +-
 app/ui/src/api/api.tsx                             | 12 +--
 app/ui/src/api/queryKeys.ts                        |  9 ++-
... (33 lines omitted) ...
 app/ui/src/pages/Unknowns/index.tsx                | 14 +++-
 app/ui/src/pages/VideoDetails/DetectedSpecies.tsx  | 26 +++++-
 app/ui/src/pages/VideoDetails/VideoInfo.tsx        | 19 ++++-
 app/ui/src/pages/VideoDetails/index.tsx            |  6 +-
 42 files changed, 427 insertions(+), 139 deletions(-)
[lean-ctx: 738→163 tok, -78%]
