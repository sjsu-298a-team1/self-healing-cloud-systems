import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_access as da
import ui

LABEL = {"model1_split_101_25_84_v1": "APPROVED Model 1 split (101 / 25 / 84)", "official_armor_v1": "Official ARMOR reproduction (126 / 84)",
         "model1_candidate_100_26_84_v1": "REJECTED candidate (100 / 26 / 84) - fails hard checks"}
CLASSES = ["Container Hardware", "Container Network", "Node CPU", "Node Disk", "Node Memory"]
REQUIRED_SPAN = 719


def render():
    ui.hero("Data Splitting", "Chronological, incident-group-aware splits - official ARMOR reproduction kept separate from the approved Model 1 split")
    mans = da.split_manifests()
    df = da.cload("splits", "case_split_assignments.csv")
    if not mans or df is None:
        ui.missing("split manifests")
        return
    st.markdown("**Three things are kept apart:** (1) the *Model 1 case split* - which injection cases train, validate and test; (2) the *sample-level anomaly-detection timeline* of the unchanged official ARMOR baseline "
                "(split at 60% of samples); (3) the *official ARMOR FT/RCL protocol* (first 126 / last 84 cases). Counting units are defined at the bottom of this page.")
    name = st.selectbox("Protocol", list(mans), format_func=lambda k: LABEL.get(k, k))
    m = mans[name]
    status_badge = {"approved": "PASS", "approved_reproduction": "PASS", "rejected_fails_hard_checks": "FAIL"}.get(m["status"], "PENDING")
    st.markdown(f"**Verdict:** {ui.badge(m['verdict'])} &nbsp; **Status:** {ui.badge(status_badge)} {m['status'].replace('_', ' ')}", unsafe_allow_html=True)
    st.caption(m["description"])
    if m["status"] == "approved":
        ui.note("<b>Approved by the project owner.</b> " + m["approval"]["decision"] + ". " + " ".join(m.get("statistical_limitations", [])[:1]), "warn")
        with st.expander("Scope: what this manifest is and is not"):
            for k_, v_ in m["scope"].items():
                st.markdown(f"- **{k_.replace('_', ' ')}** - {v_}")
            st.markdown("**Statistical limitations**\n" + "\n".join(f"- {x}" for x in m["statistical_limitations"]))
    elif m["status"] == "rejected_fails_hard_checks":
        failed = [c for c in m["checks"] if c["status"] == "FAIL"]
        ui.note("<b>REJECTED - this split fails its hard checks and is unusable.</b> " + " ".join(f"{c['id'].split('_')[0]}: {c['detail']}." for c in failed) + " Shown as evidence only; nothing is fitted on it.", "fail")
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
    key = {"official_armor_v1": "official_split", "model1_candidate_100_26_84_v1": "rejected_100_26_84_split", "model1_split_101_25_84_v1": "model1_split"}[name]
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
    st.subheader("Why 101? Try a train | validation boundary")
    scan = da.jload("splits", "boundary_scan.json")
    k = st.slider("Boundary index k (train = cases 0..k-1, validation = k..125)", 60, 125, 101)
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
        fig.add_vline(x=100, line_dash="dash", annotation_text="rejected 100")
        fig.add_vline(x=101, line_dash="solid", line_color="#2563eb", annotation_text="approved 101")
        st.plotly_chart(fig, width="stretch")
    folds = da.jload("splits", "rolling_origin_folds_v1.json")
    if folds:
        st.subheader("Forward-chaining folds (optional idea - NOT approved, not part of the protocol)")
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
| | Official ARMOR (reproduction) | Our Model 1 (approved 101 / 25 / 84) |
|---|---|---|
| Case split | first 126 train / last 84 test, by `cases.csv` order | chronological and incident-group-aware: 101 train / 25 validation / the same official last 84 test |
| AD boundary | sample-based: 60% of samples = {ad['utc']} (start of a collection day) | validation/test sample boundary aligned to the same time |
| FT / RCL boundary | case-based: first held-out case {first_ft} | same test cases |
| Difference | the AD boundary is {ad['seconds_before_first_heldout_case']:,} s before the first held-out case; FT/RCL never use `ad_cases.pkl` | both rules are kept; the validation/test sample boundary is aligned to the AD boundary |
| Pretraining | {pre_txt} | strict chronological (before the validation boundary) is primary; whole-pool pretraining is a separate sensitivity run |
| Labels | published `ad_cases.pkl` (98 post-split events) for AD | `cases.csv` authoritative; 21 AD-only events uncertain |
""")
    st.subheader("Counting units")
    cu = da.jload("preprocessing", "counting_units.json")
    sc_ = da.cload("preprocessing", "split_counts_by_unit.csv")
    if cu:
        st.markdown("\n".join(f"- **{k_}** - {v_}" for k_, v_ in cu.items()))
    if sc_ is not None:
        st.dataframe(sc_, hide_index=True, width="stretch")
        st.caption("Detection evaluation is reported as two separate populations after the AD boundary: official AD events (98) and injection cases (84); they are never averaged.")
