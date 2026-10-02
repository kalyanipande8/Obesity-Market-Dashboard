"""
Vectorized synthetic generator for public-prescription-style obesity-therapy
claims data: one row per (state x quarter x product x payer) combination,
expanded with a per-combination claim-count multiplier so the final table
has 1,000,000+ rows -- generated with numpy/pandas vector ops, not a Python
row-by-row loop, since this needs to scale to a million+ rows efficiently.

This is synthetic data. No real claims vendor, PBM, or patient record
produced any of these numbers. Structured to look like real obesity-market
prescription data (state population-weighted volume, product launch timing,
payer mix, seasonal/growth trend) but every value is simulated.
"""
import numpy as np
import pandas as pd

RNG_SEED = 42

STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
]
assert len(STATES) == 50

# Relative population weights (rough, order-of-magnitude, for believable volume skew)
STATE_WEIGHTS = np.array([
    4.9,0.7,7.3,3.0,39.0,5.8,3.6,1.0,22.0,10.9,1.4,1.9,12.6,6.8,3.2,
    2.9,4.5,4.6,1.4,6.2,7.0,10.0,5.7,2.9,6.2,1.1,2.0,3.2,1.4,9.3,
    2.1,19.8,10.6,0.8,11.8,4.0,4.2,13.0,1.1,5.2,0.9,7.0,30.0,3.4,0.6,
    8.7,7.8,1.8,5.9,0.6,
])
STATE_WEIGHTS = STATE_WEIGHTS / STATE_WEIGHTS.sum()

PRODUCTS = [
    # (name, launch_year_quarter_index, base popularity weight)
    ("Semaglutide_Inj", 0, 1.00),     # already on market at sim start
    ("Liraglutide_Inj", 0, 0.55),
    ("Phentermine_Oral", 0, 0.40),
    ("Orlistat_Oral", 0, 0.20),
    ("Tirzepatide_Inj", 4, 0.90),     # launches in quarter index 4 (adoption ramp)
    ("Naltrexone_Bupropion_Oral", 0, 0.30),
    ("Setmelanotide_Inj", 8, 0.08),   # niche, launches later
]

PAYERS = ["Commercial", "Medicare", "Medicaid", "Cash/Other"]
PAYER_BASE_SHARE = np.array([0.52, 0.27, 0.15, 0.06])

YEARS = [2021, 2022, 2023, 2024, 2025]
QUARTERS = [1, 2, 3, 4]
QUARTER_INDEX = {(y, q): i for i, (y, q) in enumerate((y, q) for y in YEARS for q in QUARTERS)}
N_QUARTERS = len(QUARTER_INDEX)  # 20

# Target: expand to 1,000,000+ rows. Base grid = 50 states x 20 quarters x 7 products x 4 payers = 28,000.
# Multiply by a claim-line expansion factor per cell (vectorized repeat) to exceed 1M comfortably.
EXPANSION_PER_CELL = 40  # 28,000 * 40 = 1,120,000 rows


def simulate(n_expansion: int = EXPANSION_PER_CELL, seed: int = RNG_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    state_idx = np.arange(len(STATES))
    quarter_idx = np.arange(N_QUARTERS)
    product_idx = np.arange(len(PRODUCTS))
    payer_idx = np.arange(len(PAYERS))

    # Build the full base grid via meshgrid (vectorized), not nested python loops.
    S, Q, P, PY = np.meshgrid(state_idx, quarter_idx, product_idx, payer_idx, indexing="ij")
    S, Q, P, PY = S.ravel(), Q.ravel(), P.ravel(), PY.ravel()

    n_base = S.shape[0]  # 50*20*7*4 = 280,000

    # Repeat each base combination n_expansion times to simulate multiple claim
    # lines / batches per state-quarter-product-payer cell, reaching 1M+ rows.
    S = np.repeat(S, n_expansion)
    Q = np.repeat(Q, n_expansion)
    P = np.repeat(P, n_expansion)
    PY = np.repeat(PY, n_expansion)
    n = S.shape[0]

    product_launch = np.array([p[1] for p in PRODUCTS])
    product_weight = np.array([p[2] for p in PRODUCTS])

    # Products not yet launched in a given quarter get ~zero volume (small noise floor).
    launched = (Q >= product_launch[P]).astype(float)
    # Adoption ramp: volume grows over quarters-since-launch, saturating.
    quarters_since_launch = np.clip(Q - product_launch[P], 0, None)
    adoption_ramp = 1 - np.exp(-quarters_since_launch / 4.0)

    # Overall market growth trend across the 20 quarters (obesity-drug market grew fast 2021-2025).
    growth_trend = 1.0 + 0.12 * Q

    base_volume = (
        STATE_WEIGHTS[S] * 20000
        * product_weight[P]
        * launched
        * (0.15 + 0.85 * adoption_ramp)
        * growth_trend
    )

    noise = rng.lognormal(mean=0.0, sigma=0.35, size=n)
    rx_count = np.round(base_volume * noise / n_expansion).astype(np.int64)
    rx_count = np.clip(rx_count, 0, None)

    # Payer mix: shift slightly by product (specialty injectables skew more commercial/cash).
    payer_adj = PAYER_BASE_SHARE[PY]
    is_injectable = np.isin(P, [0, 1, 4, 6]).astype(float)
    payer_adj = np.where(
        (PY == 0) & (is_injectable == 1), payer_adj * 1.15,
        np.where((PY == 2) & (is_injectable == 1), payer_adj * 0.7, payer_adj),
    )
    payer_noise = rng.uniform(0.85, 1.15, size=n)
    payer_weight = payer_adj * payer_noise

    unit_price_base = np.select(
        [P == 0, P == 1, P == 2, P == 3, P == 4, P == 5, P == 6],
        [950.0, 850.0, 45.0, 60.0, 1050.0, 500.0, 2400.0],
    )
    unit_price = unit_price_base * rng.uniform(0.9, 1.1, size=n)

    year_arr = np.array([YEARS[0]] * N_QUARTERS)
    qtr_lookup = {i: (y, q) for (y, q), i in QUARTER_INDEX.items()}
    years = np.array([qtr_lookup[i][0] for i in range(N_QUARTERS)])
    quarters = np.array([qtr_lookup[i][1] for i in range(N_QUARTERS)])

    df = pd.DataFrame({
        "state": np.array(STATES)[S],
        "year": years[Q],
        "quarter_num": quarters[Q],
        "quarter_index": Q,
        "product_name": np.array([p[0] for p in PRODUCTS])[P],
        "payer_type": np.array(PAYERS)[PY],
        "rx_count": rx_count,
        "unit_price": np.round(unit_price, 2),
        "payer_mix_weight": np.round(payer_weight, 4),
    })

    # Apply payer mix weight to split rx_count realistically across payer rows
    # that share the same state/quarter/product (normalize within group).
    grp_sum = df.groupby(["state", "quarter_index", "product_name"])["payer_mix_weight"].transform("sum")
    grp_sum = grp_sum.replace(0, np.nan)
    df["payer_share_within_product"] = (df["payer_mix_weight"] / grp_sum).fillna(0.25)

    df = df[df["rx_count"] >= 0].reset_index(drop=True)
    df["claim_id"] = np.arange(1, len(df) + 1)

    return df


if __name__ == "__main__":
    data = simulate()
    print(f"Generated {len(data):,} rows")
    print(data.head())
    print(f"Meets 1,000,000+ requirement: {len(data) >= 1_000_000}")
