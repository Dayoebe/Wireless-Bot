# Wireless Bot

Wireless Bot is a local prospecting assistant for finding businesses that may need a new website, a redesign, SEO improvement, or stronger digital presence.

It audits a website, scores the opportunity, stores the lead, and generates a practical outreach message you can send by email, LinkedIn, WhatsApp, or proposal.

Built for Debian/Linux, Python, SQLite, and public GitHub use.

---

## What it can do

- Audit a business website URL
- Detect stale footer years, for example `© 2021`
- Check basic SEO signals
- Check mobile readiness signals
- Check homepage speed response time
- Check sitemap and robots.txt availability
- Detect possible CMS/platform signals such as WordPress, Shopify, Wix, Squarespace, Drupal, Joomla, Laravel hints
- Score each prospect from 0 to 100
- Save leads into SQLite
- Generate outreach messages
- Export leads to CSV
- Bulk scan leads from a CSV file

---

## Ethical use

This tool is designed for responsible prospecting.

Do not spam people.
Do not bypass login pages, paywalls, CAPTCHAs, or blocked resources.
Respect `robots.txt`.
Send personalized, useful messages.
Give businesses a real reason to care.

---

## Debian setup

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

git clone https://github.com/Dayoebe/Wireless-Bot.git
cd Wireless-Bot

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python -m clienthunter.cli initdb
```

---

## Quick use

Audit one website:

```bash
python -m clienthunter.cli scan https://example.com --business-name "Example Business" --industry "Hotel"
```

List saved leads:

```bash
python -m clienthunter.cli leads
```

Export leads:

```bash
python -m clienthunter.cli export
```

Generate pitch for a saved lead:

```bash
python -m clienthunter.cli pitch 1
```

Bulk scan from CSV:

```bash
python -m clienthunter.cli bulk data/sample_leads.csv
```

---

## CSV format

Create a CSV file like this:

```csv
business_name,website,industry,source,contact_email,phone,location
Example Hotel,https://example.com,Hotel,Google Business Profile,hello@example.com,+234000000000,Akure
```

Then run:

```bash
python -m clienthunter.cli bulk data/sample_leads.csv
```

---

## Project structure

```text
Wireless-Bot/
├── clienthunter/
│   ├── auditor.py
│   ├── cli.py
│   ├── database.py
│   ├── exporter.py
│   ├── models.py
│   ├── outreach.py
│   └── utils.py
├── data/
│   └── sample_leads.csv
├── exports/
├── docs/
│   └── prospecting-playbook.md
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Future upgrades

- Search API plugin for finding businesses
- Google Business Profile manual import workflow
- LinkedIn outreach templates
- SaaS founder discovery workflow
- Project manager outreach workflow
- Streamlit dashboard
- FastAPI web app
- Laravel SaaS version
- AI-generated personalized proposals
- Screenshot-based website review
- Website redesign quote generator
