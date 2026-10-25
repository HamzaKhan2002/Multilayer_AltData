# Idea cards

Six ideas under one discipline (see `ARCHITECTURE.md`). Each card has the same fields. Examples are illustrative; PnL figures are conditional (see `PNL_METHOD.md`). One idea is developed in depth (I1); one is prepared (I2); the others are in reserve.

Card template: mechanism and counterparty; who invests and the evidence; data and engineering; pillars; concrete example; one-line falsifiable test; data to obtain; instruments and turnover; baseline to beat; conditional PnL; stop criterion.

---

## I1 · Energy inventories before the EIA report (developed)

- **Mechanism and counterparty.** The EIA publishes US stocks every week (oil on Wednesday, gas on Thursday). Participants who wait for the figure, or who only have the Tuesday API estimate, learn the information at the print. An earlier, better estimate (optical and radar satellites, shipping flows, weather) and knowing how reliable it is (clouds, radar revisit) is the edge. Counterparties: participants reacting to the print, and non-informational hedgers (producers, refiners).
- **Structure.** Thesis B (central): an independent measurement of Cushing stocks, available before the EIA figure, can change the expected price move beyond what public data and prices already contain. Branch A (complementary, capped): replication of the published post-API drift before the EIA print (Alturki and Kurov, 2022); it is never counted as evidence for B.
- **Gates, in sequence.** B-S (measurement): a weekly variable with known coverage, age and error before the cut-off. B1 (nowcast): it beats the public model B1b out of sample. B2 (information beyond prices): the out-of-sample correlation between the forecast and the price move exceeds rho*. B3 (net value): incremental net PnL against the same strategy without the variable, after costs and capacity, above the data cost. Each gate ends promising, inconclusive or stop; inconclusive is not a pass.
- **Who invests and evidence.** Mukherjee, Panayotov and Shon (JFE 2021): satellite estimates so effective that markets are no longer surprised by public announcements, identified through cloud cover. Hao and Wang (2023): cloud cover over floating-roof tanks predicts next-week oil returns. Alturki and Kurov (J. Futures Markets 42(1), 172-188, 2022): the price move after the API release predicts the drift before the EIA release; this is branch A, a published effect to replicate. Miao, Ramchander, Wang and Yang (J. Futures Markets 38(1), 38-65, 2018): inventory announcements and derivatives. Villamil Lopez and Stilla (IEEE JSTARS 14, 5638-5655, 2021): oil tank filling from spaceborne SAR with coherent scatterers; their sample has no physical ground truth. Copernicus/ESA success story (14 September 2018): Sentinel-1 used by Kayrros for oil storage; documentary evidence of use, not an independent accuracy study.
- **Vendors (market examples; their claims are not reproduced here).** Tank inventories: Kayrros (its acquisition by Energy Aspects was completed on 21 May 2026), Ursa Space (publication of 12 February 2024, with a vendor-reported 0.98 correlation with EIA levels in 2023), Kpler (Cushing drone inventories, three times a week); Orbital Insight (imagery). Raw radar: ICEYE (commercial SAR down to 0.5 m in some modes). Flows: Kpler, Vortexa.
- **Data and engineering.** Roof depth of floating-roof tanks read from the Sentinel-2 shadow (free pilot, B-S) and aggregated by hub; radar through clouds (amplitude now; phase data, SLC, to be tested); a vendor tank series only where it closes a measured gap; AIS flows (PADD 3 imports and exports: coastal balances, not Cushing) with sequence models; weather (clouds as observability, hurricanes) tabular; EIA history, curve state and volatility tabular. Targets: the weekly Cushing change (B1), then the price move (B2).
- **Pillars.** Data (satellites, AIS, weather, EIA) · regimes (observability: clouds and radar revisit; curve state; volatility) · risk (event risk at the print, CVaR of the release-day distribution, volatility targeting, holiday calendar) · fusion (baseline ladder: AR(2), then the public model B1b; candidates: Kalman or state-space filter, gradient-boosted trees, a hierarchical model per tank).
- **Example (illustrative).** On Tuesday evening, after the API figure, the satellite nowcast points to a much larger draw than the public model expects; a long WTI position sized by the event risk budget; exit after the Wednesday print (10:30 ET, 16:30 in Malta).
- **Falsifiable test.** If the physical variable does not improve the public nowcast out of sample (B1), or adds nothing to prices beyond rho* = 0.025 (B2), the physical branch stops.
- **Data to obtain.** Intraday quotes for CL1 and CL2, or the native spread, with sizes; EIA and API figures with their publication timestamps; a trial history of a processed tank series, as delivered, to compare with the pilot; Sentinel-1 phase data (SLC), or a higher-cadence source, if the pilot is pursued; weather forecast runs as issued. Free data (EIA archive, Sentinel, OpenStreetMap) already cover the pipeline, the baseline and the pilot.
- **Instruments and turnover.** CL outright and the CL1-CL2 calendar spread first; products and options (see I6) only after B2. About 52 decisions a year, one per Cushing report, fewer without a usable measurement; two expressions of one signal are not independent bets. Exit after the print. Capacity: very liquid markets (assumption: not binding at a few M$ of risk).
- **Baseline.** B1a, AR(2) on the weekly change (out-of-sample R2 0.307 on 521 forecasts at Cushing, 2016 to 2025; RMSE 1.20 Mb against 1.44 for a constant mean). B1b, a public model: season, lagged stocks, the curve, prices already seen, the API figure if known at the cut-off. B1c, B1b plus the physical variable with its age and coverage: the only test of the source's value.
- **Link to the first version.** This is the upgrade of the first version: same question, three changes (the free source tested first, with a purchase only where it closes a measured gap; four separate proofs, gated one by one; two expressions, the CL outright and the CL1-CL2 spread).
- **Checks run.** T1 (report days are more volatile: supported), T2 (direction of the surprise: not supported), T3 (cloud cover and the release-day move: inconclusive at daily resolution); see `results/verdicts.md`. In v2: T1c and T2c with the EIA archive release dates (supported, not supported), the roof-shadow pilot BS0 to BS2 and the price diagnostic B0; see `README.md` and `results/v2/`.
- **Status (25 Oct 2026).** The roof-shadow pilot is repeatable per tank; the hub test is inconclusive (19 low-sun weeks); the print is priced within minutes (B0); the Cushing coefficient is not detected on the outright (exploratory).

