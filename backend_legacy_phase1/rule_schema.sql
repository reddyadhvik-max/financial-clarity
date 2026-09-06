-- Financial Clarity — Rule Table Schema (Phase 1)
-- Versioned by financial year (FY). The LLM never computes these numbers directly;
-- it only reads rows here via `lookup_rule` and cites the matching rule_id in explanations.

CREATE TABLE fiscal_years (
    fy_id           TEXT PRIMARY KEY,      -- e.g. 'FY2024-25'
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT 0
);

-- Tax slabs, one row per bracket, per regime, per FY.
CREATE TABLE tax_slabs (
    rule_id         TEXT PRIMARY KEY,      -- e.g. 'FY24-25-new-slab-3'
    fy_id           TEXT NOT NULL REFERENCES fiscal_years(fy_id),
    regime          TEXT NOT NULL CHECK (regime IN ('old', 'new')),
    slab_order      INTEGER NOT NULL,      -- ordering within the regime for cumulative calc
    income_from     NUMERIC NOT NULL,
    income_to       NUMERIC,               -- NULL = no upper bound
    rate_pct        NUMERIC NOT NULL,
    UNIQUE (fy_id, regime, slab_order)
);

-- Standard deduction, rebate thresholds, cess — single-value rules that aren't slabs.
CREATE TABLE flat_rules (
    rule_id         TEXT PRIMARY KEY,      -- e.g. 'FY24-25-standard-deduction'
    fy_id           TEXT NOT NULL REFERENCES fiscal_years(fy_id),
    regime          TEXT CHECK (regime IN ('old', 'new', 'both')),
    rule_key        TEXT NOT NULL,         -- 'standard_deduction' | 'rebate_87a_limit' | 'cess_pct' | 'epf_employee_pct' | 'epf_employer_pct'
    value           NUMERIC NOT NULL,
    UNIQUE (fy_id, regime, rule_key)
);

-- HRA exemption formula inputs (city classification threshold, %s used in the min-of-three calc).
CREATE TABLE hra_rules (
    rule_id             TEXT PRIMARY KEY,  -- e.g. 'FY24-25-hra-metro'
    fy_id               TEXT NOT NULL REFERENCES fiscal_years(fy_id),
    city_class          TEXT NOT NULL CHECK (city_class IN ('metro', 'non_metro')),
    basic_pct_for_calc  NUMERIC NOT NULL,  -- 50% metro / 40% non-metro of basic
    UNIQUE (fy_id, city_class)
);

-- Deduction categories available under the old regime (80C, 80D, etc.) — new regime disallows most of these.
CREATE TABLE deduction_categories (
    rule_id         TEXT PRIMARY KEY,      -- e.g. 'FY24-25-80C'
    fy_id           TEXT NOT NULL REFERENCES fiscal_years(fy_id),
    section_code    TEXT NOT NULL,         -- '80C' | '80D' | '80CCD1B' | ...
    max_limit       NUMERIC NOT NULL,
    allowed_regimes TEXT NOT NULL          -- comma list, e.g. 'old' or 'old,new'
);

-- Every computed output number in the breakdown response must cite a rule_id from one of the
-- tables above (or a composite of several) so the UI's audit-trail feature (Phase 3) has
-- something concrete to point to.
