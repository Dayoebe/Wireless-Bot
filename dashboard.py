from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from clienthunter.auditor import WebsiteAuditor
from clienthunter.database import (
    VALID_LEAD_STATUSES,
    all_leads,
    init_db,
    save_lead,
    update_lead_status,
)
from clienthunter.discovery import LeadDiscovery
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
    .small-muted {
        color: #64748b;
        font-size: .88rem;
    }
</style>
"""


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=10)
def load_leads() -> list[dict[str, Any]]:
    init_db()
    return [dict(row) for row in all_leads()]


def clear_lead_cache() -> None:
    load_leads.clear()


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
        selected_status = st.selectbox("Status", status_options)
        min_score = st.slider("Minimum opportunity score", 0, 100, 0)
        search_term = st.text_input("Search business, website, industry, or location")

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


def selected_lead_from_sidebar(leads: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not leads:
        return None

    options = {lead_label(lead): lead for lead in leads}
    selected = st.selectbox("Choose a lead", list(options.keys()))
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
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
        )

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered leads as CSV",
        data=csv_data,
        file_name="wireless_bot_filtered_leads.csv",
        mime="text/csv",
    )


def render_discover_leads() -> None:
    st.subheader("Discover Leads Automatically")
    st.caption("Enter an industry and location. Wireless Bot will find likely business websites, then you can audit and save them as leads.")

    with st.form("discover_leads_form"):
        col1, col2 = st.columns(2)
        with col1:
            industry = st.text_input("Industry", placeholder="Hotel, clinic, school, real estate, logistics...")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja, Ibadan...")
        with col2:
            keywords = st.text_input("Extra keywords", placeholder="booking, appointment, services, contact...")
            max_results = st.slider("Maximum candidates", 3, 25, 10)

        submitted = st.form_submit_button("Find Candidate Websites", type="primary")

    if submitted:
        if not industry.strip():
            st.error("Please enter an industry first.")
            return

        with st.spinner("Searching for candidate business websites..."):
            try:
                candidates = LeadDiscovery().discover(
                    industry=industry,
                    location=location,
                    keywords=keywords,
                    max_results=max_results,
                )
            except Exception as exc:
                st.error(f"Discovery failed: {exc}")
                return

        st.session_state["discovered_candidates"] = [candidate.to_dict() for candidate in candidates]

    candidates = st.session_state.get("discovered_candidates", [])

    if not candidates:
        st.info("No candidates yet. Search with an industry and location to begin.")
        return

    candidates_df = pd.DataFrame(candidates)
    st.write("### Candidate Websites")
    st.dataframe(
        candidates_df[["business_name", "website", "industry", "location", "search_query", "snippet"]],
        use_container_width=True,
        hide_index=True,
    )

    st.caption("Review the candidates before saving. Search results can include false positives, so always verify important leads manually before outreach.")

    if not st.button("Audit and Save These Candidates", type="primary"):
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
            url = st.text_input("Website URL", placeholder="https://example.com")
            business_name = st.text_input("Business Name", placeholder="Example Hotel")
            industry = st.text_input("Industry", placeholder="Hotel, Clinic, SaaS, School...")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja...")
        with col2:
            source = st.text_input("Lead Source", placeholder="Google Business Profile, LinkedIn, Manual Research...")
            contact_name = st.text_input("Contact Name", placeholder="Manager")
            contact_email = st.text_input("Contact Email", placeholder="hello@example.com")
            phone = st.text_input("Phone", placeholder="+234...")

        status = st.selectbox("Initial Status", VALID_LEAD_STATUSES, index=0)
        notes = st.text_area("Internal Notes", placeholder="Why this lead looks promising, who to contact, or what you noticed.")
        submitted = st.form_submit_button("Scan Website and Save Lead", type="primary")

    if not submitted:
        return

    if not url.strip():
        st.error("Please enter a website URL.")
        return

    with st.spinner("Auditing website and saving lead..."):
        try:
            auditor = WebsiteAuditor()
            audit = auditor.audit(url)
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

    selected_lead = selected_lead_from_sidebar(leads)
    if selected_lead is None:
        st.info("No leads yet. Discover, scan, or import leads first.")
        return

    st.markdown(f"**Business:** {selected_lead.get('business_name') or '-'}")
    st.markdown(f"**Website:** {selected_lead.get('website') or '-'}")
    st.markdown(f"**Current Status:** <span class='status-pill'>{selected_lead.get('status') or 'new'}</span>", unsafe_allow_html=True)

    current_status = selected_lead.get("status") or "new"
    current_index = VALID_LEAD_STATUSES.index(current_status) if current_status in VALID_LEAD_STATUSES else 0

    with st.form("update_status_form"):
        new_status = st.selectbox("New Status", VALID_LEAD_STATUSES, index=current_index)
        notes = st.text_area("Notes", value=selected_lead.get("notes") or "")
        submitted = st.form_submit_button("Update Status", type="primary")

    if submitted:
        try:
            updated = update_lead_status(int(selected_lead["id"]), new_status, notes=notes or None)
            clear_lead_cache()
        except Exception as exc:
            st.error(f"Could not update lead: {exc}")
            return

        if updated is None:
            st.error("Lead not found.")
        else:
            st.success(f"Lead #{selected_lead['id']} updated to {new_status}.")


def render_outreach(leads: list[dict[str, Any]]) -> None:
    st.subheader("Outreach Generator")

    selected_lead = selected_lead_from_sidebar(leads)
    if selected_lead is None:
        st.info("No leads yet. Discover, scan, or import leads first.")
        return

    outreach = build_outreach(selected_lead)

    st.write("Use these as a starting point. Personalize before sending.")

    st.write("### Email")
    st.text_area("Email Pitch", outreach["email"], height=320)

    st.write("### WhatsApp")
    st.text_area("WhatsApp Pitch", outreach["whatsapp"], height=180)

    st.write("### Mini Proposal")
    st.text_area("Mini Proposal", outreach["proposal"], height=420)


def render_bulk_import() -> None:
    st.subheader("Bulk Import and Scan")
    st.caption("Upload a CSV with business_name, website, industry, source, contact_name, contact_email, phone, location, status, and notes columns.")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file is None:
        st.info("You can start with data/sample_leads.csv as a template.")
        return

    content = uploaded_file.getvalue().decode("utf-8-sig")
    reader = csv.DictReader(StringIO(content))
    rows = list(reader)

    if not rows:
        st.error("The uploaded CSV is empty.")
        return

    preview_df = pd.DataFrame(rows)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    if not st.button("Scan and Save Uploaded Leads", type="primary"):
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