## I2 · European power and gas, weather balance (prepared)

- **Mechanism and counterparty.** Weather (wind, sun, temperature) sets renewable supply and heating demand; each new forecast run moves the expected price (merit order) and storage withdrawals. Counterparties: participants hedging or adjusting on older forecasts; forced short-term balancing needs.
- **Who invests and evidence.** Citadel and FlexPower (13 October 2025, 1,700 MW, more than 11 TWh a year of short-term power); Optiver and Northpool (18 August 2026, majority stake, short-term power and gas, weather analytics); BCG (24 August 2026): "The action—and the money—has moved to intraday markets".
- **Data and engineering.** Ensemble forecasts (ECMWF, GFS) with state-space or tabular models; renewable and load forecasts (ENTSO-E); storage (AGSI+); flows (ENTSOG); outages (REMIT); a fundamental merit-order model plus ML on the residuals.
- **Pillars.** Data (weather, renewables, load, storage) · regimes (marginal fuel gas or coal, storage level, season) · risk (spikes, negative prices, CVaR, liquidity) · fusion (baseline: persistence; candidates: fundamental model, trees, custom).
- **Checks run.** T4 (merit order: supported) and T5 (storage withdrawals and heating degree days: supported); see `results/verdicts.md`.
- **Example (illustrative).** A run raises the forecast German wind sharply for D+2; the expected price falls; sell the short contract (day or week) before the market has fully integrated it.
- **Falsifiable test.** If the 95% lower bound of the out-of-sample correlation between forecast revisions and price changes, beyond persistence, does not exceed rho* = 0.063, stop.
- **Data to obtain.** Power and TTF futures (EEX, ICE), EPEX day-ahead and intraday, ensemble forecasts timestamped by run.
- **Instruments and turnover.** Power futures (DE, FR), TTF; day-ahead and intraday. About 250 decisions a year. Capacity: medium (assumption).

## I3 · Equity revenue before earnings

- **Mechanism and counterparty.** Card transactions, geolocation, web and app traffic and car-park imagery measure sales during the quarter; consensus adjusts slowly. Counterparties: investors relying on consensus and company guidance.
- **Who invests and evidence.** Froot, Kang, Ozik and Sadka (JFE 2017): about 50 million mobile devices, average excess announcement returns of 3.4%. Katona, Painter, Patatoukas and Zeng (JFQA 2025): satellite images of car parks (RS Metrics, Orbital Insight); profitable especially on bad news. Vendors: Consumer Edge, Earnest, Placer.ai, Advan, Similarweb, Sensor Tower.
- **Data and engineering.** Transaction panels with panel normalisation and sequence models; geolocation with trees or linear models; car parks with vision (vendor side).
- **Pillars.** Data · regimes (earnings season, market volatility, crowding) · risk (earnings gap, market and sector neutrality, CVaR) · fusion (baseline: consensus plus seasonality; candidates: penalised regression, trees).
- **Example (illustrative).** Two weeks before a retailer reports, cards and footfall point to revenue well above consensus; long position hedged against the sector; exit after the release.
- **Falsifiable test.** If the forecast does not predict the revenue surprise versus consensus out of sample, or if its correlation with the announcement return stays below rho* = 0.025 (lower 95% bound), stop.
- **Data to obtain.** Card or geolocation panel with point-in-time history; consensus (I/B/E/S or equivalent); earnings calendar; prices and costs.
- **Instruments and turnover.** Stocks (long and hedged short), options (see I6). About 400 bets a year (100 stocks, 4 quarters). Capacity: high on large caps (assumption).

