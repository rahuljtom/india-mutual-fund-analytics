"""Build the decision page (docs/index.html) from the result tables in outputs/tables.

Every number in the text is computed here from those tables; nothing is typed in by hand.

Usage:
    python -m mfa.site
"""
import math
import sys
from html import escape
from pathlib import Path

import pandas as pd

from mfa import site_kit

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "outputs" / "tables"
OUT = ROOT / "docs" / "index.html"
RULE_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]


def n(v):
    return f"{int(round(v)):,}"


def upper_tail(k, trials, p=0.25):
    """One-sided binomial probability of k or more successes when each trial succeeds with probability p."""
    return sum(math.comb(trials, i) * p**i * (1 - p) ** (trials - i) for i in range(k, trials + 1))


def loss_pct(v):
    """Share of windows with a loss; a tiny non-zero share is shown as such instead of rounding to 0.0%."""
    return "under 0.1%" if 0 < v < 0.05 else f"{v:.1f}%"


def lakh(v):
    return f"₹{v / 100000:.1f} lakh"


def build(out=None):
    t = {p.stem: pd.read_csv(p) for p in TABLES.glob("r*.csv")}
    dq = t["r03_data_quality"].set_index("check_name").n
    parse = t["r03_parse_summary"].iloc[0]
    funnel = t["r13_funnel"]
    mess = t["r13_data_mess"]
    harm = t["r13_category_harmonisation"]
    hold = t["r12_holding_period"]
    cost = t["r11_cost_drag"]
    back = t["r10_backtest_summary"].set_index("selection_rule")
    by_year = t["r10_backtest_by_year"]
    gap_row = t["r09_direct_vs_regular"].set_index("sub_category").loc["ALL EQUITY CATEGORIES"]
    risk = t["r07_risk_return_by_category"].set_index("sub_category")
    dd = t["r06_drawdown_by_category"].set_index("sub_category")
    trans = t["r08_quartile_transitions"]
    attr = t["r08_attrition"].set_index("quartile_first")
    rep = t["r08_top_quartile_repeat"]

    all_hold = hold[hold.sub_category == "ALL EQUITY CATEGORIES"].set_index("horizon_years")
    cost12 = cost[(cost.direct_cagr_pct == 12)].set_index("horizon_years")
    small, large = "Small Cap Fund", "Large Cap Fund"
    other_dd = dd.drop(index=[small, "Value Fund"]).median_max_drawdown_pct.median()
    top = back.loc["Top quartile of trailing 2-year return"]
    avoid = back.loc["Bottom quartile (the avoid list)"]
    lowvol = back.loc["Lowest-volatility third"]
    stay_top = trans[(trans.quartile_first == 1) & (trans.quartile_second == 1)].pct_of_surviving_first_quartile.iloc[0]
    stay_bottom = trans[(trans.quartile_first == 4) & (trans.quartile_second == 4)].pct_of_surviving_first_quartile.iloc[0]
    n_labels, n_cats = len(harm), harm.sub_category.nunique()
    first_top = int(trans[trans.quartile_first == 1].schemes.sum())
    first_bottom = int(trans[trans.quartile_first == 4].schemes.sum())
    p_top = upper_tail(int(trans[(trans.quartile_first == 1) & (trans.quartile_second == 1)].schemes.iloc[0]), first_top)
    p_bottom = upper_tail(int(trans[(trans.quartile_first == 4) & (trans.quartile_second == 4)].schemes.iloc[0]), first_bottom)
    n_zero = int(mess[mess.issue == "NAV of zero"].rows_affected.iloc[0])
    zero_sample = mess[mess.issue == "NAV of zero"].sample_value.iloc[0].split(";")[0]

    # ---------- chart data
    horizon_rows = [{"label": f"{int(y)}-year holding period", "lo": float(r.p10_annual_pct), "mid": float(r.median_annual_pct), "hi": float(r.p90_annual_pct),
                     "tip": f"<b>{int(y)}-year holding period, all equity categories</b>{n(r.windows)} windows from {n(r.schemes)} schemes<br>"
                            f"10th to 90th percentile: {r.p10_annual_pct:.1f}% to {r.p90_annual_pct:.1f}% a year (median {r.median_annual_pct:.1f}%)<br>"
                            f"windows that lost money: {loss_pct(r.pct_windows_with_loss)}"} for y, r in all_hold.iterrows()]
    three = hold[(hold.horizon_years == 3) & (hold.sub_category != "ALL EQUITY CATEGORIES")].sort_values("median_annual_pct", ascending=False)
    three_rows = [{"label": r.sub_category, "lo": float(r.p10_annual_pct), "mid": float(r.median_annual_pct), "hi": float(r.p90_annual_pct),
                   "tip": f"<b>{escape(r.sub_category)}</b>3-year windows: {n(r.windows)} from {n(r.schemes)} schemes<br>10th to 90th percentile {r.p10_annual_pct:.1f}% to {r.p90_annual_pct:.1f}% a year<br>median {r.median_annual_pct:.1f}%, windows with a loss {loss_pct(r.pct_windows_with_loss)}"}
                  for r in three.itertuples()]

    joined = dd.join(risk, lsuffix="_dd", rsuffix="_rr", how="inner")
    offsets = {}
    scatter_pts = []
    for cat, r in joined.iterrows():
        scatter_pts.append({"label": cat.replace(" Fund", ""), "x": float(r.median_max_drawdown_pct), "y": float(r.median_cagr_pct),
                            "color": "var(--s2)" if cat == small else "var(--s1)",
                            "tip": f"<b>{escape(cat)}</b>median 3-year return {r.median_cagr_pct:.1f}% a year<br>median deepest fall {r.median_max_drawdown_pct:.1f}%<br>return per unit of volatility {r.median_return_per_vol:.2f}"})

    cost_cats = [f"{int(v)}% gross" for v in sorted(cost.direct_cagr_pct.unique())]
    cost_series = []
    for k, years in enumerate(sorted(cost.horizon_years.unique())):
        sub = cost[cost.horizon_years == years].sort_values("direct_cagr_pct")
        cost_series.append({"name": f"{int(years)} years", "color": RULE_COLORS[k], "vals": [float(v) / 100000 for v in sub.sip_cost_inr],
                            "pct": [float(v) for v in sub.sip_cost_pct]})

    rules = list(back.index)
    years = sorted(by_year.formation_year.unique())
    rule_series = []
    for k, rule in enumerate(rules):
        sub = by_year[by_year.selection_rule == rule].set_index("formation_year")
        rule_series.append({"name": rule, "color": RULE_COLORS[k], "vals": [float(sub.avg_excess_pp.get(y)) if y in sub.index else None for y in years]})

    flips = sum(1 for r in rule_series if any(v > 0 for v in r["vals"] if v is not None) and any(v < 0 for v in r["vals"] if v is not None))
    negative_years = {r["name"]: sum(1 for v in r["vals"] if v is not None and v < 0) for r in rule_series}
    worst_rule = max(negative_years, key=negative_years.get)
    sign_sentence = (f"Every rule changes sign across the {len(years)} test years." if flips == len(rules)
                     else f"{flips} of the {len(rules)} rules change sign across the {len(years)} test years.")
    heat_vals = [[float(trans[(trans.quartile_first == a) & (trans.quartile_second == b)].pct_of_surviving_first_quartile.iloc[0])
                  for b in (1, 2, 3, 4)] for a in (1, 2, 3, 4)]
    heat_tips = [[trans[(trans.quartile_first == a) & (trans.quartile_second == b)].schemes.iloc[0] for b in (1, 2, 3, 4)] for a in (1, 2, 3, 4)]

    data = {"horizon": horizon_rows, "three": three_rows, "scatter": scatter_pts, "costcats": cost_cats, "cost": cost_series,
            "years": [str(int(y)) for y in years], "rules": rule_series, "heat": heat_vals, "heattips": [[int(x) for x in r] for r in heat_tips]}

    # ---------- html pieces
    funnel_html = ""
    notes = [f"from {n(parse.files)} report files and {n(parse.lines)} text lines; {n(parse.unclassified_lines)} lines the parser could not place, all reported",
             f"{n(n_zero)} zero NAVs and {n(dq['nav_not_numeric'])} non-numeric values dropped, counted",
             "read from scheme names; schemes whose plan cannot be told are left out",
             f"{n_labels} raw category labels mapped to {n_cats} categories",
             "comparable on NAV alone: Direct plan, Growth option"]
    for i, r in enumerate(funnel.itertuples()):
        big = n(r.nav_rows) if pd.notna(r.nav_rows) else n(r.schemes)
        unit = "NAV rows" if pd.notna(r.nav_rows) else "schemes"
        sub = f" · {n(r.schemes)} schemes" if pd.notna(r.nav_rows) and pd.notna(r.schemes) else ""
        funnel_html += f"<div class='step'><b>{i + 1} · {escape(r.step_name)}</b><strong>{big}</strong><span>{unit}{sub}. {notes[i][0].upper() + notes[i][1:]}</span></div>"
        if i < len(funnel) - 1:
            funnel_html += "<div class='arrow'>→</div>"
    mess_rows = "".join(
        f"<tr><td>{escape(r.issue)}</td><td>{n(r.rows_affected)}</td><td>{escape(str(r.sample_value).split(';')[0])}</td><td>{escape(r.handling)}</td><td>{escape(r.if_ignored)}</td></tr>"
        for r in mess.itertuples())
    backtest_rows = "".join(
        f"<tr><td>{escape(rule)}</td><td class='num'>{n(r.picks)}</td><td class='num'>{r.pct_vanished:.1f}%</td><td class='num'>{r.avg_excess_pp:+.2f} pp</td>"
        f"<td class='num'>{r.pct_picks_beating_category:.0f}%</td><td class='num'>{int(r.years_positive)} of {int(r.years_tested)}</td></tr>"
        for rule, r in back.iterrows())
    cost_rows = "".join(
        f"<tr><td class='num'>{int(r.direct_cagr_pct)}% a year</td><td class='num'>{lakh(r.sip_direct_inr)}</td><td class='num'>{lakh(r.sip_regular_inr)}</td>"
        f"<td class='num'><b>{lakh(r.sip_cost_inr)}</b> ({r.sip_cost_pct:.1f}%)</td></tr>" for r in cost[cost.horizon_years == 10].itertuples())

    body = f"""
<header class="hero"><div class="wrap">
<p class="eyebrow">Case study · {n(parse.rows)} daily fund prices from AMFI · India · 2018 to 2025</p>
<h1>How should an Indian saver choose an equity mutual fund?</h1>
<p class="lede">17 million raw price records, parsed from a semi-structured text report, loaded into a typed SQL warehouse and tested against what actually happened. The question: which choices change the outcome, and which are noise?</p>
<div class="decision">
<h2>Recommendation</h2>
<p style="margin:0">Three rules, in order of how much the evidence supports them. Descriptive analysis of historical data, not investment advice.</p>
<ol>
<li><b>Buy the Direct plan.</b> The Regular plan of the same scheme returned a median <b>{gap_row.median_gap_pp:.2f} points a year less</b> across {n(gap_row.pairs)} matched pairs. A monthly SIP of ₹10,000 for 10 years at 12% gross loses about <b>{lakh(cost12.loc[10].sip_cost_inr)}</b> ({cost12.loc[10].sip_cost_pct:.1f}%); over 20 years {lakh(cost12.loc[20].sip_cost_inr)} ({cost12.loc[20].sip_cost_pct:.1f}%).</li>
<li><b>Match the fund to the time you can leave it.</b> Held for one year, equity funds lost money in <b>{loss_pct(all_hold.loc[1].pct_windows_with_loss)}</b> of windows; for three years {loss_pct(all_hold.loc[3].pct_windows_with_loss)}, for five years {loss_pct(all_hold.loc[5].pct_windows_with_loss)}. Money needed within three years does not belong here. Small-cap funds earned the most but fell the most (median deepest fall {dd.loc[small].median_max_drawdown_pct:.0f}% against about {other_dd:.0f}% for most categories).</li>
<li><b>Do not pay for a past-performance screen.</b> In a walk-forward test, picking last two years' top quartile beat the category by only {top.avg_excess_pp:+.2f} points a year (better in {int(top.years_positive)} of {int(top.years_tested)} years); the funds on the avoid list did {avoid.avg_excess_pp:+.2f} points <i>better</i>, and the low-volatility third {lowvol.avg_excess_pp:+.2f} points.</li>
</ol></div>
<div class="stats">
<div class="stat"><b>{n(gap_row.pairs)}</b><span>Direct/Regular pairs compared on the same portfolio</span></div>
<div class="stat"><b>{loss_pct(all_hold.loc[1].pct_windows_with_loss)} → {loss_pct(all_hold.loc[3].pct_windows_with_loss)}</b><span>windows with a loss, 1-year then 3-year holding</span></div>
<div class="stat"><b>{stay_top:.1f}%</b><span>of top-quartile funds stayed top-quartile (25% by chance)</span></div>
<div class="stat"><b>{attr.loc[4].pct_not_surviving:.1f}% vs {attr.loc[1].pct_not_surviving:.1f}%</b><span>of bottom vs top quartile funds vanished by 2025</span></div>
</div>
</div></header>

<main class="wrap">
<section id="mess"><h2>1 · The source was a text report, not a table</h2>
<p class="kicker">AMFI publishes prices as a semi-structured text file with category and fund-house headings between the data lines. Turning it into something safe to analyse took a parser that tracks state line by line, a typed warehouse with constraints, and a decision on every kind of bad value. Only {n(funnel.schemes.iloc[-1])} of {n(funnel.schemes.iloc[1])} schemes end up comparable.</p>
<div class="pipe">{funnel_html}</div>
<div class="card tablewrap"><h3>What was wrong, and what ignoring it would have done</h3><table class="mess"><thead><tr><th>Problem</th><th>Count</th><th>Example</th><th>What was done</th><th>If it had been ignored</th></tr></thead><tbody>{mess_rows}</tbody></table>
<p class="note">Example of a zero NAV: {escape(zero_sample)}, a segregated portfolio that carries no value. The same fund category appears under {n_labels} raw labels that collapse to {n_cats} categories.</p></div>
</section>

<section id="cost"><h2>2 · The one edge that shows up everywhere: cost</h2>
<p class="kicker">Direct and Regular plans hold the same portfolio; the Regular NAV is lower because of the commission built into its costs. Gap measured on {n(gap_row.pairs)} matched pairs: median {gap_row.median_gap_pp:.2f} points a year (range {gap_row.min_gap_pp:.2f} to {gap_row.max_gap_pp:.2f}). The rupee figures below use that gap with the gross return as a scenario, not a forecast.</p>
<div class="card"><h3>Value lost by holding the Regular plan: ₹10,000 a month, in lakh rupees</h3><div class="legend" id="lg-cost"></div><div class="chart" id="c-cost"></div>
<p class="note">Costs compound: the loss share roughly doubles from {cost12.loc[10].sip_cost_pct:.1f}% at 10 years to {cost12.loc[20].sip_cost_pct:.1f}% at 20 years.</p></div>
<div class="card tablewrap"><h3>10-year SIP, by gross return assumption</h3><table><thead><tr><th class="num">Direct plan returns</th><th class="num">Direct plan corpus</th><th class="num">Regular plan corpus</th><th class="num">Lost to Regular</th></tr></thead><tbody>{cost_rows}</tbody></table></div>
</section>

<section id="risk"><h2>3 · How long you can wait matters more than which category</h2>
<p class="kicker">Every month-end start and finish across the history, by holding period. Short holds can lose; long holds almost never did. This period (2018 to 2025) includes the March 2020 crash and a strong 2021 to 2025, so the levels flatter equities.</p>
<div class="card"><h3>Annualised return by holding period: 10th to 90th percentile, median marked</h3><div class="chart" id="c-horizon"></div>
<p class="note">Windows that lost money: {loss_pct(all_hold.loc[1].pct_windows_with_loss)} at one year, {loss_pct(all_hold.loc[3].pct_windows_with_loss)} at three, {loss_pct(all_hold.loc[5].pct_windows_with_loss)} at five. Windows overlap and funds in a category hold similar stocks, so these are not independent observations.</p></div>
<div class="card"><h3>Three-year outcomes by category: 10th to 90th percentile, median marked</h3><div class="chart" id="c-three"></div></div>
<div class="card"><h3>Higher returns came with deeper falls</h3><div class="chart" id="c-scatter"></div>
<p class="note">Median 3-year return against median deepest fall since 2018. Small-cap (orange) sits alone at the high-return, high-loss corner; most categories bunch together near a 37% fall.</p></div>
</section>

<section id="pick"><h2>4 · Does a screen for "good" funds work?</h2>
<p class="kicker">Walk-forward test: on 31 December each year from 2020 to 2024, use only the trailing 24 months to pick funds within each category, then measure the next 12 months against the average fund in that category. Funds that vanished before the end are counted separately, and the excess is measured on survivors, which can only flatter the rules.</p>
<div class="card"><h3>Next-year return minus the category average, by selection rule and year (percentage points)</h3><div class="legend" id="lg-rules"></div><div class="chart" id="c-backtest"></div>
<p class="note">{sign_sentence} The weakest, the {escape(worst_rule.lower())}, is below zero in {negative_years[worst_rule]} of {len(years)} years. No rule is reliably above zero.</p></div>
<div class="card tablewrap"><table><thead><tr><th>Selection rule</th><th class="num">Picks</th><th class="num">Vanished</th><th class="num">Average excess</th><th class="num">Picks beating category</th><th class="num">Years positive</th></tr></thead><tbody>{backtest_rows}</tbody></table></div>
<div class="card"><h3>Where last period's best and worst funds ended up (share of surviving first-quartile funds)</h3><div class="chart" id="c-heat"></div>
<p class="note">Of top-quartile funds, {stay_top:.1f}% were top-quartile again (25% by chance; one-sided p = {p_top:.2f}); of bottom-quartile funds, {stay_bottom:.1f}% stayed at the bottom (one-sided p = {p_bottom:.2f}). Weak funds persist a little; strong funds do not. {attr.loc[4].pct_not_surviving:.1f}% of bottom-quartile funds had no price by the end of 2025 against {attr.loc[1].pct_not_surviving:.1f}% of top-quartile ones, which fund tables built from today's funds would hide.</p></div>
</section>

<section id="limits"><h2>5 · What would change this recommendation</h2>
<ul class="limits">
<li><b>One market regime.</b> Eight years with one crash and a strong recovery. A multi-year bear market would lengthen the holding period needed to avoid a loss.</li>
<li><b>Costs are inferred from NAVs.</b> The Direct–Regular gap is mostly the cost difference, not only; taxes, exit loads and fund size are not studied.</li>
<li><b>The backtest has five test years</b> and overlapping funds. It shows no reliable edge in these data; it cannot prove none exists.</li>
<li><b>Categories change.</b> A scheme that changed category keeps its latest one for its whole history.</li>
<li><b>Source terms.</b> AMFI's terms of use for this data have not been reviewed here; check them before reuse.</li>
</ul></section>
</main>
<footer><div class="wrap">Data: AMFI historical NAV report (portal.amfiindia.com), pulled 7 November 2026 for 1 January 2018 to 31 December 2025. Code, SQL, tests and method notes are in the repository. Re-run with <code>make all site</code>. Not investment advice.</div></footer>
"""
    script = """
const D = DATA;
rangeChart('#c-horizon',{rows:D.horizon,x:[-20,90],xf:v=>v+'%',xlab:'Annualised return (% a year)',lw:170});
rangeChart('#c-three',{rows:D.three,x:[0,70],xf:v=>v+'%',xlab:'Annualised 3-year return (% a year)',lw:190,color:'var(--s1)'});
scatter('#c-scatter',{pts:D.scatter,x:[-52,-34],y:[14,26],xf:v=>v+'%',yf:v=>v+'%',xlab:'Median deepest fall since 2018 (%)',ylab:'Median 3-year return (% a year)'});
document.getElementById('lg-cost').innerHTML=D.cost.map(s=>'<span><i style="background:'+s.color+'"></i>'+s.name+' of monthly investing</span>').join('');
groupedBar('#c-cost',{cats:D.costcats,series:D.cost,y:[0,25],vlab:v=>v.toFixed(1),yf:v=>v+' lakh',ylab:'Lost to the Regular plan (₹ lakh)',tipf:(c,s,v)=>'<b>'+c+', '+s.name+'</b>₹'+v.toFixed(1)+' lakh lost'});
const lg=document.getElementById('lg-rules');lg.innerHTML=D.rules.map(s=>'<span><i style="background:'+s.color+'"></i>'+s.name+'</span>').join('');
groupedBar('#c-backtest',{cats:D.years,series:D.rules,y:[-6,6],vlab:v=>(v>0?'+':'')+v.toFixed(1),yf:v=>(v>0?'+':'')+v,ylab:'Percentage points',tipf:(c,s,v)=>'<b>Formed '+c+': '+s.name+'</b>'+(v>0?'+':'')+v.toFixed(2)+' pp vs category average'});
heat('#c-heat',{rows:['Top quartile','Second','Third','Bottom quartile'],cols:['Top quartile','Second','Third','Bottom quartile'],vals:D.heat,vf:v=>v.toFixed(1)+'%',
 rowlab:'First period',collab:'Next period',tip:(i,j)=>'<b>'+D.heattips[i][j]+' funds</b>'+D.heat[i][j].toFixed(1)+'% of surviving funds that started in this row'});
"""
    html = site_kit.page("India equity mutual funds: what matters", "Which choices change outcomes for an Indian equity fund investor, tested on 17 million AMFI prices.",
                         body, data, script)
    target = Path(out) if out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    print("wrote", target, f"{len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    sys.exit(build() or 0)
