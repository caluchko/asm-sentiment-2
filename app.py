"""ASM Media Sentiment — Phase 2 dashboard.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from analysis import country_analysis, framing_analysis, tone_analysis  # noqa: E402

st.set_page_config(page_title="ASM Media Sentiment — Phase 2", layout="wide")

METHODOLOGY_TAB_MD = Path(__file__).resolve().parent / "methodology_tab.md"


@st.cache_data
def load_processed() -> pd.DataFrame:
    if not config.PROCESSED_PARQUET.exists():
        return pd.DataFrame()
    return pd.read_parquet(config.PROCESSED_PARQUET)


df = load_processed()
st.title("ASM Media Sentiment — Phase 2")
st.caption("GDELT GKG via BigQuery · Ghana & Brazil · per-article tone, minerals, "
           "language, and zero-shot framing classification with Claude Haiku 4.5")

if df.empty:
    st.warning("No processed data. Run extract/bigquery_extract.py then extract/parse_gkg.py.")
    st.stop()

countries = st.sidebar.multiselect("Country", ["Ghana", "Brazil"], default=["Ghana", "Brazil"])
view = df[df["country"].isin(countries)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Articles", f"{len(view):,}")
c2.metric("Ghana", f"{(view['country'] == 'Ghana').sum():,}")
c3.metric("Brazil", f"{(view['country'] == 'Brazil').sum():,}")
c4.metric("Mean tone", f"{view['tone'].mean():.2f}")

tab_method, tab_tone, tab_country, tab_lang, tab_framing = st.tabs(
    ["Methodology", "Tone trends", "Subject countries", "Language",
     "Zero-shot classification"]
)

with tab_method:
    if METHODOLOGY_TAB_MD.exists():
        st.markdown(METHODOLOGY_TAB_MD.read_text())
    else:
        st.warning(f"Methodology text not found at {METHODOLOGY_TAB_MD.name}.")

    st.markdown("##### How articles were found and attributed")
    fm = df["filter_match"].value_counts()
    gh_kw, gh_th = int(fm.get("ghana_keyword", 0)), int(fm.get("ghana_theme", 0))
    br_kw, br_th = int(fm.get("brazil_keyword", 0)), int(fm.get("brazil_theme", 0))
    other = int(fm.get("other", 0))
    gh, br = gh_kw + gh_th, br_kw + br_th
    total = gh + br + other
    GREEN, RED, GREY, BLUE = "#54a24b", "#e45756", "#b0b0b0", "#4c78a8"
    ext_labels = [
        f"GKG matches ({total:,})",                       # 0
        f"Ghana ({gh:,})",                                # 1
        f"Brazil ({br:,})",                               # 2
        f"Unattributed ({other:,})",                      # 3
        f"“galamsey” keyword ({gh_kw:,})",                # 4
        f"small-scale-mining topic ({gh_th:,})",          # 5
        f"“garimpo” keyword ({br_kw:,})",                 # 6
        f"small-scale-mining topic ({br_th:,})",          # 7
    ]
    ext_node_colors = [BLUE, GREEN, RED, GREY, GREEN, "#88b04b", RED, "#f0a3a3"]
    ext_src = [0, 0, 0, 1, 1, 2, 2]
    ext_tgt = [1, 2, 3, 4, 5, 6, 7]
    ext_val = [gh, br, other, gh_kw, gh_th, br_kw, br_th]
    ext_link_colors = [
        "rgba(84,162,75,.40)", "rgba(228,87,86,.40)", "rgba(176,176,176,.55)",
        "rgba(84,162,75,.30)", "rgba(84,162,75,.30)",
        "rgba(228,87,86,.30)", "rgba(228,87,86,.30)"]
    fig_ext = go.Figure(go.Sankey(
        node=dict(label=ext_labels, color=ext_node_colors, pad=18, thickness=16,
                  line=dict(color="white", width=0.5)),
        link=dict(source=ext_src, target=ext_tgt, value=ext_val, color=ext_link_colors)))
    fig_ext.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), font_size=12)
    st.plotly_chart(fig_ext, use_container_width=True)
    st.caption(
        "Each article is tagged by the single search clause that matched it — a country "
        "keyword, or GDELT's small-scale-mining topic. The "
        f"{other:,} *unattributed* articles were caught by broad terms (English "
        "“illegal mining”, Portuguese “garimpeiro”) but couldn't be confidently tied to "
        "Ghana or Brazil, so they are excluded from the country results and from the "
        "framing sample.")

    st.markdown("##### From sample to framing analysis")
    _fdf = framing_analysis.load()
    if _fdf.empty:
        st.info("No Claude classifications yet — run the classification step to populate "
                "this funnel.")
    else:
        fn = framing_analysis.funnel(_fdf)
        clf_labels = [
            f"Stratified sample ({fn['sampled']})",                 # 0
            f"No usable text ({fn['excluded_no_text']})",           # 1
            f"Classified by Claude ({fn['classified']})",           # 2
            f"Not about ASM ({fn['excluded_not_relevant']})",       # 3
            f"Framing analysis set ({fn['analysis']})",             # 4
        ]
        clf_node_colors = [BLUE, GREY, BLUE, GREY, GREEN]
        clf_src = [0, 0, 2, 2]
        clf_tgt = [1, 2, 3, 4]
        clf_val = [fn["excluded_no_text"], fn["classified"],
                   fn["excluded_not_relevant"], fn["analysis"]]
        clf_link_colors = ["rgba(176,176,176,.55)", "rgba(76,120,168,.35)",
                           "rgba(176,176,176,.55)", "rgba(84,162,75,.40)"]
        fig_clf = go.Figure(go.Sankey(
            node=dict(label=clf_labels, color=clf_node_colors, pad=18, thickness=16,
                      line=dict(color="white", width=0.5)),
            link=dict(source=clf_src, target=clf_tgt, value=clf_val, color=clf_link_colors)))
        fig_clf.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), font_size=12)
        st.plotly_chart(fig_clf, use_container_width=True)
        st.caption(
            "Articles with no recoverable text and no quotations, and those Claude judged "
            "not actually about artisanal mining, are set aside; framing, stance and "
            "solution-orientation results are computed on the remaining analysis set.")

with tab_tone:
    mt = tone_analysis.monthly_tone(view)
    if not mt.empty:
        st.plotly_chart(
            px.line(mt, x="month", y="mean_tone", color="country", markers=True,
                    title="Mean article tone by month"),
            use_container_width=True)
        st.plotly_chart(
            px.bar(mt, x="month", y="volume", color="country", barmode="group",
                   title="Article volume by month"),
            use_container_width=True)
        st.plotly_chart(
            px.histogram(tone_analysis.tone_distribution(view), x="tone", color="country",
                         nbins=50, barmode="overlay", opacity=0.6,
                         title="Tone distribution"),
            use_container_width=True)

with tab_country:
    for c in countries:
        st.subheader(f"{c}-filtered articles are about:")
        sc = country_analysis.subject_country_counts(df, c).head(15)
        st.plotly_chart(px.bar(sc, x="articles", y="subject_countries", orientation="h"),
                        use_container_width=True)

with tab_lang:
    lang = (view.groupby(["original_language", "country"]).size()
            .rename("articles").reset_index())
    st.plotly_chart(
        px.bar(lang, x="original_language", y="articles", color="country",
               barmode="group", title="Original language (pre-translation)"),
        use_container_width=True)

with tab_framing:
    fdf = framing_analysis.load()
    if fdf.empty:
        st.info("No Claude classifications yet. Run classify/sample.py then "
                "classify/run_classification.py (needs ANTHROPIC_API_KEY).")
    else:
        rel = framing_analysis.relevant_only(fdf)
        f = framing_analysis.funnel(fdf)
        n_rel = f["analysis"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sampled for classification", f["sampled"])
        m2.metric("Excluded — no text or quotes", f["excluded_no_text"])
        m3.metric("Excluded — not relevant (ASM)", f["excluded_not_relevant"])
        m4.metric("Analysis set", n_rel)
        fp = framing_analysis.false_positive_rate(fdf)
        fp_str = "; ".join(
            f"{r['country']} {r['fp_rate']:.1%} ({int(r['not_relevant'])}/{int(r['classified'])})"
            for _, r in fp.iterrows())
        st.caption(
            f"Funnel: {f['sampled']} sampled → "
            f"{f['excluded_no_text']} dropped (no full text and no quotes — "
            f"themes+tone+URL only, circular with the filter) → "
            f"{f['classified']} classified by Claude → "
            f"{f['excluded_not_relevant']} dropped as not actually about ASM → "
            f"{n_rel} in the analysis set. "
            f"Per-country false-positive rate (not-relevant share of classified): {fp_str}. "
            f"Framing, stance & solution orientation below are computed on these "
            f"{n_rel} articles only.")

        # ---- Classification explorer (analysis set, interactively filtered) ----
        base = framing_analysis.with_derived(rel)
        base = base[base["country"].isin(countries)]
        if base.empty:
            st.warning("No analysis-set articles for the selected country.")
            st.stop()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Classification filters")
        st.sidebar.caption(f"Apply to the {len(base)} analysis-set articles "
                           "(framing/stance/tone charts below).")
        fr_opts = sorted(base["framing"].dropna().unique())
        sel_fr = st.sidebar.multiselect("Framing", fr_opts, default=fr_opts)
        stance_opts = [s for s in framing_analysis.STANCE_ORDER
                       if s in base["stance"].unique()]
        sel_st = st.sidebar.multiselect("Stance", stance_opts, default=stance_opts)
        so_opts = [s for s in framing_analysis.SOLUTION_ORDER
                   if s in base["solution_orientation"].unique()]
        sel_so = st.sidebar.multiselect("Solution orientation", so_opts, default=so_opts)
        sel_min = st.sidebar.radio("Mineral", ["All", "Gold", "Non-gold"], horizontal=True)
        tq_opts = sorted(base["text_quality"].dropna().unique())
        sel_tq = st.sidebar.multiselect("Text quality", tq_opts, default=tq_opts)
        tlo, thi = float(base["tone"].min()), float(base["tone"].max())
        sel_tone = st.sidebar.slider("GDELT tone band", tlo, thi, (tlo, thi))
        sel_conf = st.sidebar.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

        v = base[
            base["framing"].isin(sel_fr)
            & base["stance"].isin(sel_st)
            & base["solution_orientation"].isin(sel_so)
            & base["text_quality"].isin(sel_tq)
            & base["tone"].between(*sel_tone)
            & (base["confidence"] >= sel_conf)
        ]
        if sel_min != "All":
            v = v[v["mineral_class"] == ("gold" if sel_min == "Gold" else "non-gold")]

        st.subheader("Classification explorer")
        st.caption(f"Showing {len(v)} of {len(base)} analysis-set articles after filters "
                   f"({(v['country'] == 'Ghana').sum()} Ghana / "
                   f"{(v['country'] == 'Brazil').sum()} Brazil).")
        if v.empty:
            st.warning("No articles match the current classification filters.")
            st.stop()

        FRAMING_ORDER = framing_analysis.FRAMING_TOP + ["other"]
        # Diverging valence palette (red = most critical/problem, blue = most
        # sympathetic/solution, greys in the middle) — distinct from framing's
        # qualitative colors, signalling these dimensions have direction.
        DIVERGING_COLORS = {
            "critical": "#d73027", "mixed": "#bdbdbd", "neutral": "#969696",
            "sympathetic": "#4575b4",
            "problem_focused": "#d73027", "balanced": "#bdbdbd",
            "not_applicable": "#969696", "solution_focused": "#4575b4",
        }
        def composition_bar(dim, order, title, color_map=None, dim_label=None):
            d = v.groupby(["country", dim], observed=True).size().rename("articles").reset_index()
            d["pct"] = d["articles"] / d.groupby("country")["articles"].transform("sum") * 100
            return px.bar(d, x="pct", y="country", color=dim, orientation="h", title=title,
                          category_orders={dim: order}, color_discrete_map=color_map or {},
                          hover_data={"articles": True, "pct": ":.1f"},
                          labels={"pct": "% within country", dim: dim_label or dim})

        st.markdown("#### Primary framing composition by country (share within country)")
        st.plotly_chart(
            composition_bar("framing_grouped", FRAMING_ORDER, "Primary framing",
                            dim_label="primary framing"),
            use_container_width=True)

        st.markdown("#### Stance & solution orientation (share within country)")
        st.caption("Coloured by valence: red = critical / problem-focused, "
                   "blue = sympathetic / solution-focused, grey = the middle categories.")
        dc1, dc2 = st.columns(2)
        dc1.plotly_chart(
            composition_bar("stance", framing_analysis.STANCE_ORDER, "Stance", DIVERGING_COLORS),
            use_container_width=True)
        dc2.plotly_chart(
            composition_bar("solution_orientation", framing_analysis.SOLUTION_ORDER,
                            "Solution orientation", DIVERGING_COLORS),
            use_container_width=True)

        st.markdown("#### Mineral type vs primary framing")
        st.caption("Mineral is from Claude's classification (it reads the article text), "
                   "not the GKG theme tagger — so this relates two Claude outputs, not an "
                   "independent GDELT measure. Gold dominates; the non-gold set is small, "
                   "so read it as suggestive, not conclusive.")
        md = v.groupby(["mineral_class", "framing_grouped"], observed=True).size().rename("articles").reset_index()
        md["pct"] = md["articles"] / md.groupby("mineral_class")["articles"].transform("sum") * 100
        mcounts = v["mineral_class"].value_counts().to_dict()
        md["mineral_class"] = md["mineral_class"].map(
            lambda m: f"{m} (n={mcounts.get(m, 0)})")
        st.plotly_chart(
            px.bar(md, x="pct", y="mineral_class", color="framing_grouped",
                   orientation="h", title="Primary framing share: gold vs non-gold",
                   category_orders={"framing_grouped": FRAMING_ORDER},
                   hover_data={"articles": True, "pct": ":.1f"},
                   labels={"pct": "% within mineral class", "framing_grouped": "primary framing"}),
            use_container_width=True)

        # ---- Heatmaps over ALL framing categories (no 'other' bucket) ----
        fr_order = ([f for f in framing_analysis.FRAMING_TOP if f in v["framing"].unique()]
                    + sorted(f for f in v["framing"].unique()
                             if f not in framing_analysis.FRAMING_TOP))
        fr_counts = v["framing"].value_counts().to_dict()
        hm_norm = st.radio(
            "Heatmap cell values",
            ["Row % (within framing)", "Total % (of all articles)", "Count"],
            horizontal=True,
            help="Row % shows the stance/solution mix *within* each framing — it answers "
                 "'given this framing, what stance?' and is robust to the framing imbalance. "
                 "Total % shows each cell's share of all articles, so it is dominated by the "
                 "largest framing (criminal_illegal). Count shows raw article counts.")

        def framing_heatmap(col, col_order, title):
            if hm_norm.startswith("Row"):
                ct, fmt, clab = pd.crosstab(v["framing"], v[col], normalize="index"), ".0%", "row share"
            elif hm_norm.startswith("Total"):
                ct, fmt, clab = pd.crosstab(v["framing"], v[col], normalize="all"), ".1%", "share of all"
            else:
                ct, fmt, clab = pd.crosstab(v["framing"], v[col]), "d", "articles"
            ct = ct.reindex(index=fr_order,
                            columns=[c for c in col_order if c in ct.columns]).fillna(0)
            ct.index = [f"{f} (n={fr_counts.get(f, 0)})" for f in ct.index]
            return px.imshow(ct, text_auto=fmt, color_continuous_scale="Blues",
                             aspect="auto", title=title,
                             labels={"x": col, "y": "primary framing", "color": clab})

        st.markdown("#### Primary framing × stance")
        st.plotly_chart(
            framing_heatmap("stance", framing_analysis.STANCE_ORDER, "Primary framing × stance"),
            use_container_width=True)

        st.markdown("#### Primary framing × solution orientation")
        st.plotly_chart(
            framing_heatmap("solution_orientation", framing_analysis.SOLUTION_ORDER,
                            "Primary framing × solution orientation"),
            use_container_width=True)

        # ---- Secondary framings (multi-label) ----
        st.markdown("#### Secondary framings")
        st.caption("Most articles carry a primary plus several secondary framings (mean ~2). "
                   "Secondary labels surface themes the single primary label buries "
                   "(e.g. environmental_threat and policy_progress are far more common as "
                   "secondary). 'gender' appears only as a secondary framing.")
        sec = v[["country", "framing"]].copy()
        sec["secondary"] = v["secondary_framings"].map(framing_analysis._as_list)
        sec_long = sec.explode("secondary").dropna(subset=["secondary"])

        prim_ct = v.groupby("framing").size().rename("count").reset_index()
        prim_ct["role"] = "primary"
        sec_ct = (sec_long.groupby("secondary").size().rename("count").reset_index()
                  .rename(columns={"secondary": "framing"}))
        sec_ct["role"] = "secondary mention"
        prev = pd.concat([prim_ct, sec_ct], ignore_index=True)
        prev_order = prev.groupby("framing")["count"].sum().sort_values().index.tolist()
        st.plotly_chart(
            px.bar(prev, x="count", y="framing", color="role", orientation="h", barmode="group",
                   category_orders={"framing": prev_order},
                   title="How often each framing appears: primary vs secondary mention"),
            use_container_width=True)

        st.caption("Co-occurrence: for each primary framing (row), which secondary framings "
                   "accompany it (article counts).")
        co = pd.crosstab(sec_long["framing"], sec_long["secondary"])
        co = co.reindex(index=[f for f in fr_order if f in co.index]).fillna(0).astype(int)
        st.plotly_chart(
            px.imshow(co, text_auto="d", color_continuous_scale="Blues", aspect="auto",
                      labels={"x": "secondary framing", "y": "primary framing", "color": "articles"},
                      title="Primary × secondary framing co-occurrence"),
            use_container_width=True)

        # ---- GDELT tone violins (moved to end of page) ----
        st.markdown("#### GDELT tone vs Claude labels (convergent validity)")
        st.caption("Does GDELT's lexical tone track Claude's labels? More critical / "
                   "problem-focused articles should sit lower (more negative). Tone is "
                   "lexical, so victim-focused sympathetic coverage can still read negative.")
        vr1c1, vr1c2 = st.columns(2)
        vr1c1.plotly_chart(
            px.box(v, x="stance", y="tone", color="country", points="outliers",
                   category_orders={"stance": framing_analysis.STANCE_ORDER},
                   title="Tone by stance"),
            use_container_width=True)
        vr1c2.plotly_chart(
            px.box(v, x="framing_grouped", y="tone", color="country", points="outliers",
                   category_orders={"framing_grouped": FRAMING_ORDER},
                   labels={"framing_grouped": "primary framing"},
                   title="Tone by primary framing"),
            use_container_width=True)
        vr2c1, vr2c2 = st.columns(2)
        vr2c1.plotly_chart(
            px.box(v, x="solution_orientation", y="tone", color="country", points="outliers",
                   category_orders={"solution_orientation": framing_analysis.SOLUTION_ORDER},
                   title="Tone by solution orientation"),
            use_container_width=True)
