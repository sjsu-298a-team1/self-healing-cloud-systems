import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_access as da
import ui

MODS = ["metric", "trace", "log"]


def render():
    ui.hero("Exploratory Data Analysis", "Training-partition statistics drive modelling decisions; full-dataset views are labelled descriptive")
    findings = da.jload("eda", "eda_findings.json")
    if not findings:
        ui.missing("eda/eda_findings.json")
        return
    tabs = st.tabs(["Findings", "Class distribution", "Feature distributions", "Missingness", "Correlation", "Time series", "Incident-aligned", "Variability / outliers", "Train vs validation", "Static figures"])
    with tabs[0]:
        for f in findings["findings"]:
            st.markdown(f"**{f['id']}** - {f['finding']}")
            if f["evidence"]:
                with st.expander("calculation evidence"):
                    st.json(f["evidence"])
    with tabs[1]:
        sd = da.cload("eda", "split_class_distributions.csv")
        fd = da.cload("eda", "fault_distribution.csv")
        if sd is None or fd is None:
            ui.missing("class distribution tables")
        else:
            lvl = st.radio("Granularity", ["category", "fine_type"], horizontal=True)
            v = fd[fd["level"] == lvl].sort_values("count")
            st.plotly_chart(px.bar(v, x="count", y="name", orientation="h", text="count", title=f"Fault {lvl.replace('_', ' ')} distribution (all 210 cases, descriptive)"), width="stretch")
            mans = st.multiselect("Protocols", sorted(sd["manifest"].unique()), default=sorted(sd["manifest"].unique()))
            classes = st.multiselect("Classes", sorted(sd["class"].unique()), default=sorted(sd["class"].unique()))
            w = sd[sd.manifest.isin(mans) & sd["class"].isin(classes)]
            fig = px.bar(w, x="class", y="cases", color="split", facet_col="manifest", barmode="stack", color_discrete_map=ui.SPLIT_COLORS, title="Per-split class counts")
            st.plotly_chart(fig, width="stretch")
    with tabs[2]:
        h = da.jload("eda", "feature_histograms_train.json")
        d = da.cload("eda", "descriptive_stats_by_modality_full.csv")
        if not h:
            ui.missing("feature_histograms_train.json")
        else:
            sel = st.multiselect("Modalities", MODS, default=MODS)
            cols = st.columns(len(sel) or 1)
            for col, m in zip(cols, sel):
                ed = np.array(h[m]["bin_edges"])
                fig = go.Figure(go.Bar(x=(ed[:-1] + ed[1:]) / 2, y=h[m]["counts"], marker_color=ui.PALETTE[m]))
                z = h[m]["zero_count"] / (h[m]["zero_count"] + h[m]["nonzero_count"])
                fig.update_layout(title=f"{m}: non-zero values, train (zeros {z:.0%})", yaxis_type="log", height=320)
                col.plotly_chart(fig, width="stretch")
            q = pd.DataFrame({m: h[m]["quantiles"] for m in sel}).T
            st.markdown("**Quantiles of live entries (train)**")
            st.dataframe(q, width="stretch")
        if d is not None:
            st.markdown("**Descriptive statistics by modality (full dataset - descriptive only)**")
            st.dataframe(d, hide_index=True, width="stretch")
    with tabs[3]:
        mr = da.cload("eda", "missingness_node_modality_train.csv")
        zc = da.cload("eda", "zero_fraction_by_channel_train.csv")
        if mr is None:
            ui.missing("missingness tables")
        else:
            piv = mr.pivot(index="node", columns="modality", values="zero_fraction_train")[MODS]
            st.plotly_chart(px.imshow(piv, aspect="auto", color_continuous_scale="Viridis", zmin=0, zmax=1, title="Zero fraction per node and modality (train) - 1.0 with absent=1 means structurally absent", height=820), width="stretch")
            ab = mr[mr.structurally_absent == 1]
            st.markdown(f"**Structurally absent node-modality blocks (zero in every training sample):** {len(ab)} - " + ", ".join(f"{r.node}/{r.modality}" for r in ab.itertuples()))
            part = mr[(mr.structurally_absent == 0) & (mr.all_zero_row_fraction_train > 0)]
            st.markdown(f"**Blocks with some all-zero minutes but not structurally absent (possible dropout, unverified):** {len(part)}")
            st.dataframe(part, hide_index=True, width="stretch")
        if zc is not None:
            mods = st.multiselect("Channel modality", MODS, default=MODS, key="zc")
            st.plotly_chart(px.bar(zc[zc.modality.isin(mods)], x="index", y="zero_fraction_live_train", color="modality", color_discrete_map=ui.PALETTE, hover_name="name", title="Zero fraction by channel over live entries (train)"), width="stretch")
    with tabs[4]:
        cm = da.cload("eda", "correlation_channels_train.csv")
        pairs = da.cload("eda", "highly_correlated_pairs_train.csv")
        sch = da.schema()
        if cm is None or not sch:
            ui.missing("correlation matrix")
        else:
            owner = {c["name"]: c["modality"] for c in sch["channel_order"]}
            mods = st.multiselect("Modalities in heatmap", MODS, default=MODS, key="cm")
            names = [n for n in cm["channel"] if owner[n] in mods]
            M = cm.set_index("channel").loc[names, names]
            st.plotly_chart(px.imshow(M, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto", height=640, title="System-level channel correlation (train; blank = constant channel)"), width="stretch")
            if pairs is not None and len(pairs) and str(pairs.iloc[0]["channel_a"]) != "nan":
                st.markdown("**Channel pairs with |r| >= 0.95**")
                st.dataframe(pairs, hide_index=True, width="stretch")
    with tabs[5]:
        tt = da.cload("eda", "temporal_trends_full_10min.csv")
        if tt is None:
            ui.missing("temporal_trends_full_10min.csv")
        else:
            mods = st.multiselect("Modalities", MODS, default=MODS, key="tt")
            tt = tt.copy()
            tt["t"] = pd.to_datetime(tt.timestamp, unit="s", utc=True)
            fig = go.Figure()
            for m in mods:
                fig.add_trace(go.Scatter(x=tt.t, y=tt[f"{m}_mean_abs"], mode="lines", name=m, line=dict(color=ui.PALETTE[m], width=1.2)))
            fig.update_layout(title="System-level mean |value| (10-minute means, full timeline, descriptive)", xaxis_title="UTC", yaxis_title="mean |value|")
            st.plotly_chart(fig, width="stretch")
            st.caption("Gaps between the five contiguous collection days are not interpolated.")
    with tabs[6]:
        ia = da.cload("eda", "incident_aligned.csv")
        if ia is None:
            ui.missing("incident_aligned.csv")
        else:
            c = st.columns(3)
            cats = c[0].multiselect("Class", sorted(ia.category.unique()), default=sorted(ia.category.unique()))
            m = c[1].radio("Modality", MODS, horizontal=True)
            part = c[2].radio("Cases", ["train_cases", "heldout_cases"], horizontal=True, help="train_cases = official first 126 (model-development); heldout_cases are descriptive only")
            v = ia[ia.category.isin(cats) & (ia.modality == m) & (ia.partition == part)].copy()
            v["ratio"] = v.root_mean_abs / v.other_mean_abs.clip(lower=1e-9)
            fig = px.line(v, x="offset_min", y="ratio", color="category", markers=True, title=f"{m}: mean |value| on the root-cause node / on other nodes", hover_data=["n_cases", "root_mean_abs", "other_mean_abs"])
            fig.add_vline(x=0, line_dash="dash", annotation_text="injection")
            st.plotly_chart(fig, width="stretch")
            cov = da.jload("eda", "incident_aligned_coverage.json")
            if cov:
                st.caption(f"{cov['n_cases_aligned']} cases aligned; the available window is limited by the 15-sample incident slices (minutes with data: {min(map(int, cov['cases_with_sample_at_offset']))} to {max(map(int, cov['cases_with_sample_at_offset']))}).")
    with tabs[7]:
        vr = da.cload("eda", "variability_outliers_train.csv")
        if vr is None:
            ui.missing("variability_outliers_train.csv")
        else:
            n = st.slider("Top N channels", 5, 40, 20)
            mods = st.multiselect("Modalities", MODS, default=MODS, key="vo")
            v = vr[(vr.modality.isin(mods)) & (~vr.constant.astype(bool))].sort_values("fraction_abs_gt_3", ascending=False).head(n)
            st.plotly_chart(px.bar(v.iloc[::-1], x="fraction_abs_gt_3", y="name", color="modality", orientation="h", color_discrete_map=ui.PALETTE, title="Share of values beyond |3| (train)", height=100 + 22 * n), width="stretch")
            st.dataframe(vr, hide_index=True, width="stretch", height=300)
    with tabs[8]:
        kv = da.cload("eda", "train_vs_validation_alt_split.csv")
        if kv is None:
            ui.missing("train_vs_validation_alt_split.csv")
        else:
            ui.note("Exploratory comparison on the recommended alternative split, which is pending your approval. KS on pooled entries is sensitive to the large zero mass.", "warn")
            mods = st.multiselect("Modalities", MODS, default=MODS, key="kv")
            thr = st.slider("Flag threshold (KS)", 0.05, 0.5, float(findings.get("ks_flag_threshold", 0.2)))
            v = kv[kv.modality.isin(mods)]
            fig = px.bar(v, x="index", y="ks", color="modality", color_discrete_map=ui.PALETTE, hover_name="name", title="Two-sample KS statistic per channel (train vs validation)")
            fig.add_hline(y=thr, line_dash="dash", line_color="#dc2626")
            st.plotly_chart(fig, width="stretch")
            fl = v[v.ks >= thr]
            st.markdown(f"**{len(fl)} channels at or above {thr:.2f}**")
            st.dataframe(v.sort_values("ks", ascending=False).head(15), hide_index=True, width="stretch")
    with tabs[9]:
        figs = sorted(f for f in (da.art_path("eda", "figures"),) if True)
        import os
        names = sorted(os.listdir(figs[0])) if os.path.isdir(figs[0]) else []
        if not names:
            ui.missing("static figures")
        for n in names:
            st.image(os.path.join(figs[0], n), caption=n, width="stretch")
