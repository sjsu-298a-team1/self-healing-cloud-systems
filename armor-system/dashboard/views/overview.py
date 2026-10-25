import pandas as pd
import plotly.express as px
import streamlit as st

import data_access as da
import ui


def work_items():
    """(item, status, detail) derived from artifacts that actually exist - nothing is marked done by assertion."""
    ev = da.jload("evidence", "evidence.json") or {}
    prs = {p["number"]: p for p in ev.get("prs", [])}
    q = da.jload("quality", "nine_stage_validation.json")
    mans = da.split_manifests()
    res = da.jload("preprocessing", "preprocessing_results.json")
    eda = da.jload("eda", "eda_findings.json")
    aug = da.jload("augmentation", "augmentation_assessment.json")
    insp = da.jload("inspection", "inspection_summary.json")
    tests = ev.get("tests")
    items = []
    v = da.jload("d1_validation.json", base=da.M298_43)
    items.append(("Acquisition, integrity and label decisions (298-43)", "PASS" if v else "UNKNOWN",
                  "evidence manifests present" + (f"; PR #34 is {prs[34]['state']} (review: {prs[34].get('reviewDecision') or 'none yet'})" if 34 in prs else "")))
    items.append(("Inspection evidence", "PASS" if insp else "PENDING", "inspection_summary.json, schema.json, representative records" if insp else "not generated"))
    off = mans.get("official_armor_v1")
    items.append(("Official ARMOR split (126 / 84) preserved", ("PASS" if off and off["usable"] else "FAIL") if off else "PENDING", f"manifest verdict {off['verdict']}" if off else "not generated"))
    cand = mans.get("model1_candidate_100_26_84_v1")
    if cand:
        failed = [c["id"].split("_")[0] for c in cand["checks"] if c["status"] == "FAIL"]
        items.append(("Proposed Model 1 split 100 / 26 / 84", "FAIL" if not cand["usable"] else cand["verdict"], f"failed hard checks: {', '.join(failed) or 'none'}"))
    alt = mans.get("model1_alternative_v1")
    if alt:
        items.append(("Recommended alternative split (needs your approval)", "PENDING", f"manifest verdict {alt['verdict']}; status {alt['status'].replace('_', ' ')}"))
    items.append(("CPU preprocessing (train-only scaler, indicators, windows)", "PASS" if res and not res["schema_issues"] else ("FAIL" if res else "PENDING"),
                  f"config sha256 {res['config_sha256'][:12]}..." if res else "not generated"))
    items.append(("Exploratory data analysis", "PASS" if eda else "PENDING", f"{len(eda['findings'])} computed findings" if eda else "not generated"))
    items.append(("Data augmentation assessment", "PASS" if aug else "PENDING", f"decision: {aug['decision'].replace('_', ' ')}" if aug else "not generated"))
    if q:
        sm = q["summary"]
        items.append(("Nine-stage data-quality validation", "PASS" if sm["stages_passed"] == sm["stages_total"] else "FAIL", f"{sm['stages_passed']}/{sm['stages_total']} stages, {sm['checks_passed']}/{sm['checks_total']} checks"))
    else:
        items.append(("Nine-stage data-quality validation", "PENDING", "not generated"))
    if tests:
        items.append(("Automated tests", "PASS" if tests["failures"] == 0 and tests["errors"] == 0 else "FAIL", f"{tests['total']} run, {tests['failures']} failures, {tests['errors']} errors, {tests['skipped']} skipped"))
    else:
        items.append(("Automated tests", "PENDING", "no recorded test run"))
    items.append(("Streamlit dashboard", "PASS", "this application"))
    mine = [p for n, p in prs.items() if n != 34]
    items.append(("Review and merge of PR #34", "PASS" if 34 in prs and prs[34]["state"] == "MERGED" else "PENDING", prs[34]["state"] if 34 in prs else "state unknown"))
    items.append(("Review and merge of this work (298-44)", "PASS" if mine and mine[0]["state"] == "MERGED" else "PENDING", f"PR #{mine[0]['number']} is {mine[0]['state']}" if mine else "PR not yet recorded"))
    items.append(("Model 1 training, ARMOR baseline run, Airflow", "UNKNOWN", "out of scope for data preparation - not started"))
    return items


