"""Draw README charts from the exported result tables in outputs/tables."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
CHARTS = ROOT / "outputs" / "charts"
BLUE, GREY, RED = "#2f6f9f", "#9aa5b1", "#c0504d"


def _save(fig, name):
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=140)
    plt.close(fig)


def rolling_returns():
    df = pd.read_csv(TABLES / "r05_rolling_by_category.csv").sort_values("median_cagr_pct")
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(df) + 1.5))
    y = range(len(df))
    ax.hlines(y, df["p10_cagr_pct"], df["p90_cagr_pct"], color=GREY, linewidth=6, label="10th to 90th percentile")
    ax.plot(df["median_cagr_pct"], y, "o", color=BLUE, label="median")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(df["sub_category"])
    ax.set_xlabel("3-year rolling return, % a year (all windows, 2021-2025)")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "rolling_returns.png")


def drawdowns():
    df = pd.read_csv(TABLES / "r06_drawdown_by_category.csv").sort_values("median_max_drawdown_pct", ascending=False)
    df = df.iloc[::-1]  # barh draws the first row at the bottom, so the shallowest drawdown ends up on top
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(df) + 1.5))
    ax.barh(df["sub_category"], df["median_max_drawdown_pct"], color=RED)
    for y, (dd, days) in enumerate(zip(df["median_max_drawdown_pct"], df["median_days_trough_to_recovery"])):
        label = "not recovered" if pd.isna(days) else f"{int(days)} days to recover"
        ax.text(-0.8, y, label + "  ", va="center", ha="right", fontsize=8, color="white")
    ax.set_xlabel("Median maximum drawdown, % (2018 to 2025)")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "drawdowns.png")


def plan_gap():
    df = pd.read_csv(TABLES / "r09_direct_vs_regular.csv").sort_values("median_gap_pp")
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(df) + 1.5))
    colors = [BLUE if c == "ALL EQUITY CATEGORIES" else GREY for c in df["sub_category"]]
    ax.barh(df["sub_category"], df["median_gap_pp"], color=colors)
    ax.set_xlabel("Median 3-year return gap, Direct minus Regular (percentage points a year)")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "direct_vs_regular.png")


def persistence():
    df = pd.read_csv(TABLES / "r08_quartile_transitions.csv")
    grid = df.pivot(index="quartile_first", columns="quartile_second", values="pct_of_surviving_first_quartile").fillna(0)
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    im = ax.imshow(grid.values, cmap="Blues", vmin=0, vmax=60)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            ax.text(j, i, f"{grid.values[i, j]:.0f}%", ha="center", va="center")
    ax.set_xticks(range(4))
    ax.set_xticklabels(grid.columns)
    ax.set_yticks(range(4))
    ax.set_yticklabels(grid.index)
    ax.set_xlabel("Quartile in the next 3 years (1 = best)")
    ax.set_ylabel("Quartile in the first 3 years")
    fig.colorbar(im, ax=ax, label="% of surviving first-period quartile")
    _save(fig, "persistence.png")


def main():
    rolling_returns()
    drawdowns()
    plan_gap()
    persistence()
    return 0


if __name__ == "__main__":
    sys.exit(main())