## I4 · Text intelligence (equities, credit)

- **Mechanism and counterparty.** Changes in how filings are written, calls and news contain information that inattentive investors integrate slowly. Counterparties: investors who do not read the changes.
- **Evidence.** Cohen, Malloy and Nguyen (JF 2020, "Lazy Prices"): up to 188 bp a month of gross alpha, no reaction at the announcement. Ke, Kelly and Xiu (NBER 26186): supervised text sentiment beats vendor and dictionary scores. Lopez-Lira and Tang (arXiv 2304.07619): GPT-4 predicts drift, mostly small caps and bad news; returns fall as LLM adoption rises. Glasserman and Lin (JFDS 2023): look-ahead and distraction biases of LLMs; remove identifiers.
- **Data and engineering.** EDGAR, transcripts, news; embeddings, fine-tuned transformers, supervision on returns; dated models and anonymised inputs (no leakage).
- **Pillars.** Data · regimes (LLM adoption means decay; market sentiment) · risk (factor neutrality, crowding) · fusion (baselines: bought sentiment and a model without text).
- **Example (illustrative).** A company rewrites its risk section heavily; the supervised score predicts underperformance; short, hedged against the sector, over 1 to 3 months.
- **Falsifiable test.** If the supervised score does not beat, out of sample, a bought sentiment score and a model without text, stop.
- **Data to obtain.** Timestamped news, transcripts, GPU compute (EDGAR is free).
- **Instruments.** Equities; credit (CDS, bonds) possibly. PnL not quantified: the effective number of bets is unknown and rho falls with LLM adoption; to be measured before any sizing.

## I5 · Crops from space (agriculture)

- **Mechanism and counterparty.** Vegetation state (NDVI) and seasonal weather anticipate yields before USDA reports (monthly WASDE, weekly Crop Progress). Counterparties: participants waiting for the reports.
- **Who invests and evidence.** Adjemian (American Journal of Agricultural Economics, 2012): WASDE announcements move cotton, soybean and wheat futures, and the effect is incorporated rapidly into prices. Lobell et al. (Remote Sensing of Environment, 2015): satellite-based crop yield mapping at scale.
- **Data and engineering.** NDVI from Sentinel-2 or MODIS by county with vision and time series; weather tabular; USDA as target.
- **Pillars.** Data · regimes (growth stage, drought) · risk (report gaps, limit moves) · fusion (baseline: trend plus weather; candidate: trees).
- **Example (illustrative).** In late July the aggregated vegetation index for Iowa and Illinois falls below the path of normal years; the yield forecast sits below the USDA figure; long soybeans before the August WASDE.
- **Falsifiable test.** If the vegetation index does not reduce, out of sample, the error of the yield forecast versus trend plus weather, stop.
- **Data to obtain.** Intraday grain prices; commercial imagery if resolution limits.
- **Instruments and turnover.** Corn, soybeans, wheat (futures, options). About 60 bets a year (assumption).

## I6 · Event volatility (options)

- **Mechanism and counterparty.** Option prices around an event (EIA release, earnings) assume a size of surprise; the nowcasts of I1 and I3 measure the real uncertainty (conflicting sources, clouds, panel dispersion). Counterparties: option buyers and sellers who calibrate the size on history.
- **Evidence.** Dubinsky, Johannes, Kaeck and Seeger (Review of Financial Studies, online 2018): option prices reveal the uncertainty around earnings announcements; it is large, varies over time and is informative about future volatility. A public-data pre-study on CBOE volatility indices (origins 2014 to 2026): implied-volatility indices improve a 5-day realised-variance forecast, QLIKE -26% against a log-HAR baseline (t 6.8) and -6.7% beyond VIX alone (t 2.5); the squared-error gain is weak (Clark-West p = 0.05). The study is not part of this repository.
- **Data and engineering.** Implied-volatility surfaces (vendor); surprise distributions from I1 and I3 feeding a size-of-move model (quantiles).
- **Pillars.** Data · regimes (volatility regime, event clustering) · risk (short-gamma tails: CVaR, vega limits) · fusion (baseline: implied move equals expected move).
- **Example (illustrative).** Conflicting sources and clouds before an EIA release while the day's implied move is low; buy a short-dated WTI straddle the day before and sell after the print.
- **Falsifiable test.** If the 95% lower bound of the correlation between the predicted size and (realised move minus implied move) does not exceed rho* = 0.063, stop.
- **Data to obtain.** Histories of volatility surfaces (energy, equities), option execution costs.
- **Instruments and turnover.** Options on energy futures, equity options. About 400 bets a year (earnings); energy event options would add about 52.

## Other directions

Macro and rates (online prices, job postings, cards feeding inflation and employment surprises into rate futures and options); crypto (on-chain flows, stablecoin issuance into perpetuals and options); shipping (AIS into freight and transport equities).
