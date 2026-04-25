from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from clienthunter.auditor import WebsiteAuditor
from clienthunter.database import all_leads, get_lead, init_db, list_leads, save_lead
from clienthunter.exporter import export_leads
from clienthunter.outreach import build_outreach

st.set_page_config(
    page_title="Wireless Bot",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .wireless-hero {
        padding: 2rem;
        border-radius: 1.5rem;
        background: linear-gradient(135deg, #020617 0%, #111827 55%, #1e293b 100%);
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
    }
    .wireless-hero h1 {
        font-size: 2.5rem;
        line-height: 1.05;
        margin-bottom: 0.75rem;
        font-weight: 900;
    }
    .wireless-hero p {
        color: #cbd5e1;
        max-width: 760px;
        font-size: 1.05rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
        font-size: 0.85rem;
        margin-bottom: 0.85rem;
    }
    .lead-card {
        padding: 1rem;
        border: 1px solid #e2e8f0;
        border-radius: 1rem;
        background: white;
        margin-bottom: 0.8rem;
    }
    .small-muted {
        color: #64748b;
        font-size: 0.9rem;
    }
    .score-hot {
        color: #16a34a;
        font-weight: 800;
    }
    .score-warm {
        color: #d97706;
        font-weight: 800;
    }
    .score-review {
        color: #475569;
        font-weight: 800;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
init_db()


def score_class(score: int | None) -> str:
    value = score or 0
    if value >= 80:
        return "score-hot"
    if value >= 60:
        return "score-warm"
    return "score-review"


def rows_to_dataframe(rows) -> pd.DataFrame:
    data = [dict(row) for row in rows]
    return pd.DataFrame(data) if data else pd.DataFrame()


def show_metric_cards() -> None:
    rows = all_leads()
    total = len(rows)
    hot = len([row for row in rows if (row["opportunity_score"] or 0) >= 80])
    warm = len([row for row in rows if 60 <= (row["opportunity_score"] or 0) < 80])
    stale = len([row for row in rows if row["stale_footer"]])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Leads", total)
    col2.metric("Hot Prospects", hot)
    col3.metric("Warm Prospects", warm)
    col4.metric("Old Footer Signals", stale)


def render_audit_result(audit, lead_id: int) -> None:
    st.success(f"Audit complete. Saved as Lead #{lead_id}.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Opportunity Score", f"{audit.opportunity_score}/100")
    col2.metric("Status Code", audit.status_code)
    col3.metric("Response Time", f"{audit.response_time_ms}ms")
    col4.metric("Footer Year", audit.footer_year or "Not found")

    with st.expander("View audit details", expanded=True):
        st.write(
            {
                "URL": audit.url,
                "Final URL": audit.final_url,
                "Title": audit.title,
                "Meta Description": audit.meta_description,
                "Detected Platform": audit.detected_platform,
                "HTTPS Enabled": audit.https_enabled,
                "Mobile Viewport": audit.has_viewport,
                "Sitemap": audit.has_sitemap,
                "Robots": audit.has_robots,
                "Open Graph": audit.has_open_graph,
                "Schema": audit.has_schema,
            }
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Issues Found")
        if audit.issues:
            for issue in audit.issues:
                st.warning(issue)
        else:
            st.info("No major issues found.")

    with col_b:
        st.subheader("Recommendations")
        if audit.recommendations:
            for recommendation in audit.recommendations:
                st.success(recommendation)
        else:
            st.info("No recommendations generated.")

    st.info(f"Go to the Pitch Generator tab and select Lead #{lead_id} to generate outreach content.")


st.sidebar.title("Wireless Bot")
st.sidebar.caption("Prospecting, website audit, and outreach assistant.")
section = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Single Website Audit",
        "Bulk CSV Audit",
        "Saved Leads",
        "Pitch Generator",
        "Export",
        "Playbook",
    ],
)

st.markdown(
    """
    <div class="wireless-hero">
        <div class="status-pill">🛰️ Wireless Bot · Enterprise Prospecting Engine</div>
        <h1>Find businesses that need better websites.</h1>
        <p>Audit websites, score opportunities, save leads, and generate email, WhatsApp, and proposal content from one local Debian-friendly dashboard.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if section == "Dashboard":
    show_metric_cards()
    st.divider()

    st.subheader("Recent Leads")
    recent_rows = list_leads(limit=8)

    if not recent_rows:
        st.info("No leads yet. Start with Single Website Audit or Bulk CSV Audit.")
    else:
        for row in recent_rows:
            score = row["opportunity_score"] or 0
            st.markdown(
                f"""
                <div class="lead-card">
                    <strong>{row['business_name'] or 'Unnamed Business'}</strong>
                    <div class="small-muted">{row['website']} · {row['industry'] or 'No industry'} · Created {row['created_at']}</div>
                    <div class="{score_class(score)}">Opportunity Score: {score}/100</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

elif section == "Single Website Audit":
    st.subheader("Audit One Website")
    st.caption("Use this when you already have a business website you want to inspect.")

    with st.form("single_audit_form"):
        col1, col2 = st.columns(2)
        with col1:
            website = st.text_input("Website URL", placeholder="https://example.com")
            business_name = st.text_input("Business Name", placeholder="Example Business")
            industry = st.text_input("Industry", placeholder="Hotel, SaaS, Clinic, Real Estate...")
        with col2:
            source = st.text_input("Lead Source", placeholder="Google Business Profile, LinkedIn, Referral...")
            contact_email = st.text_input("Contact Email", placeholder="hello@example.com")
            phone = st.text_input("Phone/WhatsApp", placeholder="+234...")
            location = st.text_input("Location", placeholder="Akure, Lagos, Abuja, Remote...")

        submitted = st.form_submit_button("Run Website Audit", use_container_width=True)

    if submitted:
        if not website.strip():
            st.error("Please enter a website URL.")
        else:
            with st.spinner("Auditing website and saving lead..."):
                auditor = WebsiteAuditor()
                audit = auditor.audit(website)
                lead_id = save_lead(
                    audit,
                    business_name=business_name or None,
                    industry=industry or None,
                    source=source or None,
                    contact_email=contact_email or None,
                    phone=phone or None,
                    location=location or None,
                )
            render_audit_result(audit, lead_id)

elif section == "Bulk CSV Audit":
    st.subheader("Bulk Audit from CSV")
    st.caption("Upload a CSV with columns: business_name, website, industry, source, contact_email, phone, location.")

    uploaded_file = st.file_uploader("Upload leads CSV", type=["csv"])

    if uploaded_file:
        preview_df = pd.read_csv(uploaded_file)
        st.write("Preview")
        st.dataframe(preview_df.head(20), use_container_width=True)

        if st.button("Run Bulk Audit", use_container_width=True):
            if "website" not in preview_df.columns and "url" not in preview_df.columns:
                st.error("CSV must contain either a website or url column.")
            else:
                progress = st.progress(0)
                status_box = st.empty()
                auditor = WebsiteAuditor()
                saved_ids = []

                for index, row in preview_df.iterrows():
                    website = row.get("website") or row.get("url")
                    if pd.isna(website) or not str(website).strip():
                        continue

                    status_box.info(f"Scanning {website}...")
                    audit = auditor.audit(str(website))
                    lead_id = save_lead(
                        audit,
                        business_name=None if pd.isna(row.get("business_name")) else row.get("business_name"),
                        industry=None if pd.isna(row.get("industry")) else row.get("industry"),
                        source=None if pd.isna(row.get("source")) else row.get("source"),
                        contact_email=None if pd.isna(row.get("contact_email")) else row.get("contact_email"),
                        phone=None if pd.isna(row.get("phone")) else row.get("phone"),
                        location=None if pd.isna(row.get("location")) else row.get("location"),
                    )
                    saved_ids.append(lead_id)
                    progress.progress((index + 1) / len(preview_df))

                status_box.success(f"Bulk audit complete. Saved {len(saved_ids)} lead(s).")

elif section == "Saved Leads":
    st.subheader("Saved Leads")
    rows = all_leads()
    df = rows_to_dataframe(rows)

    if df.empty:
        st.info("No saved leads yet.")
    else:
        score_filter = st.slider("Minimum opportunity score", 0, 100, 0)
        filtered = df[df["opportunity_score"].fillna(0) >= score_filter]
        st.dataframe(filtered, use_container_width=True, hide_index=True)

elif section == "Pitch Generator":
    st.subheader("Pitch Generator")
    rows = all_leads()

    if not rows:
        st.info("No leads yet. Audit a website first.")
    else:
        options = {
            f"#{row['id']} · {row['business_name'] or row['website']} · Score {row['opportunity_score']}/100": row["id"]
            for row in rows
        }
        selected_label = st.selectbox("Select Lead", list(options.keys()))
        selected_id = options[selected_label]
        lead = get_lead(selected_id)

        if lead:
            outreach = build_outreach(lead)
            tab1, tab2, tab3 = st.tabs(["Email", "WhatsApp", "Mini Proposal"])
            with tab1:
                st.text_area("Email Pitch", outreach["email"], height=360)
            with tab2:
                st.text_area("WhatsApp Pitch", outreach["whatsapp"], height=260)
            with tab3:
                st.text_area("Mini Proposal", outreach["proposal"], height=420)

elif section == "Export":
    st.subheader("Export Leads")
    st.caption("Export your saved leads to CSV for follow-up, spreadsheet work, or CRM import.")

    if st.button("Generate CSV Export", use_container_width=True):
        output_path = export_leads()
        st.success(f"Export created: {output_path}")
        with open(output_path, "rb") as file:
            st.download_button(
                label="Download CSV",
                data=file,
                file_name=Path(output_path).name,
                mime="text/csv",
                use_container_width=True,
            )

elif section == "Playbook":
    st.subheader("Prospecting Playbook")
    playbook_path = Path("docs/prospecting-playbook.md")
    if playbook_path.exists():
        st.markdown(playbook_path.read_text(encoding="utf-8"))
    else:
        st.info("Playbook file not found.")
