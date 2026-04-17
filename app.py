# ── 1. IMPORTS & CONFIG ─────────────────────────────────────
import re
import streamlit as st
from agent import investigate
from memory import collection

st.set_page_config(page_title="OSINT Agent", page_icon="🎯", layout="wide")


# ── 2. STYLING ──────────────────────────────────────────────
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #00ff41;
    text-align: center;
    font-family: 'Courier New', monospace;
    margin-bottom: 0;
}
.sub-header {
    text-align: center;
    color: #888;
    font-family: 'Courier New', monospace;
    margin-bottom: 2rem;
}
.tool-call {
    background: #1e1e1e;
    color: #00ff41;
    padding: 8px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    margin: 4px 0;
}
</style>
""", unsafe_allow_html=True)


# ── 3. HEADER ───────────────────────────────────────────────
st.markdown('<div class="main-header">🎯 OSINT INTELLIGENCE AGENT</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">// autonomous open-source intelligence //</div>', unsafe_allow_html=True)


# ── 4. SIDEBAR: INVESTIGATION ARCHIVE ───────────────────────
with st.sidebar:
    st.header("📂 Investigation Archive")

    if st.button("🔄 Refresh Archive"):
        st.rerun()

    results = collection.get()
    if results["metadatas"]:
        subjects_data = sorted([
            {
                "id": doc_id,
                "subject": m.get("subject", "Unknown"),
                "date": m.get("timestamp", "Unknown")[:10],
                "query": m.get("query", ""),
            }
            for m, doc_id in zip(results["metadatas"], results["ids"])
        ], key=lambda x: x["date"], reverse=True)

        st.markdown(f"**{len(subjects_data)} investigations stored**")
        st.markdown("---")

        for entry in subjects_data:
            with st.expander(f"🎯 {entry['subject']}"):
                st.caption(f"📅 {entry['date']}")
                st.caption(f"🔍 {entry['query']}")
                if st.button("View full report", key=f"view_{entry['id']}"):
                    st.session_state["view_report_id"] = entry["id"]
    else:
        st.info("No investigations yet. Run your first query.")


# ── 5. MAIN QUERY INPUT ─────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("### 🔍 New Investigation")
    query = st.text_input(
        "Enter target",
        placeholder="e.g., Find information about Anthropic",
        label_visibility="collapsed",
    )
    investigate_btn = st.button("🚀 Launch Investigation", type="primary", use_container_width=True)

with col2:
    st.markdown("### 📊 Stats")
    st.metric("Total Investigations", collection.count() if collection else 0)


# ── 6. INVESTIGATION EXECUTION ──────────────────────────────
if investigate_btn and query:
    with st.spinner("🛰️ Agent investigating... (this may take 30-60 seconds)"):
        try:
            result = investigate(query)
            st.success("✅ Investigation complete")

            if result["saved_subject"]:
                st.info(f"📁 Saved to memory: **{result['saved_subject']}**")

            if result["tool_calls"]:
                with st.expander(f"🔧 Tool calls made ({len(result['tool_calls'])})"):
                    for i, tc in enumerate(result["tool_calls"], 1):
                        args_str = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
                        st.markdown(
                            f'<div class="tool-call">{i}. <b>{tc["name"]}</b>({args_str})</div>',
                            unsafe_allow_html=True,
                        )

            image_urls = re.findall(r'https://maps\.googleapis\.com/maps/api/staticmap[^\s\)]+', result["response"])
            if image_urls:
                st.markdown("### 🛰️ Satellite Intelligence")
                cols = st.columns(min(len(image_urls), 3))
                for i, url in enumerate(image_urls[:3]):
                    with cols[i]:
                        st.image(url, caption=f"Zoom level {i+1}", use_container_width=True)

            st.markdown("---")
            st.markdown(result["response"])

        except Exception as e:
            st.error(f"Investigation failed: {str(e)}")

elif investigate_btn and not query:
    st.warning("⚠️ Please enter a target to investigate.")


# ── 7. RETRIEVED REPORT VIEW ────────────────────────────────
if "view_report_id" in st.session_state:
    report_id = st.session_state["view_report_id"]
    results = collection.get(ids=[report_id])
    if results["documents"]:
        st.markdown("---")
        st.markdown("### 📄 Retrieved Report")
        metadata = results["metadatas"][0]
        st.caption(f"📅 {metadata.get('timestamp', '')[:10]} | 🔍 Query: *{metadata.get('query', '')}*")
        st.markdown(results["documents"][0])
        if st.button("Clear view"):
            del st.session_state["view_report_id"]
            st.rerun()