def render():
    ui.hero("ARMOR D1 - Data Preparation Dashboard", "AI-Driven Incident Response and Self-Healing Cloud Systems - DATA 298A Team 1 - every number below is read from generated artifacts")
    insp = da.jload("inspection", "inspection_summary.json")
    if not insp:
        ui.missing("inspection/inspection_summary.json")
        return
    c = insp["counts"]
    cols = st.columns(5)
    ui.card(cols[0], "Failure cases", ui.fmt_int(c["cases"]), f"{insp['classes']['n_categories']} classes, {insp['classes']['n_fine_types']} fine types")
    ui.card(cols[1], "Samples", ui.fmt_int(c["samples"]), f"{ui.fmt_int(c['train_file_samples'])} normal / {ui.fmt_int(c['test_file_samples'])} incident slices")
    ui.card(cols[2], "Nodes", c["nodes"], "services and machines")
    ui.card(cols[3], "Feature channels", c["channels"], "per node and minute")
    ui.card(cols[4], "Tensor size", f"{insp['size']['tensor_bytes_float32'] / 1e6:.0f} MB", f"{insp['dtype']}, {ui.fmt_int(insp['size']['values'])} values")
    st.write("")
    left, right = st.columns([1, 1])
    with left:
        mc = insp["modality_channel_counts"]
        fig = px.pie(names=list(mc), values=list(mc.values()), hole=0.55, color=list(mc), color_discrete_map=ui.PALETTE, title="Feature channels by modality")
        fig.update_traces(textinfo="label+value")
        st.plotly_chart(fig, width="stretch")
    with right:
        cc = insp["classes"]["category_counts"]
        df = pd.DataFrame({"class": list(cc), "cases": list(cc.values())}).sort_values("cases")
        fig = px.bar(df, x="cases", y="class", orientation="h", title="Fault classes (210 cases)", text="cases")
        fig.update_traces(marker_color=ui.CLASS_COLORS[0])
        st.plotly_chart(fig, width="stretch")
    st.subheader("Source and provenance")
    prov, ck = da.jload("provenance.json", base=da.M298_43), da.jload("checksums.json", base=da.M298_43)
    if prov and ck:
        a = ck["official_archive"]
        d1 = next((m for m in ck["fetched_members"] if m["member"].endswith("data/D1.zip")), {})
        st.markdown(f"""
| | |
|---|---|
| Source | Zenodo record [{a['record_id']}](https://zenodo.org/records/{a['record_id']}) ({a['license']}, published {a['publication_date']}); derived from the public ART repository |
| Acquired | only `ARMOR/data/D1.zip` by range request ({ui.fmt_int(ck['bytes_fetched_from_archive'])} bytes of {ui.fmt_int(a['file_size'])}); D2 and checkpoints not downloaded |
| D1.zip | {ui.fmt_int(d1.get('size', 0))} B, sha256 `{d1.get('sha256', '?')[:24]}...` |
| Integrity | member CRC32/size match the official archive directory; whole-archive md5 not recomputed (would need D2 bytes) |
| Ground truth | injection time, level, root-cause instance, fault type per case; **no end times or durations** |
""")
    else:
        ui.missing("298-43 provenance/checksums manifests (PR #34)")
    st.subheader("Work completed versus pending")
    rows = work_items()
    st.markdown("\n".join(f"- {ui.badge(s)} **{n}** - {d}" for n, s, d in rows), unsafe_allow_html=True)
    ui.note("Status badges are derived from the artifacts and recorded test/PR evidence. Anything not generated shows as PENDING, never as complete.")
