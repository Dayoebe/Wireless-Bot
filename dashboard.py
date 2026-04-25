from __future__ import annotations

import csv
import time
from io import StringIO
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
    update_lead_status,
)
from clienthunter.discovery import LeadDiscovery, build_manual_search_links
from clienthunter.outreach import build_outreach


st.set_page_config(
    page_title="Wireless Bot",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .wireless-hero {
        padding: 1.6rem 1.8rem;
        border-radius: 1.4rem;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        color: white;
        margin-bottom: 1.3rem;
    }
    .wireless-hero h1 {
        margin: 0;
        font-size: 2.1rem;
        letter-spacing: -0.03em;
    }
    .wireless-hero p {
        margin: .55rem 0 0 0;
        color: #dbeafe;
        max-width: 950px;
    }
    .status-pill {
        display: inline-block;
        padding: .18rem .6rem;
        border-radius: 999px;
        background: #e2e8f0;
        color: #0f172a;
        font-size: .8rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .wireless-loader {
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
    .wireless-loader::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,.08) 45%, transparent 70%);
        transform: translateX(-100%);
        animation: shimmerMove 2.8s infinite;
        pointer-events: none;
    }
    .wireless-loader-grid {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: 108px 1fr;
        gap: 1rem;
        align-items: center;
    }
    .wireless-loader h4 {
        margin: 0 0 .4rem 0;
        font-size: 1.05rem;
        color: #ffffff;
    }
    .wireless-loader p {
        margin: 0;
        color: #dbeafe;
        font-size: .94rem;
        line-height: 1.55;
    }
    .loader-subtitle {
        margin-top: .35rem !important;
        color: #93c5fd !important;
        font-size: .86rem !important;
    }
    .radar-shell {
        width: 96px;
        height: 96px;
        border-radius: 999px;
        position: relative;
        margin: 0 auto;
        background:
            radial-gradient(circle at center, rgba(134,239,172,.30) 0 7%, transparent 8% 100%),
            radial-gradient(circle, rgba(255,255,255,.12) 1px, transparent 1px);
        border: 1px solid rgba(255,255,255,.16);
        overflow: hidden;
        box-shadow: inset 0 0 25px rgba(34,197,94,.12), 0 0 22px rgba(34,197,94,.10);
    }
    .radar-ring,
    .radar-ring::before,
    .radar-ring::after {
        content: "";
        position: absolute;
        inset: 12%;
        border: 1px solid rgba(255,255,255,.16);
        border-radius: 999px;
    }
    .radar-ring::before { inset: 22%; }
    .radar-ring::after { inset: 34%; }
    .radar-cross-x,
    .radar-cross-y {
        position: absolute;
        background: rgba(255,255,255,.11);
    }
    .radar-cross-x { top: 50%; left: 0; right: 0; height: 1px; }
    .radar-cross-y { left: 50%; top: 0; bottom: 0; width: 1px; }
    .radar-sweep {
        position: absolute;
        inset: -12%;
        background: conic-gradient(
            from 0deg,
            rgba(34,197,94,0.00) 0deg,
            rgba(34,197,94,0.00) 275deg,
            rgba(74,222,128,0.18) 318deg,
            rgba(134,239,172,0.75) 348deg,
            rgba(34,197,94,0.00) 360deg
        );
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
    .radar-dot.dot-1 { top: 22px; left: 59px; animation-delay: 0s; }
    .radar-dot.dot-2 { top: 57px; left: 27px; animation-delay: .45s; }
    .radar-dot.dot-3 { top: 62px; left: 66px; animation-delay: .9s; }
    .loader-dots {
        display: flex;
        gap: .42rem;
        margin-top: .8rem;
        align-items: center;
    }
    .loader-dots span {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #93c5fd;
        animation: bounceDots 1.2s infinite ease-in-out;
    }
    .loader-dots span:nth-child(2) { animation-delay: .15s; }
    .loader-dots span:nth-child(3) { animation-delay: .3s; }
    .signal-bar-wrap {
        display: flex;
        gap: 4px;
        align-items: end;
        margin-top: .9rem;
    }
    .signal-bar {
        width: 6px;
        border-radius: 999px;
        background: linear-gradient(180deg, #93c5fd, #22c55e);
        animation: signalJump 1s infinite ease-in-out;
    }
    .signal-bar:nth-child(1) { height: 10px; animation-delay: 0s; }
    .signal-bar:nth-child(2) { height: 16px; animation-delay: .1s; }
    .signal-bar:nth-child(3) { height: 22px; animation-delay: .2s; }
    .signal-bar:nth-child(4) { height: 28px; animation-delay: .3s; }
    .mission-chip {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        margin-bottom: .55rem;
        padding: .18rem .55rem;
        border-radius: 999px;
        background: rgba(59,130,246,.18);
        color: #bfdbfe;
        font-size: .75rem;
        font-weight: 700;
        letter-spacing: .02em;
        text-transform: uppercase;
    }
    @keyframes radarSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    @keyframes dotPulse {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(134,239,172,.75); }
        70% { transform: scale(1.12); box-shadow: 0 0 0 13px rgba(134,239,172,0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(134,239,172,0); }
    }
    @keyframes bounceDots {
        0%, 80%, 100% { transform: translateY(0); opacity: .55; }
        40% { transform: translateY(-6px); opacity: 1; }
    }
    @keyframes signalJump {
        0%, 100% { transform: scaleY(0.78); opacity: .72; }
        50% { transform: scaleY(1.22); opacity: 1; }
    }
    @keyframes shimmerMove {
        0% { transform: translateX(-110%); }
        70%, 100% { transform: translateX(120%); }
    }
    @media (max-width: 768px) {
        .wireless-loader-grid {
            grid-template-columns: 1fr;
            text-align: center;
        }
        .loader-dots,
        .signal-bar-wrap {
            justify-content: center;
        }
    }
</style>
"""

FUN_DISCOVERY_STAGES = [
    (
        "📡 Raising antenna and scanning local signals.",
        "Looking around your target location for possible businesses.",
    ),
    (
        "🧭 Checking maps, directories, and search result trails.",
        "Real clients live offline too, so map data comes first.",
    ),
    (
        "🕵️ Filtering weak matches and suspicious links.",
        "Dropping noisy pages so you do not chase shadows.",
    ),
    (
        "💼 Packing promising prospects into your pipeline.",
        "The goal is simple: fewer guesses, more client conversations.",
    ),
    (
        "🚀 Almost there. Preparing candidates and fallback searches.",
        "If automatic discovery gets blocked, you still get one-click research links.",
    ),
]


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=10)
def load_leads() -> list[dict[str, Any]]:
    init_db()
    return [dict(row) for row in all_leads()]


def clear_lead_cache() -> None:
    load_leads.clear()


def refresh_dashboard() -> None:
    clear_lead_cache()
    st.rerun()


def render_waiting_animation(stage_text: str, subtitle: str = "") -> str:
    subtitle_html = f"<p class='loader-subtitle'>{subtitle}</p>" if subtitle else ""
    return f"""
    <div class="wireless-loader">
        <div class="wireless-loader-grid">
            <div class="radar-shell">
                <div class="radar-ring"></div>
                <div class="radar-cross-x"></div>
                <div class="radar-cross-y"></div>
                <div class="radar-sweep"></div>
                <div class="radar-dot dot-1"></div>
                <div class="radar-dot dot-2"></div>
                <div class="radar-dot dot-3"></div>
            </div>
            <div>
                <div class="mission-chip">Wireless Mission Active</div>
                <h4>Wireless Bot is scouting for leads...</h4>
                <p>{stage_text}</p>
                {subtitle_html}
                <div class="loader-dots"><span></span><span></span><span></span></div>
                <div class="signal-bar-wrap">
                    <div class="signal-bar"></div>
                    <div class="signal-bar"></div>
                    <div class="signal-bar"></div>
                    <div class="signal-bar"></div>
                </div>
            </div>
        </div>
    </div>
    """


def leads_dataframe(leads: list[dict[str, Any]]) -> pd.DataFrame:
    if not leads:
        return pd.DataFrame()

    df = pd.DataFrame(leads)
    preferred_columns = [
        "id",
        "business_name",
        "website",
        "industry",
        "location",
        "status",
        "opportunity_score",
        "footer_year",
        "stale_footer",
        "detected_platform",
        "contact_name",
        "contact_email",
        "phone",
        "source",
        "notes",
        "created_at",
        "updated_at",
    ]
    available_columns = [column for column in preferred_columns if column in df.columns]
    remaining_columns = [column for column in df.columns if column not in available_columns]
    return df[available_columns + remaining_columns]


def filter_leads(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    with st.sidebar:
        st.subheader("Filters")
        status_options = ["all", *VALID_LEAD_STATUSES]
        selected_status = st.selectbox("Status", status_options, key="sidebar_status_filter")
        min_score = st.slider("Minimum opportunity score", 0, 100, 0, key="sidebar_min_score_filter")
        search_term = st.text_input("Search business, website, industry, or location", key="sidebar_search_filter")

    filtered = df.copy()

    if selected_status != "all" and "status" in filtered.columns:
        filtered = filtered[filtered["status"].fillna("new") == selected_status]

    if "opportunity_score" in filtered.columns:
        filtered = filtered[filtered["opportunity_score"].fillna(0).astype(int) >= min_score]

    if search_term.strip():
        text = search_term.strip().lower()
        searchable_columns = [
            column
            for column in ["business_name", "website", "industry", "location", "source"]
            if column in filtered.columns
        ]
        mask = pd.Series(False, index=filtered.index)
        for column in searchable_columns:
            mask = mask | filtered[column].fillna("").astype(str).str.lower().str.contains(text, regex=False)
        filtered = filtered[mask]

    return filtered


def lead_label(lead: dict[str, Any]) -> str:
    business = lead.get("business_name") or "Unnamed business"
    website = lead.get("website") or "No website"
    status = lead.get("status") or "new"
    score = lead.get("opportunity_score") or 0
    return f"#{lead['id']} · {business} · {status} · {score}/100 · {website}"


def selected_lead(leads: list[dict[str, Any]], key: str, label: str = "Choose a lead") -> dict[str, Any] | None:
    if not leads:
        return None
    options = {lead_label(lead): lead for lead in leads}
    selected = st.selectbox(label, list(options.keys()), key=key)
    return options[selected]


def render_header() -> None:
    st.markdown(
        """
        <div class="wireless-hero">
            <h1>📡 Wireless Bot</h1>
            <p>A local prospecting dashboard for discovering business websites, auditing opportunities, tracking leads, and generating outreach that can win clients.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(leads: list[dict[str, Any]], filtered_df: pd.DataFrame) -> None:
    st.subheader("Lead Overview")

    total_leads = len(leads)
    high_value = sum(1 for lead in leads if int(lead.get("opportunity_score") or 0) >= 70)
    contacted = sum(1 for lead in leads if lead.get("status") == "contacted")
    won = sum(1 for lead in leads if lead.get("status") == "won")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads", total_leads)
    col2.metric("High Opportunity", high_value)
    col3.metric("Contacted", contacted)
    col4.metric("Won", won)

    st.divider()

    if filtered_df.empty:
        st.info("No leads match the current filter. Discover leads, scan a website, or import a CSV to begin.")
        return

    chart_col, table_col = st.columns([1, 2])

    with chart_col:
        if "status" in filtered_df.columns:
            status_counts = filtered_df["status"].fillna("new").value_counts().rename_axis("status").reset_index(name="count")
            st.bar_chart(status_counts, x="status", y="count")

    with table_col:
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered leads as CSV",
        data=csv_data,
        file_name="wireless_bot_filtered_leads.csv",
        mime="text/csv",
        key="download_filtered_leads_csv",
    )


def render_manual_search_links(industry: str, location: str, keywords: str) -> None:
    links = build_manual_search_links(industry, location, keywords)
    if not links:
        return

    st.write("### One-click fallback searches")
    st.caption("Automatic discovery can be blocked by search engines. These links open ready-made searches so you can still find businesses faster and paste any good website into Manual Scan.")

    links_df = pd.DataFrame(links)
    st.dataframe(links_df, use_container_width=True, hide_index=True)

    for link in links[:6]:
        st.markdown(f"- [{link['source']} — {link['query']}]({link['url']})")


def render_discover_leads() -> None:
    st.subheader("Discover Leads Automatically")
    st.caption("Enter an industry and location. Wireless Bot will find likely business websites, then you can audit and save them as leads.")

    with st.form("discover_leads_form"):
        col1, col2 = st.columns(2)
        with col1:
            industry = st.text_input("Industry", placeholder="Hotel, clinic, school, real estate, logistics...", key="discover_industry")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja, Ibadan...", key="discover_location")
        with col2:
            keywords = st.text_input("Extra keywords", placeholder="booking, appointment, services, contact...", key="discover_keywords")
            max_results = st.slider("Maximum candidates", 3, 25, 10, key="discover_max_results")
            deep_search = st.toggle("Deep search", value=False, help="Slower, but checks extra search engines.", key="discover_deep_search")
        submitted = st.form_submit_button("Find Candidate Websites", type="primary")

    if submitted:
        if not industry.strip():
            st.error("Please enter an industry first.")
            return

        loading_box = st.empty()
        for stage_text, subtitle in FUN_DISCOVERY_STAGES:
            loading_box.markdown(
                render_waiting_animation(stage_text, subtitle),
                unsafe_allow_html=True,
            )
            time.sleep(0.35)

        try:
            discovery = LeadDiscovery(timeout=8, enable_deep_search=deep_search)
            candidates = discovery.discover(
                industry=industry,
                location=location,
                keywords=keywords,
                max_results=max_results,
            )
        except Exception as exc:
            loading_box.empty()
            st.error(f"Discovery failed: {exc}")
            return

        loading_box.markdown(
            render_waiting_animation(
                "✅ Mission complete. Sorting what Wireless Bot found.",
                "Preparing results, diagnostics, and fallback links now.",
            ),
            unsafe_allow_html=True,
        )
        time.sleep(0.35)
        loading_box.empty()

        st.session_state["last_discovery_inputs"] = {
            "industry": industry,
            "location": location,
            "keywords": keywords,
        }
        st.session_state["discovered_candidates"] = [candidate.to_dict() for candidate in candidates]
        st.session_state["discovery_debug"] = discovery.last_debug

    candidates = st.session_state.get("discovered_candidates", [])
    last_inputs = st.session_state.get("last_discovery_inputs", {})

    if not candidates:
        st.info("No candidate websites found yet. Try a broader search like `Hotel`, `Clinic`, `School`, or add a nearby city/state.")
        debug_lines = st.session_state.get("discovery_debug", [])
        if debug_lines:
            with st.expander("Search diagnostics", expanded=True):
                for line in debug_lines:
                    st.write(f"- {line}")
        if last_inputs:
            render_manual_search_links(
                last_inputs.get("industry", ""),
                last_inputs.get("location", ""),
                last_inputs.get("keywords", ""),
            )
        return

    if st.button("Clear Previous Discovery Results", key="clear_discovery_results"):
        st.session_state.pop("discovered_candidates", None)
        st.session_state.pop("discovery_debug", None)
        st.session_state.pop("last_discovery_inputs", None)
        st.success("Previous discovery results cleared.")
        st.rerun()

    candidates_df = pd.DataFrame(candidates)
    st.write("### Candidate Websites")
    st.dataframe(
        candidates_df[["business_name", "website", "industry", "location", "source", "search_query", "snippet"]],
        use_container_width=True,
        hide_index=True,
    )

    st.caption("Review the candidates before saving. Search results can include false positives, directories, or irrelevant websites, so verify important leads before outreach.")

    if not st.button("Audit and Save These Candidates", type="primary", key="audit_save_discovered_candidates"):
        return

    auditor = WebsiteAuditor()
    saved = 0
    skipped = 0
    progress = st.progress(0)
    status_box = st.empty()

    for index, candidate in enumerate(candidates, start=1):
        website = candidate.get("website")
        if not website:
            skipped += 1
            progress.progress(index / len(candidates))
            continue

        status_box.write(f"Auditing {website}...")
        try:
            audit = auditor.audit(website)
            save_lead(
                audit,
                business_name=candidate.get("business_name") or None,
                industry=candidate.get("industry") or None,
                source=candidate.get("source") or "Web Discovery",
                location=candidate.get("location") or None,
                status="new",
                notes=f"Discovered from query: {candidate.get('search_query') or ''}",
            )
            saved += 1
        except Exception as exc:
            skipped += 1
            st.warning(f"Skipped {website}: {exc}")

        progress.progress(index / len(candidates))

    clear_lead_cache()
    status_box.empty()
    st.success(f"Discovery import complete. Saved {saved} lead(s), skipped {skipped}.")


def render_scan_form() -> None:
    st.subheader("Manual Scan and Save")
    st.caption("Use this when you already have a website URL. For less manual work, use Discover Leads first.")

    with st.form("scan_lead_form"):
        col1, col2 = st.columns(2)
        with col1:
            url = st.text_input("Website URL", placeholder="https://example.com", key="manual_url")
            business_name = st.text_input("Business Name", placeholder="Example Hotel", key="manual_business_name")
            industry = st.text_input("Industry", placeholder="Hotel, Clinic, SaaS, School...", key="manual_industry")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja...", key="manual_location")
        with col2:
            source = st.text_input("Lead Source", placeholder="Google Business Profile, LinkedIn, Manual Research...", key="manual_source")
            contact_name = st.text_input("Contact Name", placeholder="Manager", key="manual_contact_name")
            contact_email = st.text_input("Contact Email", placeholder="hello@example.com", key="manual_contact_email")
            phone = st.text_input("Phone", placeholder="+234...", key="manual_phone")

        status = st.selectbox("Initial Status", VALID_LEAD_STATUSES, index=0, key="manual_initial_status")
        notes = st.text_area("Internal Notes", placeholder="Why this lead looks promising, who to contact, or what you noticed.", key="manual_notes")
        submitted = st.form_submit_button("Scan Website and Save Lead", type="primary")

    if not submitted:
        return

    if not url.strip():
        st.error("Please enter a website URL.")
        return

    with st.spinner("Auditing website and saving lead..."):
        try:
            audit = WebsiteAuditor().audit(url)
            lead_id = save_lead(
                audit,
                business_name=business_name or None,
                industry=industry or None,
                source=source or None,
                contact_name=contact_name or None,
                contact_email=contact_email or None,
                phone=phone or None,
                location=location or None,
                status=status,
                notes=notes or None,
            )
            clear_lead_cache()
        except Exception as exc:
            st.error(f"Scan failed: {exc}")
            return

    st.success(f"Lead #{lead_id} saved successfully.")

    result = audit.to_dict()
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Score", f"{result['opportunity_score']}/100")
    metric_col2.metric("Status Code", result["status_code"])
    metric_col3.metric("Response Time", f"{result['response_time_ms']}ms")
    metric_col4.metric("Page Size", f"{result['page_size_kb']}KB")

    st.write("### Issues")
    if result["issues"]:
        for issue in result["issues"]:
            st.warning(issue)
    else:
        st.success("No major issues found.")

    st.write("### Recommendations")
    for recommendation in result["recommendations"]:
        st.info(recommendation)


def render_manage_leads(leads: list[dict[str, Any]]) -> None:
    st.subheader("Manage Lead Status")

    selected = selected_lead(leads, key="manage_status_lead_select")
    if selected is None:
        st.info("No leads yet. Discover, scan, or import leads first.")
        return

    st.markdown(f"**Business:** {selected.get('business_name') or '-'}")
    st.markdown(f"**Website:** {selected.get('website') or '-'}")
    st.markdown(f"**Current Status:** <span class='status-pill'>{selected.get('status') or 'new'}</span>", unsafe_allow_html=True)

    current_status = selected.get("status") or "new"
    current_index = VALID_LEAD_STATUSES.index(current_status) if current_status in VALID_LEAD_STATUSES else 0

    with st.form("update_status_form"):
        new_status = st.selectbox("New Status", VALID_LEAD_STATUSES, index=current_index, key="manage_status_new_status")
        notes = st.text_area("Notes", value=selected.get("notes") or "", key="manage_status_notes")
        submitted = st.form_submit_button("Update Status", type="primary")

    if submitted:
        try:
            updated = update_lead_status(int(selected["id"]), new_status, notes=notes or None)
            clear_lead_cache()
        except Exception as exc:
            st.error(f"Could not update lead: {exc}")
            return
        if updated is None:
            st.error("Lead not found.")
        else:
            st.success(f"Lead #{selected['id']} updated to {new_status}.")

    st.divider()
    st.write("### Remove Lead")
    confirm_delete = st.checkbox(
        f"I understand this will permanently delete lead #{selected['id']}.",
        key="manage_delete_confirm",
    )
    if st.button("Delete Selected Lead", type="secondary", disabled=not confirm_delete, key="manage_delete_button"):
        if delete_lead(int(selected["id"])):
            st.success(f"Lead #{selected['id']} deleted.")
            refresh_dashboard()
        else:
            st.error("Lead could not be deleted.")


def render_outreach(leads: list[dict[str, Any]]) -> None:
    st.subheader("Outreach Generator")

    selected = selected_lead(leads, key="outreach_lead_select")
    if selected is None:
        st.info("No leads yet. Discover, scan, or import leads first.")
        return

    outreach = build_outreach(selected)
    st.write("Use these as a starting point. Personalize before sending.")

    st.write("### Email")
    st.text_area("Email Pitch", outreach["email"], height=320, key="outreach_email_text")

    st.write("### WhatsApp")
    st.text_area("WhatsApp Pitch", outreach["whatsapp"], height=180, key="outreach_whatsapp_text")

    st.write("### Mini Proposal")
    st.text_area("Mini Proposal", outreach["proposal"], height=420, key="outreach_proposal_text")


def render_bulk_import() -> None:
    st.subheader("Bulk Import and Scan")
    st.caption("Upload a CSV with business_name, website, industry, source, contact_name, contact_email, phone, location, status, and notes columns.")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key="bulk_import_csv")

    if uploaded_file is None:
        st.info("You can start with data/sample_leads.csv as a template.")
        return

    content = uploaded_file.getvalue().decode("utf-8-sig")
    rows = list(csv.DictReader(StringIO(content)))

    if not rows:
        st.error("The uploaded CSV is empty.")
        return

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not st.button("Scan and Save Uploaded Leads", type="primary", key="bulk_scan_save"):
        return

    auditor = WebsiteAuditor()
    saved = 0
    skipped = 0
    progress = st.progress(0)
    status_box = st.empty()

    for index, row in enumerate(rows, start=1):
        website = row.get("website") or row.get("url")
        if not website:
            skipped += 1
            progress.progress(index / len(rows))
            continue

        status_box.write(f"Scanning {website}...")
        try:
            audit = auditor.audit(website)
            save_lead(
                audit,
                business_name=row.get("business_name") or None,
                industry=row.get("industry") or None,
                source=row.get("source") or None,
                contact_name=row.get("contact_name") or None,
                contact_email=row.get("contact_email") or None,
                phone=row.get("phone") or None,
                location=row.get("location") or None,
                status=row.get("status") or "new",
                notes=row.get("notes") or None,
            )
            saved += 1
        except Exception as exc:
            skipped += 1
            st.warning(f"Skipped {website}: {exc}")

        progress.progress(index / len(rows))

    clear_lead_cache()
    status_box.empty()
    st.success(f"Bulk scan complete. Saved {saved} lead(s), skipped {skipped}.")


def main() -> None:
    init_db()
    render_header()

    leads = load_leads()
    df = leads_dataframe(leads)

    with st.sidebar:
        st.title("Wireless Bot")
        st.caption("Client prospecting pipeline")
        st.divider()

    filtered_df = filter_leads(df)

    overview_tab, discover_tab, scan_tab, manage_tab, outreach_tab, import_tab = st.tabs(
        ["Overview", "Discover Leads", "Manual Scan", "Manage Status", "Outreach", "Bulk Import"]
    )

    with overview_tab:
        render_overview(leads, filtered_df)
    with discover_tab:
        render_discover_leads()
    with scan_tab:
        render_scan_form()
    with manage_tab:
        render_manage_leads(leads)
    with outreach_tab:
        render_outreach(leads)
    with import_tab:
        render_bulk_import()


if __name__ == "__main__":
    main()
