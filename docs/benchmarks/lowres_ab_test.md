# Low-Res Enhance A/B Test

## Inputs
- sharpen=on: TP=182 FP=19 FN=28 TN=411
- sharpen=off: TP=169 FP=14 FN=41 TN=416

## Metrics
| Mode | Precision | Recall | FPR |
|---|---:|---:|---:|
| sharpen=on | 0.9055 | 0.8667 | 0.0442 |
| sharpen=off | 0.9235 | 0.8048 | 0.0326 |

## Delta (on - off)
- precision_delta: -0.0180
- recall_delta: 0.0619
- fpr_delta: 0.0116
