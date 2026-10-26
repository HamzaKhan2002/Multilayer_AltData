# Six-month plan, success criteria and stop criteria

One idea is prototyped (I1: a free version is built and tested, and the plan builds its final systemic version), one is prepared (I2), the others stay in reserve. I1 is prototyped as thesis B (central) with branch A (complementary, capped); its gates B-S, B1 (against the public model B1b), B2 and B3 are defined in the I1 card of `IDEAS.md`. The ranking weighs conditional PnL, data cost and time to a first signal, not potential alone: I3 has the highest conditional potential but the most expensive data, so it moves up as soon as a transaction panel is available.

Each gate ends in one of three outcomes, written in advance: promising, inconclusive or stop. Inconclusive is not a pass.

| Period | Work | Gate |
|---|---|---|
| Month 1 | Professional Cushing trial against the pilot (a sample, then a historical trial; delivery dates logged from the first day); B1 against the public model B1b on the declared target; CL1-CL2 quotes; A capped; I2 in parallel on free data. | **Gate 1** (end of month 1): a physical variable that beats the public nowcast on its own target, out of sample (B-S, B1). Otherwise: inconclusive (one bounded extension, if it can change the decision at a reasonable cost) or stop for that use; if no credible source passes, B's budget is reallocated and I2 is promoted. |
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
- a useful incremental gain excluded by the interval (below the cost threshold).
- A fusion model that does not beat the baseline: keep the baseline, or stop.
- A data trial whose incremental value is below its cost.
- The drawdown rules of the capital protocol.

## Capital protocol

Paper, then 25%, 50% and 100% of the target risk. Risk is halved when the drawdown from the high-water mark reaches one annual standard deviation of the strategy's PnL; the strategy stops at 1.5 annual standard deviations. These thresholds are proposed defaults, to be set with Borel's risk team; capital only with Borel's approval.

## Decisions revised on 25 October 2026

- **Three decisions, three levels of proof.** Funding an experiment needs a documented mechanism, an uncertainty the experiment can resolve and a bounded cost; subscribing for a strategy needs incremental value measured on that source's own data; committing market risk needs independent results, costs, capacity and a risk mandate. Demanding a demonstrated PnL before the data can be examined would be circular. The research investment requested now is a bounded trial of one professional Cushing dataset (TankWatch or Wood Mackenzie first, Kpler as comparator, Ursa Space as alternative; raw radar is not a priority).
- **Free source first, then a trial, then a subscription only if earned** (replaces "buy processed data where it exists").
- **The 3-4 cents ceiling is withdrawn.** It extrapolated a non-significant Cushing coefficient. A reaction within a window does not show full incorporation and a non-detection is not an absence of effect.
- **Cadence is a documented constraint of the pilot protocol, not an identified cause** of the weak hub correlation; a repeatable measurement is not a measurement of known error.
- **B1 is adapted to the target the source is built to measure**; the mean RMSE of the EIA figure must not eliminate a source built to measure another physical constraint.
- **k and event risk are set on the holding window** (`results/v3/pnl_grid_windows.csv`): 0.018 from the API release to 10:36, 0.040 from 09:30, 0.051 for the six minutes after the print.
- **B0 sensitivity and the clock.** The year gate that excluded 2026 tested a strong reaction, not the clock; the clock is supported by independent checks and the sensitivity keeping 2026 gives the same conclusion.
- **Branch A** now has a price-only proxy (v3, exploratory); no result of A is evidence for B.

## Revisions of 26 October 2026

- **One decision rule everywhere.** Promising: a useful effect estimated, with compatible robustness and uncertainty. Inconclusive: the interval cannot separate a useful gain from none; one bounded extension is justified only if it can change the decision at a reasonable cost. Stop that use: data unfit for the test, a useful gain excluded, or additional information that costs disproportionately. An economic stop can be decided without a statistical refutation: it is a budget decision, not proof that no edge exists, and a negative B1 concerns the intended use and target, not all physical information.
- **B2 is incremental.** The augmented forecast is compared with the forecast without the source by a paired difference; a good total correlation does not show that the source adds anything. The threshold rho* belongs to the Gaussian sign-rule illustration, not to every policy; B3 (incremental net PnL against the same strategy without the source) remains the economic arbiter.
- **Order of work.** The professional-data trial and its economic evaluation come first; new measurement work (scene calibration, Friday anchoring, Sentinel-1 phase) is taken up where the trial identifies a limit it can address.
- **Branch A.** The price proxy is a partial exploratory reproduction of the relation studied by Alturki and Kurov (post-API return, their Table 2A and Figure 4), not of their API-minus-consensus strategy (Table 8). A weak positive association in 2013-2019; persistence not established in 2019-2023 (r -0.03, interval -0.18 to 0.13); 2026 (14 events) insufficient.
- **Friday reference time.** EIA survey instructions: 7 a.m. Eastern Time. The frozen protocol used Central; recomputing BS0 and BS2 with Eastern changes nothing (`results/v3/et_reference_sensitivity.json`).
- **Break-even and grids.** The break-even edge per covered event is in dollars per barrel (x100 for cents), after variable costs, with operating costs added to the annual cost when included. The PnL grids do not subtract a subscription or operating costs and are neither expected-return estimates nor capacity measures.
