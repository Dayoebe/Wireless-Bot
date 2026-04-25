# Wireless Bot

Wireless Bot is a local prospecting assistant for finding businesses that may need a new website, a redesign, SEO improvement, or stronger digital presence.

It audits a website, scores the opportunity, stores the lead, tracks follow-up status, and generates practical outreach messages you can send by email, LinkedIn, WhatsApp, or proposal.

Built for Debian/Linux, Python, SQLite, Streamlit, and public GitHub use.

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
- Track lead status: `new`, `contacted`, `replied`, `won`, `lost`
- Add internal notes for follow-up
- Generate outreach messages
- Export leads to CSV
- Bulk scan leads from a CSV file
- Use a Streamlit GUI dashboard for scanning, tracking, outreach, importing, and exporting

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

## Launch the GUI dashboard

```bash
streamlit run dashboard.py
```

The dashboard gives you:

- Lead overview metrics
- Lead filtering by status, score, and keyword
- Website scan form
- Lead status management
- Outreach generator
- Bulk CSV import and scan
- CSV download/export

---

## Quick CLI use

Audit one website:

```bash
python -m clienthunter.cli scan https://example.com --business-name "Example Business" --industry "Hotel"
```

Audit and save with status and notes:

```bash
python -m clienthunter.cli scan https://example.com \
  --business-name "Example Business" \
  --industry "Hotel" \
  --status new \
  --notes "Found from Google Business Profile"
```

List saved leads:

```bash
python -m clienthunter.cli leads
```

Update lead status:

```bash
python -m clienthunter.cli status 1 contacted --notes "Sent first WhatsApp message"
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
business_name,website,industry,source,contact_name,contact_email,phone,location,status,notes
Example Hotel,https://example.com,Hotel,Google Business Profile,Manager,hello@example.com,+234000000000,Akure,new,Footer looks outdated
```

Then run:

```bash
python -m clienthunter.cli bulk data/sample_leads.csv
```

Or upload it through the GUI dashboard.

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
├── docs/
│   └── prospecting-playbook.md
├── exports/
├── tests/
│   └── test_database_flow.py
├── dashboard.py
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
- Better dashboard charts and pipeline board
- FastAPI web app
- Laravel SaaS version
- AI-generated personalized proposals
- Screenshot-based website review
- Website redesign quote generator
