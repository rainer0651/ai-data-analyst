# Database Context — Snowflake

> The AI data analyst reads this whole file before writing any SQL. It currently
> describes the **TPCH_SF1 sample dataset** (Snowflake's built-in benchmark data) so the
> app works out of the box. When you load your own data (e.g. the bike store sheets),
> replace the sections below with your real schema and update `.env`'s
> `SNOWFLAKE_DATABASE` / `SNOWFLAKE_SCHEMA`.

---

## 1. Overview

- **What this database holds:** TPC-H, a classic sales/ordering benchmark dataset. Think
  of it as a wholesale supplier: customers place orders, each order has line items for
  parts supplied by suppliers, and customers/suppliers belong to nations and regions.
- **Grain of the core tables:** `ORDERS` = one row per order; `LINEITEM` = one row per
  line on an order (this is where quantities and prices live).
- **Scale:** the `SF1` schema is ~1 GB (~1.5M orders, ~6M line items).

## 2. Connection defaults

The app connects with these (from `.env`) and validates every query is read-only
(single `SELECT`/`WITH`, no writes) before running it.

| Setting | Value |
|---|---|
| Database | `SNOWFLAKE_SAMPLE_DATA` |
| Default schema | `TPCH_SF1` |
| Warehouse | `COMPUTE_WH` |
| Role | *(account default — currently ACCOUNTADMIN; see note below)* |

> ⚠️ **Read-only role not yet set.** The connection currently runs as ACCOUNTADMIN. The
> app's query validator still blocks writes, but for defense in depth create a SELECT-only
> role and set `SNOWFLAKE_ROLE` to it.

## 3. Schemas & tables

All tables are in `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`. Columns are prefixed by table
(`C_` = customer, `O_` = orders, `L_` = lineitem, etc.).

### `CUSTOMER`
- **Grain:** one row per customer.
- **Key columns:** `C_CUSTKEY` (PK), `C_NAME`, `C_NATIONKEY` (→ NATION), `C_ACCTBAL`
  (account balance), `C_MKTSEGMENT` (e.g. AUTOMOBILE, BUILDING, FURNITURE, MACHINERY, HOUSEHOLD).

### `ORDERS`
- **Grain:** one row per order.
- **Key columns:** `O_ORDERKEY` (PK), `O_CUSTKEY` (→ CUSTOMER), `O_ORDERSTATUS`
  (`O` open / `F` fulfilled / `P` partial), `O_TOTALPRICE`, `O_ORDERDATE` (DATE),
  `O_ORDERPRIORITY`, `O_CLERK`, `O_SHIPPRIORITY`.

### `LINEITEM`
- **Grain:** one row per line item on an order. This is the fact table for revenue.
- **Key columns:** `L_ORDERKEY` (→ ORDERS), `L_PARTKEY` (→ PART), `L_SUPPKEY` (→ SUPPLIER),
  `L_LINENUMBER`, `L_QUANTITY`, `L_EXTENDEDPRICE` (quantity × part price, pre-discount),
  `L_DISCOUNT` (fraction 0–1), `L_TAX` (fraction), `L_RETURNFLAG` (`R`/`A`/`N`),
  `L_LINESTATUS`, `L_SHIPDATE`, `L_COMMITDATE`, `L_RECEIPTDATE`, `L_SHIPMODE`.

### `PART`
- **Grain:** one row per part. `P_PARTKEY` (PK), `P_NAME`, `P_MFGR`, `P_BRAND`, `P_TYPE`,
  `P_SIZE`, `P_CONTAINER`, `P_RETAILPRICE`.

### `SUPPLIER`
- `S_SUPPKEY` (PK), `S_NAME`, `S_NATIONKEY` (→ NATION), `S_ACCTBAL`.

### `PARTSUPP` (part–supplier bridge)
- `PS_PARTKEY` (→ PART), `PS_SUPPKEY` (→ SUPPLIER), `PS_AVAILQTY`, `PS_SUPPLYCOST`.

### `NATION`
- `N_NATIONKEY` (PK), `N_NAME` (e.g. UNITED STATES, GERMANY), `N_REGIONKEY` (→ REGION).

### `REGION`
- `R_REGIONKEY` (PK), `R_NAME` (AMERICA, ASIA, EUROPE, MIDDLE EAST, AFRICA).

## 4. Joins & relationships

- `ORDERS.O_CUSTKEY` → `CUSTOMER.C_CUSTKEY`
- `LINEITEM.L_ORDERKEY` → `ORDERS.O_ORDERKEY`
- `LINEITEM.L_PARTKEY` → `PART.P_PARTKEY`
- `LINEITEM.L_SUPPKEY` → `SUPPLIER.S_SUPPKEY`
- `PARTSUPP.PS_PARTKEY` → `PART.P_PARTKEY`; `PARTSUPP.PS_SUPPKEY` → `SUPPLIER.S_SUPPKEY`
- `CUSTOMER.C_NATIONKEY` / `SUPPLIER.S_NATIONKEY` → `NATION.N_NATIONKEY`
- `NATION.N_REGIONKEY` → `REGION.R_REGIONKEY`

## 5. Common metrics & definitions

- **Revenue (net of discount):** `SUM(L_EXTENDEDPRICE * (1 - L_DISCOUNT))` from `LINEITEM`.
- **Gross revenue (pre-discount):** `SUM(L_EXTENDEDPRICE)`.
- **Order value:** use `O_TOTALPRICE` on `ORDERS`, or sum line revenue for a discounted figure.
- **Units sold:** `SUM(L_QUANTITY)`.

## 6. Conventions & preferences

- ⚠️ **Dates are historical.** All order/ship dates fall between **1992-01-01 and
  1998-08-02**. Relative filters like "last month" or `CURRENT_DATE` return nothing —
  interpret time ranges against 1992–1998 (e.g. "last year of data" = 1998), or ask the
  user which period they mean.
- **Discounts** (`L_DISCOUNT`, `L_TAX`) are fractions between 0 and 1, not percentages.
- **Default row limit:** add an explicit `LIMIT 1000` to non-aggregated queries.
- Amounts are unitless benchmark numbers (treat as dollars).

## 7. Example question → SQL pairs

**Q:** "What was total net revenue by region in 1997?"
```sql
SELECT r.R_NAME AS region,
       SUM(l.L_EXTENDEDPRICE * (1 - l.L_DISCOUNT)) AS net_revenue
FROM lineitem l
JOIN orders o   ON o.O_ORDERKEY = l.L_ORDERKEY
JOIN customer c ON c.C_CUSTKEY  = o.O_CUSTKEY
JOIN nation n   ON n.N_NATIONKEY = c.C_NATIONKEY
JOIN region r   ON r.R_REGIONKEY = n.N_REGIONKEY
WHERE o.O_ORDERDATE >= '1997-01-01' AND o.O_ORDERDATE < '1998-01-01'
GROUP BY r.R_NAME
ORDER BY net_revenue DESC;
```

**Q:** "Top 10 customers by number of orders."
```sql
SELECT c.C_NAME, COUNT(*) AS order_count
FROM orders o
JOIN customer c ON c.C_CUSTKEY = o.O_CUSTKEY
GROUP BY c.C_NAME
ORDER BY order_count DESC
LIMIT 10;
```

---

## Feedback Log

> The app appends entries here automatically when a user clicks **Report a problem**
> on a data pull. Review these periodically and fold recurring corrections into the
> sections above.

<!-- FEEDBACK_LOG_START -->
<!-- New feedback is inserted below this line, newest last. -->
