import pandas as pd
import plotly.express as px
import streamlit as st

import data_access as da
import ui


def render():
    ui.hero("Data Quality", "Nine-stage validation adapted to D1, automated tests and deliberate-corruption demonstrations")
    q = da.jload("quality", "nine_stage_validation.json")
    if not q:
        ui.missing("quality/nine_stage_validation.json")
        return
    sm = q["summary"]
    c = st.columns(4)
    ui.card(c[0], "Stages passed", f"{sm['stages_passed']} / {sm['stages_total']}", "")
    ui.card(c[1], "Checks passed", f"{sm['checks_passed']} / {sm['checks_total']}", "")
    ui.card(c[2], "Corruption cases", f"{sm['corruptions_detected']} / {sm['corruption_tests']}", "behaved as expected")
    ev = da.jload("evidence", "evidence.json") or {}
    t = ev.get("tests")
    ui.card(c[3], "Unit tests", f"{t['total'] - t['failures'] - t['errors'] - t['skipped']} ok / {t['total']}" if t else "not recorded", f"{t['failures']} failures, {t['errors']} errors, {t['skipped']} skipped" if t else "")
    st.write("")
    df = pd.DataFrame([{"stage": f"{s['stage']}. {s['name']}", "PASS": sum(1 for x in s["checks"] if x["status"] == "PASS"),
                        "FAIL": sum(1 for x in s["checks"] if x["status"] != "PASS")} for s in q["stages"]])
    fig = px.bar(df, x="stage", y=["PASS", "FAIL"], barmode="stack", title="Check results per stage", color_discrete_map={"PASS": "#10b981", "FAIL": "#dc2626"})
    fig.update_layout(xaxis_title=None, yaxis_title="checks", legend_title=None)
    st.plotly_chart(fig, width="stretch")
    for s in q["stages"]:
        with st.expander(f"Stage {s['stage']} - {s['name']}  [{s['status']}]", expanded=(s["status"] != "PASS" or s["stage"] == 9)):
            st.markdown("\n".join(f"- {ui.badge(x['status'])} **{x['name']}** - {x['detail']}" for x in s["checks"]), unsafe_allow_html=True)
    st.subheader("Corruption demonstration")
    s9 = next(s for s in q["stages"] if s["stage"] == 9)
    st.dataframe(pd.DataFrame([{"corruption": x["name"], "result": x["status"], "evidence": x["detail"]} for x in s9["checks"]]), hide_index=True, width="stretch")
    ui.note("Each corruption is applied to an in-memory copy; the clean control must raise no alarm. The deliberately failing split (100/26/84) is detected by Stage 7, not hidden.")
    if t:
        st.subheader("Test run")
        st.caption(f"{t['command']} - recorded {t['ran_utc']} on {ev.get('git', {}).get('head', '?')[:10]}")
        st.dataframe(pd.DataFrame(t["suites"]), hide_index=True, width="stretch")
    st.subheader("Warnings and limitations")
    insp = da.jload("inspection", "inspection_summary.json") or {}
    rec = insp.get("label_reconciliation")
    items = []
    mans = da.split_manifests()
    cand = mans.get("model1_candidate_100_26_84_v1")
    if cand and not cand["usable"]:
        items.append(("FAIL", "The proposed 100 / 26 / 84 split fails incident isolation, boundary gap and boundary containment checks (cases 99 and 100 are 448 s apart and share an incident group)."))
    if cand and any(c_["status"] == "WARN" for c_ in cand["checks"]):
        items.append(("WARN", "Validation has a single Node Memory case: per-class validation metrics for that class are unstable."))
    if rec:
        items.append(("WARN", f"`ad_cases.pkl` ({rec['ad_cases_pkl_count']}) and `cases.csv` ({rec['cases_csv_count']}) differ by {rec['ad_only']} AD-only and {rec['case_only']} case-only events; the origin is unexplained."))
    items += [("WARN", "No incident end times or durations exist; sample-level labels cannot be derived without inventing a duration."),
              ("WARN", "ARMOR's feature scaling used the full timeline; a train-only second stage cannot remove that."),
              ("INFO", "Features are precomputed numeric aggregates, not raw telemetry.")]
    st.markdown("\n".join(f"- {ui.badge(k)} {v}" for k, v in items), unsafe_allow_html=True)
