# Six-month plan, success criteria and stop criteria

One idea is developed (I1), one is prepared (I2), the others stay in reserve. I1 is developed as thesis B (central) with branch A (complementary, capped); its gates B-S, B1 (against the public model B1b), B2 and B3 are defined in the I1 card of `IDEAS.md`. The ranking weighs conditional PnL, data cost and time to a first signal, not potential alone: I3 has the highest conditional potential but the most expensive data, so it moves up as soon as a transaction panel is available.

Each gate ends in one of three outcomes, written in advance: promising, inconclusive or stop. Inconclusive is not a pass.

| Period | Work | Gate |
|---|---|---|
| Month 1 | B-S at hub level (Sentinel-1 phase data, SLC, or a vendor trial against the pilot); B1 against the public model B1b; CL1-CL2 quotes; A capped; I2 in parallel on free data. | **Gate 1** (end of month 1): a weekly physical variable that beats the public nowcast out of sample (B-S, B1). Otherwise B stops and I2 is promoted. |
| Months 2 to 3 | B2 on prices, then B3 net of costs and capacity; regime and risk layers only where they change a decision; placebos. | **Gate 2** (end of month 3): price information above rho* (B2); incremental net PnL positive on both halves, capacity estimated (B3). |
| Month 4 | Isolated, logged paper run; next idea prepared (I3 if a transaction panel is available, otherwise I2). | |
| Month 5 | Window held back by Borel (genuine out of sample); capital proposal. | |
| Month 6 | Decision with Borel under the capital protocol (below): paper, then 25%, 50%, 100% of the target risk. | **Gate 3** (end of month 6): paper gap at most cost plus 50%; rho on the held-back window above rho*; capital only with Borel's approval. |

## Success at six months

- One strategy validated on held-back data, with positive net PnL and an estimated capacity, or a documented stop with the gap quantified.
- A second idea through Gate 1.
- Reproducible code and point-in-time data.

## Stop (at any time)

- A data source that cannot be verified point-in-time.
- rho below its threshold.
- A fusion model that does not beat the baseline: keep the baseline, or stop.
- A data trial whose incremental value is below its cost.
- The drawdown rules of the capital protocol.

## Capital protocol

Paper, then 25%, 50% and 100% of the target risk. Risk is halved when the drawdown from the high-water mark reaches one annual standard deviation of the strategy's PnL; the strategy stops at 1.5 annual standard deviations. These thresholds are proposed defaults, to be set with Borel's risk team; capital only with Borel's approval.
