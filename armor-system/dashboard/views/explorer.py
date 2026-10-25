import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_access as da
import ui


def render():
    ui.hero("Dataset Explorer", "Schema, representative records, cases and timestamps of the actual D1 release")
    insp, sch = da.jload("inspection", "inspection_summary.json"), da.schema()
    if not insp or not sch:
        ui.missing("inspection artifacts")
        return
    tabs = st.tabs(["Schema", "Representative records", "Case explorer", "Timestamps and sampling", "Live sample inspector"])
    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        ui.card(c1, "Per-sample tensor", f"{sch['tensor_shape_per_sample'][0]} x {sch['tensor_shape_per_sample'][1]}", sch["dtype"])
        ui.card(c2, "Channel order sha256", sch["channel_order_sha256"][:10], "stable ordering fingerprint")
        ui.card(c3, "Node order sha256", sch["node_order_sha256"][:10], "stable ordering fingerprint")
        h = insp["numeric_health"]
        ui.card(c4, "NaN / Inf", f"{h['nan']} / {h['inf']}", f"max |v| {h['max_abs']:.3f} (bound sqrt(179) = {h['sqrt_179']:.3f})")
        st.write("")
        stats = da.cload("inspection", "channel_statistics_full_dataset.csv")
        ch = pd.DataFrame(sch["channel_order"])
        if stats is not None:
            ch = ch.merge(stats.drop(columns=["name", "modality"]), on="index")
        f1, f2 = st.columns([1, 2])
        mods = f1.multiselect("Modality", ["metric", "trace", "log"], default=["metric", "trace", "log"])
        q = f2.text_input("Search channel name", "")
        view = ch[ch["modality"].isin(mods)]
        if q:
            view = view[view["name"].str.contains(q, case=False)]
        st.caption(f"{len(view)} of {len(ch)} channels (full-dataset descriptive statistics)")
        st.dataframe(view, width="stretch", height=360, hide_index=True)
        masks = da.cload("preprocessing", "structural_masks.csv")
        nodes = pd.DataFrame({"position": range(len(sch["node_order"])), "node": sch["node_order"]})
        if masks is not None:
            m = masks[masks["fit_set"] == "official_train_period"].pivot(index="node", columns="modality", values="structurally_absent")
            nodes = nodes.merge(m.add_prefix("absent_").reset_index(), on="node")
        st.markdown("**Node order** (position = index in the tensor); `absent_*` = modality structurally absent for that node")
        st.dataframe(nodes, width="stretch", height=300, hide_index=True)
    with tabs[1]:
        reps = da.jload("inspection", "representative_records.json")
        if not reps:
            ui.missing("representative_records.json")
        else:
            pick = st.selectbox("Fault class", [r["category"] for r in reps])
            r = next(x for x in reps if x["category"] == pick)
            a, b = st.columns([1, 1])
            a.json({k: v for k, v in r.items() if k not in ("full_vector", "top_abs_channels")})
            top = pd.DataFrame(r["top_abs_channels"])
            fig = px.bar(top.iloc[::-1], x="value", y="channel", color="modality", orientation="h", color_discrete_map=ui.PALETTE, title=f"Largest |value| channels on {r['node']}")
            b.plotly_chart(fig, width="stretch")
            vec = np.array(r["full_vector"])
            owner = [c["modality"] for c in sch["channel_order"]]
            fig = go.Figure(go.Bar(x=list(range(len(vec))), y=vec, marker_color=[ui.PALETTE[o] for o in owner], hovertext=[c["name"] for c in sch["channel_order"]]))
            fig.update_layout(title="All 130 channel values of that node at the sample nearest the injection", xaxis_title="channel index", yaxis_title="value", height=320)
            st.plotly_chart(fig, width="stretch")
    with tabs[2]:
        df = da.cload("splits", "case_split_assignments.csv")
        if df is None:
            ui.missing("splits/case_split_assignments.csv")
        else:
            f = st.columns(4)
            cats = f[0].multiselect("Class", sorted(df["category"].unique()), default=sorted(df["category"].unique()))
            lv = f[1].multiselect("Level", sorted(df["level"].unique()), default=sorted(df["level"].unique()))
            sp = f[2].multiselect("Official split", ["train", "test"], default=["train", "test"])
            txt = f[3].text_input("cmdb_id contains", "")
            lo, hi = int(df.timestamp.min()), int(df.timestamp.max())
            rng = st.slider("Injection time range", lo, hi, (lo, hi), format="%d")
            v = df[df.category.isin(cats) & df.level.isin(lv) & df.official_split.isin(sp) & df.timestamp.between(*rng)]
            if txt:
                v = v[v.cmdb_id.str.contains(txt, case=False)]
            st.caption(f"{len(v)} of {len(df)} cases")
            fig = px.scatter(v, x=pd.to_datetime(v.timestamp, unit="s", utc=True), y="category", color="category", hover_data=["failure_type", "cmdb_id", "level", "official_split"], title="Cases over time")
            fig.update_layout(showlegend=False, xaxis_title="injection time (UTC)")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(v[["case_index", "utc", "category", "failure_type", "level", "cmdb_id", "group_id", "official_split"]], width="stretch", hide_index=True, height=320)
            ui.note("`cmdb_id` names a graph node exactly for 136 cases; for service-level cases it names a service without replica suffix. Fault end times are not part of the release.")
    with tabs[3]:
        s = insp["sampling"]
        c1, c2, c3 = st.columns(3)
        ui.card(c1, "First sample", s["first"], "UTC")
        ui.card(c2, "Last sample", s["last"], "UTC")
        ui.card(c3, "Nominal step", f"{s['nominal_step_seconds']} s", f"sorted: {s['is_sorted']}, unique: {s['unique']}")
        days = pd.DataFrame(s.get("collection_days", []))
        if len(days):
            fig = px.bar(days, x="start", y=["samples"], title="Contiguous collection days (5 runs of 1,440 one-minute samples)", text="samples")
            fig.update_layout(showlegend=False, xaxis_title="run start (UTC)")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(days, hide_index=True, width="stretch")
            st.caption(s.get("collection_day_note", ""))
        st.markdown("**Step sizes between consecutive samples (seconds: count)**")
        st.json(s["step_seconds_counts"])
        gt = insp["ground_truth"]
        st.markdown("**Ground truth available:** " + "; ".join(gt["available"]))
        st.markdown("**Not available:** " + "; ".join(gt["not_available"]))
        rec = insp.get("label_reconciliation")
        if rec:
            ui.note(f"`ad_cases.pkl` has {rec['ad_cases_pkl_count']} events versus {rec['cases_csv_count']} cases: {rec['exact_shared']} shared, {rec['ad_only']} AD-only, {rec['case_only']} case-only; "
                    f"all after the AD split {rec['ad_split_utc']}. Origin unexplained (it came from the ART release).", "warn")
    with tabs[4]:
        cache = None
        st.caption("Reads the Git-ignored feature cache (`armor-system/data/processed`). Loaded once on demand.")
        if st.button("Load feature cache") or st.session_state.get("cache_loaded"):
            st.session_state["cache_loaded"] = True
            cache = da.feature_cache()
        if cache is None:
            if st.session_state.get("cache_loaded"):
                ui.missing("data/processed/d1_features_v1.npz", "run `python armor-system/data/pipeline.py --stage cache`")
        else:
            ts, X, is_test = cache["ts"], cache["X"], cache["is_test"]
            idx = st.slider("Sample index (time order)", 0, len(ts) - 1, 4400)
            st.write(f"timestamp {int(ts[idx])} - {pd.to_datetime(int(ts[idx]), unit='s', utc=True)} - source file: {'test_samples' if is_test[idx] else 'train_samples'}")
            fig = px.imshow(X[idx], aspect="auto", color_continuous_scale="RdBu_r", zmin=-4, zmax=4, labels=dict(x="channel", y="node", color="value"), title="46 x 130 feature matrix (colour clipped to +/-4)")
            st.plotly_chart(fig, width="stretch")
            n_i = st.selectbox("Node", sch["node_order"], index=0)
            c_i = st.selectbox("Channel", [c["name"] for c in sch["channel_order"]], index=0)
            w = st.slider("Window (minutes before / after)", 5, 120, 30)
            lo, hi = max(0, idx - w), min(len(ts), idx + w + 1)
            y = X[lo:hi, sch["node_order"].index(n_i), [c["name"] for c in sch["channel_order"]].index(c_i)]
            fig = px.line(x=pd.to_datetime(ts[lo:hi], unit="s", utc=True), y=y, markers=True, title=f"{n_i} - {c_i}")
            fig.update_layout(xaxis_title="UTC", yaxis_title="value")
            st.plotly_chart(fig, width="stretch")
