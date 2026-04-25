from __future__ import annotations

import json
from sqlite3 import Row
from textwrap import dedent
from typing import Any

from jinja2 import Environment

TEMPLATE_ENV = Environment(trim_blocks=True, lstrip_blocks=True)


EMAIL_TEMPLATE = TEMPLATE_ENV.from_string(
    dedent(
        """
        Subject: Quick idea to improve {{ business_name }}'s online presence

        Hello {{ contact_name }},

        I came across {{ business_name }} and took a quick look at your online presence. I noticed a few areas that can be improved to make the business look more current, trustworthy, and easier for customers to contact.

        A few observations:
        {% for issue in issues[:5] -%}
        - {{ issue }}
        {% else -%}
        - Your website may benefit from a deeper UX, SEO, and conversion review.
        {% endfor %}

        I help businesses build and improve websites that are faster, mobile-friendly, search-friendly, and designed to convert visitors into enquiries.

        For {{ industry_label }}, I can help with:
        {% for rec in recommendations[:5] -%}
        - {{ rec }}
        {% else -%}
        - Website redesign, stronger messaging, clearer calls-to-action, and better technical presentation.
        {% endfor %}

        I would be happy to share a short, practical improvement plan for your website and show how it can support visibility, trust, customer enquiries, and conversion.

        Best regards,
        Oyetoke Adedayo Ebenezer
        Full-Stack Web Developer
        Wireless Computer Services
        Portfolio: https://dayoebe.github.io/
        """
    ).strip()
)


WHATSAPP_TEMPLATE = TEMPLATE_ENV.from_string(
    dedent(
        """
        Hello {{ contact_name }}, my name is Oyetoke Adedayo Ebenezer, a full-stack web developer at Wireless Computer Services.

        I checked {{ business_name }}'s online presence and noticed some areas that can be improved to make the business look more professional, modern, mobile-friendly, and easier for customers to contact.

        I can help with website redesign, SEO setup, WhatsApp/contact integration, speed improvement, and a stronger business presentation online.

        Would you like me to share a short improvement plan for your website?
        """
    ).strip()
)


PROPOSAL_TEMPLATE = TEMPLATE_ENV.from_string(
    dedent(
        """
        # Website/Digital Presence Improvement Proposal

        ## Business
        {{ business_name }}

        ## Industry
        {{ industry_label }}

        ## Website
        {{ website }}

        ## Current opportunity score
        {{ opportunity_score }}/100

        ## Key issues noticed
        {% for issue in issues -%}
        - {{ issue }}
        {% else -%}
        - A deeper review can identify UX, SEO, performance, and conversion improvement opportunities.
        {% endfor %}

        ## Recommended improvements
        {% for rec in recommendations -%}
        - {{ rec }}
        {% else -%}
        - Improve website structure, messaging, responsiveness, technical SEO, and customer enquiry flow.
        {% endfor %}

        ## Suggested service package
        {{ package_name }}

        ## Suggested deliverables
        {% for deliverable in deliverables -%}
        - {{ deliverable }}
        {% endfor %}

        ## Positioning statement
        This project will help {{ business_name }} appear more credible, communicate services clearly, improve customer enquiries, and build stronger trust with visitors.
        """
    ).strip()
)


def clean_rendered_text(value: str) -> str:
    """Normalize template output without destroying intentional paragraph breaks."""
    lines = [line.rstrip() for line in value.splitlines()]
    cleaned_lines: list[str] = []
    previous_blank = False

    for line in lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        cleaned_lines.append(line)
        previous_blank = is_blank

    return "\n".join(cleaned_lines).strip()


def row_get(row: Row, key: str, default: Any = None) -> Any:
    """Read a sqlite row safely, even when a future column is not available yet."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def safe_contact_name(lead: Row) -> str:
    raw_name = row_get(lead, "contact_name")

    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()

    return "there"


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def package_for_industry(industry: str | None) -> tuple[str, list[str]]:
    label = (industry or "Business").strip().lower()

    enterprise_deliverables = [
        "Modern responsive website redesign",
        "Clear service/product pages",
        "SEO title and meta description setup",
        "WhatsApp and contact form integration",
        "Google Analytics and Search Console setup",
        "Speed and image optimization",
        "Security and SSL checks",
        "Basic content refresh and conversion-focused copy",
    ]

    if any(word in label for word in ["saas", "startup", "software", "tech"]):
        return (
            "SaaS Growth & Product Support Package",
            [
                "Landing page improvement",
                "Feature page and pricing page review",
                "Dashboard/UI implementation support",
                "Bug fixing and frontend/backend development support",
                "Documentation and release support",
                "Conversion-focused copy and onboarding improvement",
            ],
        )

    if any(word in label for word in ["hotel", "apartment", "travel", "restaurant", "lounge"]):
        return (
            "Bookings & Customer Enquiry Website Package",
            [
                "Modern homepage redesign",
                "Rooms/menu/services pages",
                "Gallery and testimonials",
                "WhatsApp booking CTA",
                "Google Maps integration",
                "SEO setup for local discovery",
            ],
        )

    if any(word in label for word in ["clinic", "hospital", "pharmacy", "health"]):
        return (
            "Healthcare Trust & Appointment Website Package",
            [
                "Professional healthcare website redesign",
                "Services and specialist pages",
                "Appointment/contact form",
                "WhatsApp quick contact",
                "Trust-building content and testimonials",
                "Local SEO setup",
            ],
        )

    if any(word in label for word in ["real estate", "property"]):
        return (
            "Property Listing & Lead Capture Package",
            [
                "Property listing pages",
                "Lead capture forms",
                "WhatsApp enquiry CTA",
                "Search/filter-ready structure",
                "Gallery and location information",
                "SEO setup for property keywords",
            ],
        )

    return ("Business Website Upgrade Package", enterprise_deliverables)


def build_outreach(lead: Row) -> dict[str, str]:
    business_name = row_get(lead, "business_name") or row_get(lead, "website") or "the business"
    industry_label = row_get(lead, "industry") or "your type of business"
    issues = parse_json_list(row_get(lead, "issues_json"))
    recommendations = parse_json_list(row_get(lead, "recommendations_json"))
    package_name, deliverables = package_for_industry(row_get(lead, "industry"))

    context = {
        "business_name": business_name,
        "contact_name": safe_contact_name(lead),
        "industry_label": industry_label,
        "website": row_get(lead, "website") or "Not provided",
        "opportunity_score": row_get(lead, "opportunity_score") or 0,
        "issues": issues,
        "recommendations": recommendations,
        "package_name": package_name,
        "deliverables": deliverables,
    }

    return {
        "email": clean_rendered_text(EMAIL_TEMPLATE.render(**context)),
        "whatsapp": clean_rendered_text(WHATSAPP_TEMPLATE.render(**context)),
        "proposal": clean_rendered_text(PROPOSAL_TEMPLATE.render(**context)),
    }
