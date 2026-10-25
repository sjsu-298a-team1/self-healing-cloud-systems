import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_access as da
import ui

LABEL = {"official_armor_v1": "Official ARMOR (126 / 84)", "model1_candidate_100_26_84_v1": "Proposed Model 1 (100 / 26 / 84)",
         "model1_alternative_v1": "Recommended alternative (needs approval)"}
CLASSES = ["Container Hardware", "Container Network", "Node CPU", "Node Disk", "Node Memory"]
REQUIRED_SPAN = 719


def render():
    ui.hero("Data Splitting", "Chronological, incident-group-aware splits - official ARMOR reproduction kept separate from our Model 1 candidate")
    mans = da.split_manifests()
    df = da.cload("splits", "case_split_assignments.csv")
    if not mans or df is None:
        ui.missing("split manifests")
        return
    cand = mans.get("model1_candidate_100_26_84_v1")
    if cand and not cand["usable"]:
        failed = [c for c in cand["checks"] if c["status"] == "FAIL"]
        ui.note("<b>The proposed 100 / 26 / 84 split FAILS its hard checks and is marked unusable.</b> " + " ".join(f"{c['id'].split('_')[0]}: {c['detail']}." for c in failed) +
                " It is shown for transparency; nothing is trained or fitted on it.", "fail")
    name = st.selectbox("Protocol", list(mans), format_func=lambda k: LABEL.get(k, k))
    m = mans[name]
    st.markdown(f"**Verdict:** {ui.badge(m['verdict'])} &nbsp; **Status:** {ui.badge(m['status'].upper().replace('EVALUATED', 'INFO'))} {m['status'].replace('_', ' ')}", unsafe_allow_html=True)
    st.caption(m["description"])
    cr = m["case_ranges"]
    cols = st.columns(len(cr))
    for col, (s, r) in zip(cols, cr.items()):
        ui.card(col, s, f"{r['n_cases']} cases", f"cases {r['start_index']}-{r['end_index_exclusive'] - 1}")
    st.write("")
    a, b = st.columns([1, 1])
    with a:
        rows = [{"split": s, "class": c, "cases": n} for s, r in cr.items() for c, n in r["class_counts"].items()]
        fig = px.bar(pd.DataFrame(rows), x="split", y="cases", color="class", title="Class counts per split", text="cases", color_discrete_sequence=ui.CLASS_COLORS)
        st.plotly_chart(fig, width="stretch")
    with b:
        t = pd.DataFrame({s: r["class_counts"] for s, r in cr.items()})
        t["total"] = t.sum(axis=1)
        st.markdown("**Minority-class coverage**")
        st.dataframe(t, width="stretch")
        low = [(s, c, n) for s, r in cr.items() for c, n in r["class_counts"].items() if n < 3]
        st.markdown("Split-classes with fewer than 3 cases: " + (", ".join(f"{s}/{c}={n}" for s, c, n in low) if low else "none"))
    key = {"official_armor_v1": "official_split", "model1_candidate_100_26_84_v1": "candidate_split", "model1_alternative_v1": "alternative_split"}[name]
    st.subheader("Chronological timeline")
    d = df.copy()
    d["t"] = pd.to_datetime(d.timestamp, unit="s", utc=True)
    fig = px.scatter(d, x="t", y=[0] * len(d), color=key, color_discrete_map=ui.SPLIT_COLORS, hover_data=["case_index", "category", "failure_type", "group_id"], title="Cases coloured by split (hover for details)")
    for bd in m["sample_time_boundaries"]:
        x = pd.to_datetime(bd["boundary_ts"], unit="s", utc=True)
        fig.add_vline(x=x, line_dash="dash", line_color="#475569", annotation_text="sample boundary", annotation_position="top")
    fig.update_yaxes(visible=False)
    fig.update_layout(height=280)
    st.plotly_chart(fig, width="stretch")
    st.subheader("Leakage and quality checks")
    chk = pd.DataFrame(m["checks"])
    st.markdown("\n".join(f"- {ui.badge(r['status'])} **{r['id']}** ({r['severity']}) - {r['detail']}" for _, r in chk.iterrows()), unsafe_allow_html=True)
    st.caption(f"Sample partition (7,200 samples): {m['sample_partition']}. Incident groups: {m['incident_groups']}.")
    st.subheader("Try a train | validation boundary")
    scan = da.jload("splits", "boundary_scan.json")
    k = st.slider("Boundary index k (train = cases 0..k-1, validation = k..125)", 60, 125, 100)
    ts, gid = df.timestamp.tolist(), df.group_id.tolist()
    gap = ts[k] - ts[k - 1]
    safe = gap - REQUIRED_SPAN
    iso_ok = gid[k] != gid[k - 1]
    val = df.iloc[k:126].category.value_counts().reindex(CLASSES, fill_value=0)
    c1, c2, c3 = st.columns(3)
    ui.card(c1, "Case-to-case gap", f"{gap} s", f"needs > {REQUIRED_SPAN} s ({'OK' if safe > 0 else 'overlap'})")
    ui.card(c2, "Incident group isolation", "OK" if iso_ok else "CUT", "cases k-1 and k in different groups" if iso_ok else "one incident group spans the boundary")
    ui.card(c3, "Validation Node Memory", int(val["Node Memory"]), f"{126 - k} validation cases")
    st.markdown(ui.badge("PASS" if (safe > 0 and iso_ok) else "FAIL") + f" boundary at k = {k}; validation class counts: {val.to_dict()}", unsafe_allow_html=True)
    if scan:
        s = pd.DataFrame(scan["scan"])
        fig = px.bar(s, x="k", y="safe_gap_seconds", color="boundary_ok", color_discrete_map={True: "#10b981", False: "#dc2626"}, title="Safe gap at each candidate boundary (green = usable)")
        fig.add_vline(x=100, line_dash="dash", annotation_text="proposed 100")
        st.plotly_chart(fig, width="stretch")
    folds = da.jload("splits", "rolling_origin_folds_v1.json")
    if folds:
        st.subheader("Forward-chaining folds (proposed, pending approval)")
        rows = []
        for f in folds["folds"]:
            rows.append({"fold": f["fold"], "train cases": f["train"][1] - f["train"][0], "validation cases": f["validation"][1] - f["validation"][0],
                         **{f"val {c}": n for c, n in f["validation_class_counts"].items()}, **{f"train {c}": n for c, n in f["train_class_counts"].items()}})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.subheader("Official ARMOR versus Model 1 protocols")
    ad = m["ad_split"]
    first_ft = pd.to_datetime(ad["first_heldout_case_ts"], unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
    pre = ((da.jload("d1_inspection.json", base=da.M298_43) or {}).get("split_and_leakage", {}) or {}).get("pretraining_exposure", {})
    pre_txt = f"all {pre.get('train_samples_total', '?'):,} normal samples ({pre.get('train_samples_after_ad_split_ts', '?'):,} after the AD boundary)" if pre else "all normal samples (count unavailable)"
    st.markdown(f"""
| | Official ARMOR (reproduction) | Our Model 1 (proposed, not yet approved) |
|---|---|---|
| Case split | first 126 train / last 84 test, by `cases.csv` order | chronological; test = the same official last 84; train/validation boundary near case 100 |
| AD boundary | sample-based: 60% of samples = {ad['utc']} (start of a collection day) | validation/test sample boundary aligned to the same time |
| FT / RCL boundary | case-based: first held-out case {first_ft} | same test cases |
| Difference | the AD boundary is {ad['seconds_before_first_heldout_case']:,} s before the first held-out case; FT/RCL never use `ad_cases.pkl` | keeps both rules; reported separately |
| Pretraining | {pre_txt} | strict chronological primary; whole-pool as a separate sensitivity run |
| Labels | published `ad_cases.pkl` (98 post-split events) for AD | `cases.csv` authoritative; 21 AD-only events uncertain |
""")
