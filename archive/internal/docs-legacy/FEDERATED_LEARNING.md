# Federated learning prototype (#375)

**Not production.** Security review required before any real multi-site gradient upload.

## Threat model (Phase 1)

- **Poisoning:** malicious clients skewing FedAvg — mitigations TBD (trimmed mean, robust agg, anomaly detection).
- **Version skew:** incompatible model shapes — enforce contract + semver on weights.
- **Privacy:** differential privacy / secure aggregation — future work; raw gradients are sensitive.

## Runnable simulation

```bash
pip install numpy
python3 scripts/federated/simulate_fedavg.py --clients 5 --seed 0
```

Toy **linear regression** split across clients vs pooled OLS — demonstrates FedAvg-style averaging of local estimators. See JSON field `disclaimer`.

## Phase 2

Opt-in channel only; no default in product until reviewed.
