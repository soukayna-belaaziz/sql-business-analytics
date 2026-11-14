# Building the Olist KPI dashboard in Power BI Desktop

This is a step-by-step guide to rebuild the dashboard of this repository in
Power BI Desktop, on the same star schema. **No `.pbix` file is included in the
repo**: the report has to be built by following the steps below (Power BI
Desktop runs on Windows only and was not available in the environment where
this project was developed). The SQL side is done and tested; the guide
covers the Power BI side, so it is also a practical exercise in data modelling
and DAX.

Estimated time: 2-3 hours the first time.

---

## 0. Get the data

```bash
python data/download_data.py      # raw Olist CSVs (once)
python -m src.pipeline --powerbi  # builds DuckDB and exports the mart to powerbi/data/
```

`powerbi/data/` then contains seven CSV files (about 68 MB in total, therefore
not committed to git):

| File | Grain | Rows | Key |
|---|---|---:|---|
| `dim_date.csv` | one row per calendar day | 800 | `date_key` (yyyymmdd) |
| `dim_customer.csv` | one row per real customer (`customer_unique_id`) | 96,096 | `customer_key` |
| `dim_product.csv` | one row per product | 32,951 | `product_key` |
| `dim_seller.csv` | one row per seller | 3,095 | `seller_key` |
| `fact_orders.csv` | one row per order | 99,441 | `order_id` |
| `fact_order_items.csv` | one row per order line | 112,650 | `order_id` + `order_item_id` |
| `fact_payments.csv` | one row per payment record | 103,886 | `order_id` + `payment_sequential` |

Business definitions are the same as in SQL (see `olist_dbt/models/marts/fact_orders.sql`):
revenue = item `price` (freight excluded); only rows with `is_valid_sale = true`
count as sales; reporting period = Jan 2017 - Aug 2018 (`dim_date[is_reporting_period]`).

## 1. Import (Power Query)

1. **Get data > Text/CSV**, select `dim_date.csv`, click **Transform Data** (not Load).
2. Repeat for the other six files (Home > New Source > Text/CSV).
3. **Locale - important on an Italian Windows.** The files use `.` as decimal
   separator and ISO dates. With an Italian locale Power Query may read
   `137.37` as `13737`. Either set *File > Options and settings > Options >
   Current file > Regional settings > Locale for import = English (United States)*
   before importing, or for each decimal column use *Change Type > Using Locale >
   Decimal Number / English (United States)*.
4. Check the column types:
   - `*_key`, `order_id`, `zip_prefix`, `cohort_month`, `year_month`: **Text**
     (`date_key` and `purchase_date_key` may stay Whole Number, but must have the same type on both sides).
   - `price`, `freight_value`, `gross_value`, `payment_value`, `items_value`, `lifetime_revenue`: **Fixed decimal number**.
   - `purchase_ts`, `delivered_customer_ts`, ...: **Date/Time**; `date`, `month_start`, `first_purchase_date`, `estimated_delivery_date`: **Date**.
   - `is_*` columns: **True/False**.
5. **Close & Apply**.

## 2. Data model (Model view)

Create the relationships below - all **one-to-many, single cross-filter direction**
(dimension filters fact). Delete any relationship Power BI auto-detected that is
not in this list.

| From (one side) | To (many side) |
|---|---|
| `dim_date[date_key]` | `fact_orders[purchase_date_key]` |
| `dim_date[date_key]` | `fact_order_items[purchase_date_key]` |
| `dim_date[date_key]` | `fact_payments[purchase_date_key]` |
| `dim_customer[customer_key]` | `fact_orders[customer_key]` |
| `dim_customer[customer_key]` | `fact_order_items[customer_key]` |
| `dim_customer[customer_key]` | `fact_payments[customer_key]` |
| `dim_product[product_key]` | `fact_order_items[product_key]` |
| `dim_seller[seller_key]` | `fact_order_items[seller_key]` |

Then:

- **Mark `dim_date` as date table** (Table tools > Mark as date table > column `date`).
  Time-intelligence functions (`SAMEPERIODLASTYEAR`, `DATEADD`) need this because the
  relationships use the integer `date_key`, not the date itself.
- `dim_date[year_month]`: *Column tools > Sort by column > `month_start`*.
- Hide the key columns on the fact side (right click > Hide in report view) so
  users slice only by dimension attributes.
