from __future__ import annotations

import json
from sqlite3 import Row

from jinja2 import Template


EMAIL_TEMPLATE = Template(
    """
Subject: Quick idea to improve {{ business_name }}'s online presence

Hello {{ contact_name | default("there", true) }},

I came across {{ business_name }} and took a quick look at your online presence. I noticed a few areas that can be improved to make the business look more current, trustworthy, and easier for customers to contact.

A few observations:
{% for issue in issues[:5] %}
- {{ issue }}
{% endfor %}

I help businesses build and improve websites that are faster, mobile-friendly, search-friendly, and designed to convert visitors into enquiries.

For {{ industry_label }}, I can help with:
{% for rec in recommendations[:5] %}
- {{ rec }}
{% endfor %}

I would be happy to share a short improvement plan for your website and show how it can help with visibility, trust, and customer conversion.

Best regards,
Oyetoke Adedayo Ebenezer
Full-Stack Web Developer
Wireless Computer Services
Portfolio: https://dayoebe.github.io/
"""
)


WHATSAPP_TEMPLATE = Template(
    """
Hello {{ business_name }}, my name is Oyetoke Adedayo Ebenezer, a full-stack web developer at Wireless Computer Services.

I checked your online presence and noticed some areas that can be improved to make the business look more professional, modern, mobile-friendly, and easier for customers to contact.

I can help with website redesign, SEO setup, WhatsApp/contact integration, speed improvement, and a stronger business presentation online.

Would you like me to share a short improvement plan for your website?
"""
)


PROPOSAL_TEMPLATE = Template(
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
{% for issue in issues %}
- {{ issue }}
{% endfor %}

## Recommended improvements
{% for rec in recommendations %}
- {{ rec }}
{% endfor %}

## Suggested service package
{{ package_name }}

## Suggested deliverables
{% for deliverable in deliverables %}
- {{ deliverable }}
{% endfor %}

## Positioning statement
This project will help {{ business_name }} appear more credible, communicate services clearly, improve customer enquiries, and build stronger trust with visitors.
"""
)


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
    business_name = lead["business_name"] or lead["website"]
    industry_label = lead["industry"] or "your type of business"
    issues = parse_json_list(lead["issues_json"])
    recommendations = parse_json_list(lead["recommendations_json"])
    package_name, deliverables = package_for_industry(lead["industry"])

    context = {
        "business_name": business_name,
        "industry_label": industry_label,
        "website": lead["website"],
        "opportunity_score": lead["opportunity_score"],
        "issues": issues,
        "recommendations": recommendations,
        "package_name": package_name,
        "deliverables": deliverables,
    }

    return {
        "email": EMAIL_TEMPLATE.render(**context).strip(),
        "whatsapp": WHATSAPP_TEMPLATE.render(**context).strip(),
        "proposal": PROPOSAL_TEMPLATE.render(**context).strip(),
    }
