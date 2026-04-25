from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from clienthunter.auditor import WebsiteAuditor
from clienthunter.database import (
    VALID_LEAD_STATUSES,
    all_leads,
    delete_lead,
    init_db,
    save_lead,
    save_prospect,
    update_lead_status,
)
from clienthunter.discovery import LeadDiscovery, build_manual_search_links
from clienthunter.outreach import build_outreach

st.set_page_config(
    page_title="Wireless Bot Prospector",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.main .block-container { padding-top: 2rem; padding-bottom: 3rem; }
.hero {
    padding: 1.45rem 1.6rem;
    border-radius: 1.3rem;
    background: linear-gradient(135deg, #020617 0%, #0f172a 55%, #1e293b 100%);
    color: white;
    margin-bottom: 1.2rem;
}
.hero h1 { margin: 0; font-size: 2rem; letter-spacing: -0.03em; }
.hero p { margin: .55rem 0 0 0; color: #dbeafe; max-width: 920px; }
.loader-card {
    position: relative;
    overflow: hidden;
    padding: 1.25rem;
    border-radius: 1.35rem;
    background: radial-gradient(circle at top left, rgba(34,197,94,.18), transparent 30%),
                linear-gradient(135deg, #020617 0%, #0f172a 45%, #1e293b 100%);
    color: #fff;
    margin: 1rem 0;
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow: 0 18px 45px rgba(2, 6, 23, 0.28);
}
.loader-card::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,.08) 45%, transparent 70%);
    transform: translateX(-100%);
    animation: shimmerMove 2.8s infinite;
    pointer-events: none;
}
.loader-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: 108px 1fr;
    gap: 1rem;
    align-items: center;
}
.radar {
    width: 96px;
    height: 96px;
    border-radius: 999px;
    position: relative;
    margin: 0 auto;
    background: radial-gradient(circle at center, rgba(134,239,172,.30) 0 7%, transparent 8% 100%),
                radial-gradient(circle, rgba(255,255,255,.12) 1px, transparent 1px);
    border: 1px solid rgba(255,255,255,.16);
    overflow: hidden;
    box-shadow: inset 0 0 25px rgba(34,197,94,.12), 0 0 22px rgba(34,197,94,.10);
}
.radar-ring, .radar-ring::before, .radar-ring::after {
    content: "";
    position: absolute;
    inset: 12%;
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 999px;
}
.radar-ring::before { inset: 22%; }
.radar-ring::after { inset: 34%; }
.radar-sweep {
    position: absolute;
    inset: -12%;
    background: conic-gradient(from 0deg, rgba(34,197,94,0) 0deg, rgba(34,197,94,0) 275deg, rgba(74,222,128,.18) 318deg, rgba(134,239,172,.75) 348deg, rgba(34,197,94,0) 360deg);
    border-radius: 999px;
    animation: radarSpin 2.2s linear infinite;
}
.radar-dot {
    position: absolute;
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: #86efac;
    box-shadow: 0 0 0 0 rgba(134,239,172,.75);
    animation: dotPulse 1.8s infinite;
}
.dot-1 { top: 22px; left: 59px; }
.dot-2 { top: 57px; left: 27px; animation-delay: .45s; }
.dot-3 { top: 62px; left: 66px; animation-delay: .9s; }
.mission-chip {
    display: inline-flex;
    margin-bottom: .55rem;
    padding: .18rem .55rem;
    border-radius: 999px;
    background: rgba(59,130,246,.18);
    color: #bfdbfe;
    font-size: .75rem;
    font-weight: 700;
    text-transform: uppercase;
}
.loader-card h4 { margin: 0 0 .4rem 0; font-size: 1.05rem; color: white; }
.loader-card p { margin: 0; color: #dbeafe; font-size: .94rem; line-height: 1.55; }
.loader-dots { display: flex; gap: .42rem; margin-top: .8rem; align-items: center; }
.loader-dots span {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: #93c5fd;
    animation: bounceDots 1.2s infinite ease-in-out;
}
.loader-dots span:nth-child(2) { animation-delay: .15s; }
.loader-dots span:nth-child(3) { animation-delay: .3s; }
.status-pill {
    display: inline-block;
    padding: .18rem .6rem;
    border-radius: 999px;
    background: #e2e8f0;
    color: #0f172a;
    font-size: .78rem;
    font-weight: 700;
}
@keyframes radarSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes dotPulse {
    0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(134,239,172,.75); }
    70% { transform: scale(1.12); box-shadow: 0 0 0 13px rgba(134,239,172,0); }
    100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(134,239,172,0); }
}
@keyframes bounceDots {
    0%, 80%, 100% { transform: translateY(0); opacity: .55; }
    40% { transform: translateY(-6px); opacity: 1; }
}
@keyframes shimmerMove {
    0% { transform: translateX(-110%); }
    70%, 100% { transform: translateX(120%); }
}
@media (max-width: 768px) {
    .loader-grid { grid-template-columns: 1fr; text-align: center; }
    .loader-dots { justify-content: center; }
}
</style>
"""

DISCOVERY_STAGES = [
    ("📡 Raising antenna and scanning local signals.", "Looking for businesses with or without websites."),
    ("🧭 Checking maps, directories, and search trails.", "Phone numbers, emails, addresses, and websites all count."),
    ("🕵️ Filtering weak matches and suspicious links.", "The mission is useful prospects, not empty tables."),
    ("💼 Packaging prospects into your pipeline.", "Businesses without websites may be your hottest leads."),
]

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=10)
def load_leads() -> list[dict[str, Any]]:
    init_db()
    return [dict(row) for row in all_leads()]


def refresh() -> None:
    load_leads.clear()
    st.rerun()


def loader_html(title: str, subtitle: str) -> str:
    return f"""
    <div class="loader-card">
        <div class="loader-grid">
            <div class="radar">
                <div class="radar-ring"></div>
                <div class="radar-sweep"></div>
                <div class="radar-dot dot-1"></div>
                <div class="radar-dot dot-2"></div>
                <div class="radar-dot dot-3"></div>
            </div>
            <div>
                <div class="mission-chip">Wireless Mission Active</div>
                <h4>Wireless Bot is scouting prospects...</h4>
                <p>{title}</p>
                <p>{subtitle}</p>
                <div class="loader-dots"><span></span><span></span><span></span></div>
            </div>
        </div>
    </div>
    """


def render_header() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>📡 Wireless Bot Prospector</h1>
            <p>Find business prospects with or without websites, save contacts, track follow-up, and generate outreach for client acquisition.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def leads_dataframe(leads: list[dict[str, Any]]) -> pd.DataFrame:
    if not leads:
        return pd.DataFrame()
    df = pd.DataFrame(leads)
    preferred = [
        "id", "business_name", "prospect_type", "website", "phone", "contact_email",
        "industry", "location", "address", "status", "opportunity_score", "source", "notes", "created_at"
    ]
    cols = [col for col in preferred if col in df.columns]
    return df[cols + [col for col in df.columns if col not in cols]]


def filter_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    with st.sidebar:
        st.subheader("Filters")
        status = st.selectbox("Status", ["all", *VALID_LEAD_STATUSES], key="status_filter")
        prospect_type = st.selectbox("Prospect type", ["all", "business", "website"], key="type_filter")
        min_score = st.slider("Minimum score", 0, 100, 0, key="score_filter")
        q = st.text_input("Search", key="search_filter")
    out = df.copy()
    if status != "all" and "status" in out:
        out = out[out["status"].fillna("new") == status]
    if prospect_type != "all" and "prospect_type" in out:
        out = out[out["prospect_type"].fillna("business") == prospect_type]
    if "opportunity_score" in out:
        out = out[out["opportunity_score"].fillna(0).astype(int) >= min_score]
    if q.strip():
        text = q.strip().lower()
        searchable = [c for c in ["business_name", "website", "phone", "contact_email", "industry", "location", "address", "source"] if c in out.columns]
        mask = pd.Series(False, index=out.index)
        for col in searchable:
            mask = mask | out[col].fillna("").astype(str).str.lower().str.contains(text, regex=False)
        out = out[mask]
    return out


def candidate_columns(df: pd.DataFrame) -> list[str]:
    wanted = ["business_name", "confidence", "website", "phone", "email", "address", "industry", "location", "source", "search_query", "snippet"]
    return [col for col in wanted if col in df.columns]


def render_discovery() -> None:
    st.subheader("Discover Business Prospects")
    st.caption("This now returns businesses with websites, businesses without websites, phone numbers, emails, addresses, and research prospects where available.")

    with st.form("discover_form"):
        col1, col2 = st.columns(2)
        with col1:
            industry = st.text_input("Industry", placeholder="Hotel, school, clinic, restaurant...", key="disc_industry")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja...", key="disc_location")
        with col2:
            keywords = st.text_input("Extra keywords", placeholder="contact, booking, admission, appointment...", key="disc_keywords")
            max_results = st.slider("Maximum prospects", 3, 50, 20, key="disc_max")
            deep_search = st.toggle("Deep search", value=False, help="Slower; checks extra search sources.", key="disc_deep")
        submitted = st.form_submit_button("Find Business Prospects", type="primary")

    if submitted:
        if not industry.strip():
            st.error("Enter an industry first.")
            return
        loading = st.empty()
        for title, subtitle in DISCOVERY_STAGES:
            loading.markdown(loader_html(title, subtitle), unsafe_allow_html=True)
            time.sleep(0.35)
        try:
            discovery = LeadDiscovery(timeout=8, enable_deep_search=deep_search)
            candidates = discovery.discover(industry, location, keywords, max_results=max_results)
        except Exception as exc:
            loading.empty()
            st.error(f"Discovery failed: {exc}")
            return
        loading.markdown(loader_html("✅ Mission complete.", "Sorting prospects and preparing save actions."), unsafe_allow_html=True)
        time.sleep(0.35)
        loading.empty()
        st.session_state["candidates"] = [c.to_dict() for c in candidates]
        st.session_state["debug"] = discovery.last_debug
        st.session_state["last_inputs"] = {"industry": industry, "location": location, "keywords": keywords}

    candidates = st.session_state.get("candidates", [])
    last_inputs = st.session_state.get("last_inputs", {})

    if not candidates:
        st.info("No prospects shown yet. Search an industry/location to begin. If automatic search is blocked, use the one-click fallback links below.")
        debug = st.session_state.get("debug", [])
        if debug:
            with st.expander("Search diagnostics", expanded=True):
                for item in debug:
                    st.write(f"- {item}")
        if last_inputs:
            links = build_manual_search_links(last_inputs.get("industry", ""), last_inputs.get("location", ""), last_inputs.get("keywords", ""))
            if links:
                st.write("### One-click fallback searches")
                st.dataframe(pd.DataFrame(links), use_container_width=True, hide_index=True)
        return

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Clear Previous Discovery Results", key="clear_disc"):
            st.session_state.pop("candidates", None)
            st.session_state.pop("debug", None)
            st.session_state.pop("last_inputs", None)
            st.rerun()
    with col_b:
        st.success(f"Found {len(candidates)} prospect(s).")

    df = pd.DataFrame(candidates)
    st.write("### Business Prospects")
    st.dataframe(df[candidate_columns(df)], use_container_width=True, hide_index=True)

    with st.expander("Search diagnostics"):
        for item in st.session_state.get("debug", []):
            st.write(f"- {item}")

    if not st.button("Save All Prospects", type="primary", key="save_prospects"):
        return

    saved = 0
    audited = 0
    failed = 0
    progress = st.progress(0)
    status_box = st.empty()
    auditor = WebsiteAuditor()

    for index, candidate in enumerate(candidates, start=1):
        name = candidate.get("business_name") or candidate.get("title") or "Unnamed business"
        website = candidate.get("website") or ""
        status_box.write(f"Saving {name}...")
        try:
            if website:
                try:
                    audit = auditor.audit(website)
                    save_lead(
                        audit,
                        business_name=name,
                        industry=candidate.get("industry") or None,
                        source=candidate.get("source") or None,
                        contact_email=candidate.get("email") or None,
                        phone=candidate.get("phone") or None,
                        location=candidate.get("location") or None,
                        address=candidate.get("address") or None,
                        notes=f"Discovered from: {candidate.get('search_query') or ''}",
                    )
                    audited += 1
                except Exception:
                    save_prospect(
                        business_name=name,
                        industry=candidate.get("industry") or None,
                        source=candidate.get("source") or None,
                        website=website,
                        contact_email=candidate.get("email") or None,
                        phone=candidate.get("phone") or None,
                        location=candidate.get("location") or None,
                        address=candidate.get("address") or None,
                        notes=f"Website found but audit failed. Research query: {candidate.get('search_query') or ''}",
                    )
            else:
                save_prospect(
                    business_name=name,
                    industry=candidate.get("industry") or None,
                    source=candidate.get("source") or None,
                    website=None,
                    contact_email=candidate.get("email") or None,
                    phone=candidate.get("phone") or None,
                    location=candidate.get("location") or None,
                    address=candidate.get("address") or None,
                    notes=f"Business prospect without confirmed website. Research query: {candidate.get('search_query') or ''}",
                )
            saved += 1
        except Exception as exc:
            failed += 1
            st.warning(f"Could not save {name}: {exc}")
        progress.progress(index / len(candidates))

    load_leads.clear()
    status_box.empty()
    st.success(f"Saved {saved} prospect(s). Audited {audited} website(s). Failed {failed}.")


def lead_options(leads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        f"#{lead['id']} · {lead.get('business_name') or 'Unnamed'} · {lead.get('status') or 'new'} · {lead.get('website') or 'No website'}": lead
        for lead in leads
    }


def render_manage(leads: list[dict[str, Any]]) -> None:
    st.subheader("Manage Prospects")
    if not leads:
        st.info("No saved prospects yet.")
        return
    options = lead_options(leads)
    selected_key = st.selectbox("Choose prospect", list(options.keys()), key="manage_select")
    lead = options[selected_key]
    st.write(f"**Business:** {lead.get('business_name') or '-'}")
    st.write(f"**Website:** {lead.get('website') or 'No website yet'}")
    st.write(f"**Phone:** {lead.get('phone') or '-'}")
    st.write(f"**Email:** {lead.get('contact_email') or '-'}")
    st.write(f"**Address:** {lead.get('address') or '-'}")
    current = lead.get("status") or "new"
    idx = VALID_LEAD_STATUSES.index(current) if current in VALID_LEAD_STATUSES else 0
    with st.form("manage_form"):
        new_status = st.selectbox("Status", VALID_LEAD_STATUSES, index=idx, key="manage_status")
        notes = st.text_area("Notes", value=lead.get("notes") or "", key="manage_notes")
        submitted = st.form_submit_button("Update Prospect", type="primary")
    if submitted:
        update_lead_status(int(lead["id"]), new_status, notes=notes)
        st.success("Prospect updated.")
        refresh()
    st.divider()
    confirm = st.checkbox("I understand this will permanently delete this prospect.", key="delete_confirm")
    if st.button("Delete Prospect", disabled=not confirm, key="delete_button"):
        delete_lead(int(lead["id"]))
        st.success("Prospect deleted.")
        refresh()


def render_outreach(leads: list[dict[str, Any]]) -> None:
    st.subheader("Outreach Generator")
    if not leads:
        st.info("No saved prospects yet.")
        return
    options = lead_options(leads)
    selected_key = st.selectbox("Choose prospect", list(options.keys()), key="outreach_select")
    lead = options[selected_key]
    outreach = build_outreach(lead)
    st.text_area("Email", outreach["email"], height=300, key="email_outreach")
    st.text_area("WhatsApp", outreach["whatsapp"], height=180, key="whatsapp_outreach")
    st.text_area("Mini Proposal", outreach["proposal"], height=360, key="proposal_outreach")


def render_manual_scan() -> None:
    st.subheader("Manual Website Scan")
    st.caption("Use this when you already have a website URL.")
    with st.form("manual_scan"):
        col1, col2 = st.columns(2)
        with col1:
            url = st.text_input("Website URL", placeholder="https://example.com", key="manual_url")
            business_name = st.text_input("Business name", key="manual_name")
            industry = st.text_input("Industry", key="manual_industry")
            location = st.text_input("Location", key="manual_location")
        with col2:
            source = st.text_input("Source", key="manual_source")
            contact_email = st.text_input("Email", key="manual_email")
            phone = st.text_input("Phone", key="manual_phone")
            address = st.text_input("Address", key="manual_address")
        submitted = st.form_submit_button("Audit and Save", type="primary")
    if submitted:
        if not url.strip():
            st.error("Enter a website URL.")
            return
        try:
            audit = WebsiteAuditor().audit(url)
            lead_id = save_lead(
                audit,
                business_name=business_name or None,
                industry=industry or None,
                source=source or None,
                contact_email=contact_email or None,
                phone=phone or None,
                location=location or None,
                address=address or None,
            )
            load_leads.clear()
            st.success(f"Saved website lead #{lead_id}.")
        except Exception as exc:
            st.error(f"Scan failed: {exc}")


def main() -> None:
    init_db()
    render_header()
    leads = load_leads()
    df = leads_dataframe(leads)
    filtered = filter_df(df)
    tab_overview, tab_discover, tab_manual, tab_manage, tab_outreach = st.tabs(
        ["Overview", "Discover Prospects", "Manual Scan", "Manage", "Outreach"]
    )
    with tab_overview:
        st.subheader("Pipeline Overview")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Saved prospects", len(leads))
        c2.metric("Without website", sum(1 for lead in leads if not lead.get("website")))
        c3.metric("With website", sum(1 for lead in leads if lead.get("website")))
        c4.metric("Won", sum(1 for lead in leads if lead.get("status") == "won"))
        if filtered.empty:
            st.info("No saved prospects yet. Start from Discover Prospects.")
        else:
            st.dataframe(filtered, use_container_width=True, hide_index=True)
            st.download_button(
                "Download prospects CSV",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name="wireless_bot_prospects.csv",
                mime="text/csv",
            )
    with tab_discover:
        render_discovery()
    with tab_manual:
        render_manual_scan()
    with tab_manage:
        render_manage(leads)
    with tab_outreach:
        render_outreach(leads)


if __name__ == "__main__":
    main()
