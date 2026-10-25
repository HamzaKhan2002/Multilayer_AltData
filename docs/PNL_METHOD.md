# PnL method: conditional orders of magnitude, never results

No strategy has been backtested in this repository. The numbers below follow from explicit assumptions and answer one question: if the out-of-sample correlation between the forecast and the price move is rho, what is the order of magnitude of the annual PnL for a given risk budget?

## Formula

Constant-size bets on the sign of a forecast, Gaussian approximation:

    IR_net  = sqrt(N) * ( sqrt(2/pi) * rho - k )
    PnL_net = IR_net * B

- N: independent bets per year.
- rho: out-of-sample correlation between the forecast and the price move over the holding period (for I1, measured in gate B2). It is not a correlation with the stock surprise.
- k: round-trip cost divided by the standard deviation of the move.
- B: annual risk budget (standard deviation of PnL). Reference: B = 1 M$ per year, that is 10 M$ of capital at 10% volatility.
- Break-even correlation: rho* = k / sqrt(2/pi).

`python scripts/pnl_grid.py` recomputes the grid and writes `results/v2/pnl_grid_v2.csv`; with `--v1` it writes `results/pnl_grid.csv`, the first grid.

## Assumptions

N and k come from the structure of each market and are to be replaced by real costs and capacity. The same grid of rho is used for every idea (0.03 low, 0.06 central, 0.10 high).

| Idea | N per year | k | Why |
|---|---|---|---|
| I1 Energy inventories | 52 | 0.02 | One decision per Cushing report; fewer weeks without a usable measurement. About one tick plus fees (roughly 15 to 25 USD round trip) against a daily standard deviation of about 1,000 to 1,700 USD per contract. |
| I2 European power and gas | 250 | 0.05 | One decision per trading day. Round trip about 0.1 to 0.3% of price against a daily standard deviation of 3 to 5%. |
| I3 Equity revenue before earnings | 400 | 0.02 | 100 stocks times 4 quarters. About 10 bp round trip against 5 to 6% standard deviation over the announcement window. |
| I5 Crops from space | 60 | 0.03 | A few reports per crop per year. About 17 USD against about 500 USD standard deviation on a report day (corn). |
| I6 Event volatility (options) | 400 | 0.05 | Earnings events; energy event options would add about 52 and are not counted. About 4% of a straddle premium against the standard deviation of a straddle PnL. |
| I4 Text | not quantified | | The number of effectively independent bets is unknown (overlapping horizons, common factors) and rho falls as LLM adoption rises. To be measured before any sizing. |

I1 counts one decision per Cushing report. The gas report is not a separate I1 bet, and two expressions of one signal (the outright and the calendar spread) are not independent bets.

## Grid (M$ per year for B = 1 M$), illustrative

Illustrative: conditional on N, k and rho, never a result. Values below zero mean the forecast does not cover costs at that frequency (shown as < 0 in the deck). The v1 grid (I1 with N = 104: 52 oil and 52 gas reports) is kept in `results/pnl_grid.csv`.

| Idea | rho* | rho = 0.03 | rho = 0.06 | rho = 0.10 |
|---|---|---|---|---|
| I1 Energy inventories | 0.025 | 0.03 | 0.20 | 0.43 |
| I2 European power and gas | 0.063 | -0.41 | -0.03 | 0.47 |
| I3 Equity revenue | 0.025 | 0.08 | 0.56 | 1.20 |
| I5 Crops | 0.038 | -0.05 | 0.14 | 0.39 |
| I6 Event volatility | 0.063 | -0.52 | -0.04 | 0.60 |

## Reading

- "If the out-of-sample correlation between the forecast and the price move is rho, then the order of magnitude is X." Nothing more.
- The PnL scales with B until capacity binds. Capacity is an assumption for each market, to be measured.
- No aggregation across ideas: their correlations are not measured.
- Ranking by conditional potential at the central correlation: I3, then I1, I5, I2 and I6. The order of work also weighs data cost and time to a first signal.
