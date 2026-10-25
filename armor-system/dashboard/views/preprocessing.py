import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_access as da
import ui

MODS = ["metric", "trace", "log"]


def render():
    ui.hero("Preprocessing", "CPU-only, train-only fitted transformations - a zero is not a missing value")
    status_map = {"approved": "PASS", "approved_reproduction": "PASS"}
    res = da.jload("preprocessing", "preprocessing_results.json")
    cfg = da.jload("preprocessing", "preprocessing_config_v1.json")
    if not res or not cfg:
        ui.missing("preprocessing results/config")
        return
    c = st.columns(4)
    ui.card(c[0], "Schema issues", len(res["schema_issues"]), "validate_schema + order check")
    ui.card(c[1], "NaN / Inf", f"{res['missing_inspection']['nan']} / {res['missing_inspection']['inf']}", "whole dataset")
    ui.card(c[2], "Fit sets", len(res["fits"]), "each fit only on its own training period")
    ui.card(c[3], "Config sha256", cfg["config_sha256"][:10], "reproducibility fingerprint")
    st.write("")
    ui.note("ARMOR's features arrive pre-scaled by an undocumented recipe that used the whole timeline, so a train-only second stage cannot undo that. Official ARMOR preprocessing is not changed.", "warn")
    tabs = st.tabs(["Configuration", "Raw to prepared example", "Scaling statistics", "Structural masks and indicators", "Before / after", "Windowing and counts", "Validation evidence"])
    with tabs[0]:
        st.json(cfg)
    with tabs[1]:
        ex = da.jload("preprocessing", "prepared_example.json")
        if not ex:
            ui.missing("preprocessing/prepared_example.json")
        else:
            st.markdown(f"One approved **training** case: `{ex['category']}` - {ex['failure_type']} on `{ex['node']}`; window {ex['window_first_utc']} to {ex['window_last_utc']} (7 consecutive one-minute samples: 6 inputs + the next step).")
            names = [c["name"] for c in ex["channels_shown"]]
            rows = []
            for stg in ex["stages"]:
                if "node_excerpt" in stg:
                    for t, vals in enumerate(stg["node_excerpt"]):
                        rows.append({"stage": stg["stage"], "minute": t - 3, **{n: v for n, v in zip(names, vals)}})
            df = pd.DataFrame(rows)
            for stg in ex["stages"]:
                st.markdown(f"**{stg['stage'].capitalize()}** - {stg['what']}" + (f" - shape {stg['shape']}" if "shape" in stg else ""))
                if stg["stage"] == "validated":
                    st.markdown(f"Issues found: **{len(stg['issues'])}** {stg['issues'] or ''}")
                elif stg["stage"] == "prepared":
                    st.json({"arrays": stg["arrays"], "dtype": stg["dtype"], "timestamps": stg["timestamps"], "structurally_absent_trace_nodes": stg["structural_absent_nodes_trace"], "structurally_absent_log_nodes": stg["structural_absent_nodes_log"]})
                else:
                    st.dataframe(df[df.stage == stg["stage"]].drop(columns="stage"), hide_index=True, width="stretch")
            long = df.melt(id_vars=["stage", "minute"], var_name="channel", value_name="value")
            st.plotly_chart(px.line(long, x="minute", y="value", color="stage", facet_col="channel", facet_col_wrap=3, markers=True, title="Same channels before and after the Model 1 train-only transform (minute 0 = nearest sample to injection)"), width="stretch")
    with tabs[2]:
        fit = st.selectbox("Fit set", list(res["fits"]), key="pp_fit")
        r = res["fits"][fit]
        st.markdown(f"{ui.badge(status_map.get(r['status'], 'PENDING'))} <b>{r['status'].replace('_', ' ')}</b> - {r['definition']}", unsafe_allow_html=True)
        st.write(f"{r['n_fit_samples']:,} fit samples, {r['fit_first']} to {r['fit_last']}; {r['constant_entries_scale_set_to_1']:,} node-channel entries are constant in the fit set (scale set to 1).")
        z = da.nload("preprocessing", r["scaler_file"])
        if z is None:
            ui.missing(r["scaler_file"])
        else:
            live = ~z["absent_entry"] & ~z["constant"]
            fig = px.histogram(x=z["scale"][live], nbins=60, title="Fitted per node-channel scale (std) over live non-constant entries", labels={"x": "scale"})
            st.plotly_chart(fig, width="stretch")
            node_view = pd.DataFrame({"node_index": range(z["mean"].shape[0]), "live_non_constant_channels": live.sum(axis=1), "absent_entries": z["absent_entry"].sum(axis=1), "constant_entries": z["constant"].sum(axis=1)})
            st.dataframe(node_view, hide_index=True, width="stretch", height=300)
    with tabs[3]:
        fit2 = st.selectbox("Fit set", list(res["fits"]), key="pp_fit2")
        m = da.cload("preprocessing", "structural_masks.csv")
        if m is None:
            ui.missing("structural_masks.csv")
        else:
            v = m[m.fit_set == fit2].pivot(index="node", columns="modality", values="structurally_absent")[MODS]
            st.plotly_chart(px.imshow(v, aspect="auto", color_continuous_scale=[[0, "#e2e8f0"], [1, "#dc2626"]], title="Structurally absent node-modality blocks (red) - zero in every fit sample", height=800), width="stretch")
        r = res["fits"][fit2]
        st.markdown(f"Absent blocks per modality: {r['structural_absent_blocks']}. Node-modality rows that are all zero in a minute but not structural (kept as an unverified 'possible dropout' indicator, not asserted missing): **{r['observed_all_zero_not_structural_node_modality_rows']:,}**.")
        st.markdown("Indicators emitted by `preprocess.transform`: `structural_absent` (46 x 3, fixed) and `observed_all_zero_not_structural` (N x 46 x 3).")
    with tabs[4]:
        ba = da.cload("preprocessing", "before_after_summary.csv")
        if ba is None:
            ui.missing("before_after_summary.csv")
        else:
            f3 = st.selectbox("Fit set", sorted(ba.fit_set.unique()), key="pp_fit3")
            v = ba[ba.fit_set == f3]
            met = st.radio("Statistic", ["mean", "std", "p01", "p99", "zero_fraction"], horizontal=True)
            fig = px.bar(v, x="modality", y=met, color="stage", barmode="group", facet_col="period", title=f"{met} before vs after the transform, by modality and period")
            st.plotly_chart(fig, width="stretch")
            st.caption("After the transform the fit period is centred (mean ~0, std ~1 on non-constant entries); the later period is not, which shows held-out data did not influence the parameters.")
            st.dataframe(v, hide_index=True, width="stretch")
        st.markdown("**Live before / after for one series**")
        sch = da.schema()
        if st.button("Load feature cache for the live view") or st.session_state.get("cache_loaded"):
            st.session_state["cache_loaded"] = True
            cache = da.feature_cache()
            z = da.nload("preprocessing", res["fits"][st.session_state.get("pp_fit3", list(res["fits"])[0])]["scaler_file"]) if sch else None
            if cache is None or z is None:
                ui.missing("feature cache or scaler")
            else:
                n = st.selectbox("Node", sch["node_order"], key="pp_node")
                ch = st.selectbox("Channel", [x["name"] for x in sch["channel_order"]], index=1, key="pp_ch")
                i, j = sch["node_order"].index(n), [x["name"] for x in sch["channel_order"]].index(ch)
                raw = cache["X"][:, i, j]
                out = np.zeros_like(raw) if z["absent_entry"][i, j] else (raw - z["mean"][i, j]) / z["scale"][i, j]
                t = pd.to_datetime(cache["ts"], unit="s", utc=True)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=t, y=raw, mode="lines", name="before", line=dict(width=1)))
                fig.add_trace(go.Scatter(x=t, y=out, mode="lines", name="after", line=dict(width=1)))
                fig.update_layout(title=f"{n} - {ch}" + (" (structurally absent: forced to 0)" if z["absent_entry"][i, j] else (" (constant in fit set: scale 1)" if z["constant"][i, j] else "")))
                st.plotly_chart(fig, width="stretch")
    with tabs[5]:
        wc = da.cload("preprocessing", "window_counts.csv")
        w = cfg["windowing"]
        st.markdown(f"Window **{w['window']}** input steps + **{w['horizon']}** target step at **{w['step_seconds']} s** (ARMOR's series length 7). Windows never bridge a gap and are dropped if they cross a split boundary.")
        if wc is None:
            ui.missing("window_counts.csv")
        else:
            st.dataframe(wc, hide_index=True, width="stretch")
            st.plotly_chart(px.bar(wc, x="split", y=["kept_inside_period", "dropped_crossing_boundary"], facet_col="manifest", title="Windows per split"), width="stretch")
            st.caption("Counted on the contiguous 7,200-sample timeline; ARMOR itself windows its train and test files separately (see the 298-43 report).")
    with tabs[6]:
        q = da.jload("quality", "nine_stage_validation.json")
        if not q:
            ui.missing("quality/nine_stage_validation.json")
        else:
            for s in q["stages"]:
                if s["stage"] in (2, 6, 7, 8):
                    st.markdown(f"{ui.badge(s['status'])} **Stage {s['stage']} - {s['name']}**", unsafe_allow_html=True)
                    for ch_ in s["checks"]:
                        st.markdown(f"- {ui.badge(ch_['status'])} {ch_['name']} - {ch_['detail']}", unsafe_allow_html=True)
