import pandas as pd
import plotly.express as px
import streamlit as st

import data_access as da
import ui

LINEAR = "https://linear.app/298a-team-1-self-healing-cloud/issue"


def render():
    ui.hero("Deliverables and Evidence", "What was actually generated, tested and submitted")
    ev = da.jload("evidence", "evidence.json")
    if not ev:
        ui.missing("evidence/evidence.json")
        return
    st.caption(f"Evidence generated {ev['generated_utc']} on branch `{ev['git']['branch']}` at `{ev['git']['head'][:10]}`" + (" (working tree had uncommitted changes)" if ev["git"].get("dirty") else ""))
    st.subheader("Links")
    rows = [{"item": p["title"], "kind": f"PR #{p['number']}", "state": p["state"], "review": p.get("reviewDecision") or "none", "url": p["url"]} for p in ev.get("prs", [])]
    rows += [{"item": l["title"], "kind": "Linear", "state": l.get("note", ""), "review": "", "url": l["url"]} for l in ev.get("linear", [])]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("url")})
    st.subheader("Tests executed")
    t = ev.get("tests")
    if t:
        c = st.columns(4)
        ui.card(c[0], "Run", t["total"], t["command"])
        ui.card(c[1], "Failures", t["failures"], "")
        ui.card(c[2], "Errors", t["errors"], "")
        ui.card(c[3], "Skipped", t["skipped"], "")
        st.dataframe(pd.DataFrame(t["suites"]), hide_index=True, width="stretch")
    else:
        ui.missing("a recorded test run")
    st.subheader("Generated artifacts")
    a = pd.DataFrame(ev["artifacts"])
    f = st.multiselect("Category", sorted(a.category.unique()), default=sorted(a.category.unique()))
    v = a[a.category.isin(f)]
    st.caption(f"{len(v)} files, {v.bytes.sum() / 1e6:.2f} MB (small, committed). Large caches stay in Git-ignored `armor-system/data/processed/`.")
    st.plotly_chart(px.bar(a.groupby("category").bytes.sum().reset_index(), x="category", y="bytes", title="Committed artifact size by category"), width="stretch")
    st.dataframe(v, hide_index=True, width="stretch", height=360)
    st.subheader("Documentation")
    for d in ev.get("docs", []):
        st.markdown(f"- `{d['path']}` - {d['purpose']}" + ("" if d["exists"] else " **(missing)**"))
    st.subheader("Outstanding limitations and next steps")
    for s, text in ev.get("limitations", []):
        st.markdown(f"- {ui.badge(s)} {text}", unsafe_allow_html=True)
