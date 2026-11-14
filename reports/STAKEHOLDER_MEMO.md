# Memo: what drives bad reviews, and what to do next

**To:** Head of Marketplace Operations  **From:** Data analyst  **Data:** Olist public dataset,
orders Jan 2017 to Aug 2018 (cancelled orders excluded)

## In one sentence

Orders more than doubled, but late deliveries (under 7% of orders) now generate a third of all bad
reviews, and they are concentrated in identifiable regions and sellers.

## Three findings

1. **A late parcel costs about two stars.** 6.7% of reviewed orders arrive after
   the promised date, yet they produce 32.6% of all 1-2 star reviews. When we
   compare like with like (same seller, product category, region and month), a late order still
   scores 1.9 to 2.0 stars lower, and the chance of a bad review
   goes up by about 52 percentage points (9% on time vs
   62% late). 84% of late customers wrote their review
   *before* the parcel arrived. Meanwhile on-time delivery slipped from 96.5% to
   92.3% year on year.
2. **The problems cluster.** Northeast customers spend more per order (BRL 165 vs
   131 in the Southeast) but wait 20 days instead of
   11, and only 87.2% of their orders arrive on time. The
   62 sellers who hand parcels to the carrier late on 20%+ of orders
   (30.5% on average, 11.8% of revenue) average
   3.78 stars, against 4.15 for the most punctual sellers.
3. **Growth is new customers, and demand has levelled off.** Orders grew 137%
   year on year (Jan-Aug 2018 vs Jan-Aug 2017) while the average basket stayed flat (+0.4%). Only 3.5% of
   2018 orders come from returning customers. Weekly orders in 2018 hover around
   1,611.

## Three recommendations

1. **Protect the delivery promise on the worst routes.** Add a safety margin to promised dates
   for Northeast destinations and alert on any order close to its promise. If the estimated effect
   holds, halving late deliveries would have meant about 1,650 fewer 1-2 star
   reviews over the 20 months analysed. Test it first: pad the promise on a random half of routes
   for a month and compare reviews and conversion.
2. **Put the late-shipping sellers on a shipping-time agreement.** Start with the
   62 sellers above 20% late hand-over: a weekly scorecard, a warning, then
   reduced visibility. Their 11.8% revenue share makes the risk manageable.
3. **Plan on a 4-week average, and test retention before scaling it.** For staffing and carrier
   capacity, a 4-week average forecasts the next weeks 13% more accurately than
   "same as last week" (typical error 17%): about 1,869 orders a
   week, plausible range 1,415 to 2,491. In parallel, run a win-back
   campaign for the 13,967 high-value customers who have not bought for about a
   year (28.8% of revenue), keeping a random 20% as a control group.

## How sure are we?

The delivery finding is consistent across four statistical approaches, but it comes from
historical data, not an experiment: something we cannot see (e.g. fragile products) could explain
part of it. That is why recommendations 1 and 3 start with a controlled test. The data is a public
sample of Olist orders, with no margin or cost data, so "revenue" means merchandise value.
Details: `reports/ANALYSIS_DELAY_AND_FORECAST.md`, `docs/QUERIES.md`.