- Do **not** relate the three fact tables to each other. Fact-to-fact
  relationships create ambiguous filter paths (items -> orders -> customer and
  items -> customer). Shared dimensions are enough; section 3.3 shows how to pass
  a product filter to order-level measures when needed.

Result: two star schemas (orders, items) and payments sharing the conformed
dimensions `dim_date` and `dim_customer`.

## 3. DAX measures

Create an empty table to hold the measures (*Home > Enter data*, name it
`_Measures`, load it, then delete its dummy column after the first measure exists).
Format each measure as shown in the comment.

### 3.1 Core measures

```dax
Revenue =                                   -- Currency, 0 decimals
CALCULATE (
    SUM ( fact_order_items[price] ),
    fact_order_items[is_valid_sale] = TRUE ()
)

Orders =                                    -- Whole number
CALCULATE (
    COUNTROWS ( fact_orders ),
    fact_orders[is_valid_sale] = TRUE ()
)

Customers =                                 -- Whole number
CALCULATE (
    DISTINCTCOUNT ( fact_orders[customer_key] ),
    fact_orders[is_valid_sale] = TRUE ()
)

AOV =                                       -- Currency, 2 decimals
DIVIDE ( [Revenue], [Orders] )

Revenue PY =
CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )

Revenue YoY % =                             -- Percentage, 1 decimal
DIVIDE ( [Revenue] - [Revenue PY], [Revenue PY] )

Revenue MoM % =                             -- Percentage, 1 decimal
VAR PrevMonth =
    CALCULATE ( [Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
RETURN
    DIVIDE ( [Revenue] - PrevMonth, PrevMonth )

Repeat Customer Rate =                      -- Percentage, 2 decimals
-- share of customers with 2+ valid orders inside the selected period
VAR CustomersInContext =
    CALCULATETABLE (
        VALUES ( fact_orders[customer_key] ),
        fact_orders[is_valid_sale] = TRUE ()
    )
VAR Repeaters =
    COUNTROWS (
        FILTER (
            CustomersInContext,
            CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_valid_sale] = TRUE () ) >= 2
        )
    )
RETURN
    DIVIDE ( Repeaters, COUNTROWS ( CustomersInContext ) )

On-time Delivery % =                        -- Percentage, 1 decimal
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_valid_sale] = TRUE (),
        fact_orders[is_delivered] = TRUE (),
        fact_orders[is_on_time] = TRUE ()
    ),
    CALCULATE (
        COUNTROWS ( fact_orders ),
        fact_orders[is_valid_sale] = TRUE (),
        fact_orders[is_delivered] = TRUE ()
    )
)

Avg Review Score =                          -- Decimal, 2 decimals
CALCULATE (
    AVERAGE ( fact_orders[review_score] ),
    fact_orders[is_valid_sale] = TRUE ()
)
```

### 3.2 Supporting measures

```dax
Freight % of Revenue =
DIVIDE (
    CALCULATE ( SUM ( fact_order_items[freight_value] ), fact_order_items[is_valid_sale] = TRUE () ),
    [Revenue]
)

Late Shipping % =                           -- seller handed parcel to carrier after the limit
DIVIDE (
    CALCULATE (
        COUNTROWS ( fact_order_items ),
        fact_order_items[is_valid_sale] = TRUE (),
        fact_order_items[is_shipped_late] = TRUE ()
    ),
    CALCULATE (
        COUNTROWS ( fact_order_items ),
        fact_order_items[is_valid_sale] = TRUE (),
        NOT ISBLANK ( fact_order_items[is_shipped_late] )
    )
)
```

### 3.3 Order measures filtered by product or seller

`fact_orders` is not connected to `dim_product`, so a category slicer does not
filter `[Orders]` by default. `TREATAS` pushes the order ids that survive the
product/seller filter onto `fact_orders`:

```dax
Orders (item filters) =
CALCULATE (
    [Orders],
    TREATAS ( VALUES ( fact_order_items[order_id] ), fact_orders[order_id] )
)

AOV (item filters) = DIVIDE ( [Revenue], [Orders (item filters)] )
```

Use these two on pages that have a category or seller slicer.

### 3.4 Calculated columns (for the delivery and cohort visuals)

On `fact_orders` (*Table tools > New column*):

