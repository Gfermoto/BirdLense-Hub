# Wave 3: UI report

| Route | Viewport | HTTP | Console warn/error | Page errors | Failed req | FCP ms | Load ms | CLS | Axe violations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `/` | mobile-375 | 200 | 2 | 0 | 1 | 600 | 929 | 0 | 0 |
| `/` | tablet-768 | 200 | 2 | 0 | 1 | 632 | 993 | 0 | 0 |
| `/` | desktop-1280 | 200 | 2 | 0 | 1 | 644 | 1073 | 0 | 0 |
| `/timeline` | mobile-375 | 200 | 4 | 0 | 1 | 688 | 1046 | 0 | 0 |
| `/timeline` | tablet-768 | 200 | 4 | 0 | 1 | 648 | 1115 | 0 | 0 |
| `/timeline` | desktop-1280 | 200 | 4 | 0 | 1 | 652 | 997 | 0 | 0 |
| `/favorites` | mobile-375 | 200 | 4 | 0 | 1 | 672 | 351 | 0 | 0 |
| `/favorites` | tablet-768 | 200 | 4 | 0 | 1 | 580 | 1094 | 0 | 0 |
| `/favorites` | desktop-1280 | 200 | 4 | 0 | 1 | 692 | 1084 | 0 | 0 |
| `/library` | mobile-375 | 200 | 2 | 0 | 1 | 792 | 424 | 0 | 0 |
| `/library` | tablet-768 | 200 | 2 | 0 | 1 | 720 | 362 | 0 | 0 |
| `/library` | desktop-1280 | 200 | 2 | 0 | 1 | 800 | 398 | 0 | 0 |
| `/system` | mobile-375 | 200 | 4 | 0 | 1 | 740 | 1078 | 0 | 0 |
| `/system` | tablet-768 | 200 | 4 | 0 | 1 | 680 | 1054 | 0 | 0 |
| `/system` | desktop-1280 | 200 | 4 | 0 | 1 | 776 | 383 | 0 | 0 |
| `/settings` | mobile-375 | 200 | 4 | 0 | 1 | 784 | 397 | 0 | 0 |
| `/settings` | tablet-768 | 200 | 4 | 0 | 1 | 824 | 418 | 0 | 0 |
| `/settings` | desktop-1280 | 200 | 4 | 0 | 1 | 888 | 433 | 0 | 0 |
| `/species-directory` | mobile-375 | 200 | 4 | 0 | 1 | 832 | 450 | 0 | 0 |
| `/species-directory` | tablet-768 | 200 | 4 | 0 | 1 | 736 | 1137 | 0 | 0 |
| `/species-directory` | desktop-1280 | 200 | 4 | 0 | 1 | 844 | 1275 | 0 | 0 |
| `/live` | mobile-375 | 200 | 2 | 0 | 1 | 812 | 441 | 0 | 0 |
| `/live` | tablet-768 | 200 | 2 | 0 | 1 | 856 | 1370 | 0 | 0 |
| `/live` | desktop-1280 | 200 | 2 | 0 | 1 | 1040 | 535 | 0 | 0 |
| `/` | desktop-api-abort |  | 1 | 0 | 0 |  |  |  |  |

## Notes
- Screenshots: `.review-automation/screenshots/`
- Raw JSON: `.review-automation/logs/ui-review-results.json`
- Lighthouse not run: Chrome lighthouse package is not part of repo; Playwright PerformanceNavigationTiming used as lightweight proxy.