```dax
Delay Bucket =
SWITCH (
    TRUE (),
    ISBLANK ( fact_orders[delay_days] ), "Not delivered",
    fact_orders[delay_days] < 0, "1 Early",
    fact_orders[delay_days] = 0, "2 On the estimated day",
    fact_orders[delay_days] <= 7, "3 Late 1-7 days",
    "4 Late 8+ days"
)

Months Since First Purchase =
VAR FirstDate = RELATED ( dim_customer[first_purchase_date] )
RETURN
    IF (
        NOT ISBLANK ( FirstDate ),
        DATEDIFF (
            DATE ( YEAR ( FirstDate ), MONTH ( FirstDate ), 1 ),
            DATE ( YEAR ( fact_orders[purchase_ts] ), MONTH ( fact_orders[purchase_ts] ), 1 ),
            MONTH
        )
    )
```

Retention measure for the cohort matrix:

```dax
Cohort Retention % =
DIVIDE (
    [Customers],
    CALCULATE (
        [Customers],
        REMOVEFILTERS ( fact_orders[Months Since First Purchase] ),
        fact_orders[Months Since First Purchase] = 0
    )
)
```

## 4. Report pages

Use one theme colour for the main series (e.g. `#2A78D6`) and one accent for
"bad" values (e.g. `#EB6834`). No dual-axis charts: if two measures have
different units, use two visuals.

**Page 1 - Executive overview**

- Top row, slicers: `dim_date[year_month]` (Between, or a slider on `dim_date[date]`),
  `dim_customer[region]` (dropdown), `dim_product[category]` (dropdown, search on).
  Add a page-level filter `dim_date[is_reporting_period] = True`.
- Second row, six cards: Revenue, Orders (item filters), AOV (item filters),
  On-time Delivery %, Avg Review Score, Repeat Customer Rate.
- Clustered column chart: `dim_date[year_month]` x Revenue.
- Line chart below it: `dim_date[year_month]` x Revenue YoY % (only from 2018-01,
  earlier months have no prior year).
- Bar chart: `dim_product[category]` x Revenue, visual-level filter *Top N = 10 by Revenue*.

**Page 2 - Delivery and satisfaction**

- Column chart: `fact_orders[Delay Bucket]` x Avg Review Score (exclude "Not delivered").
- Table or filled map: `dim_customer[state]` with Orders, On-time Delivery %,
  Avg Review Score; conditional formatting (background colour scale) on On-time Delivery %.
- Bar chart: `dim_customer[region]` x Freight % of Revenue.
- Card: Late Shipping %.

**Page 3 - Customers and sellers**

- Matrix: rows `dim_customer[cohort_month]`, columns `fact_orders[Months Since First Purchase]`
  (filter 0-12), values Cohort Retention %, conditional formatting colour scale.
  Remove the date slicer interaction on this visual (*Format > Edit interactions*),
  otherwise later months of a cohort are filtered out.
- Table: `dim_seller[seller_key]`, `dim_seller[state]`, Revenue, Orders (item filters),
  Late Shipping %, Avg Review Score; sorted by Revenue descending.
- Donut or bar: `fact_payments[payment_type]` x payment value share
  (`SUM ( fact_payments[payment_value] )` with `is_valid_sale = TRUE`).

## 5. Reconcile with SQL before trusting the report

With no slicer selected and the page filter `is_reporting_period = True`, the
cards must match `reports/powerbi_validation.md` (generated from SQL by the
pipeline). Values at the time of writing:

| Measure | SQL value |
|---|---:|
| Revenue | 13,449,529.68 BRL |
| Orders | 97,905 |
| Customers | 94,703 |
| AOV | 137.37 BRL |
| Freight % of Revenue | 16.65% |
| Repeat Customer Rate | 3.03% |
| On-time Delivery % | 93.21% |
| Avg Review Score | 4.12 |
| Late Shipping % | 9.23% |
| Revenue YoY % for 2018-08 | 49.4% |

If a value differs, the usual causes are: wrong decimal parsing (step 1.3),
`is_valid_sale` not filtered, an auto-detected extra relationship, or
`dim_date` not marked as date table (YoY blank or wrong).

## 6. What to say about it

When describing this work, be precise: the data model, SQL, tests and the
Streamlit dashboard are in the repository; the Power BI version is a rebuild of
the same model following this guide. Only claim a Power BI report once it has
actually been built and reconciled with section 5.
