# Wireless Bot

Wireless Bot is a local prospecting assistant for finding businesses that may need a new website, a redesign, SEO improvement, or stronger digital presence.

It can discover possible business websites from an industry/location search, audit each website, score the opportunity, store the lead, track follow-up status, and generate practical outreach messages you can send by email, LinkedIn, WhatsApp, or proposal.

Built for Debian/Linux, Python, SQLite, Streamlit, and public GitHub use.

---

## What it can do

- Discover likely business websites from industry, location, and optional keywords
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
- Use a Streamlit GUI dashboard for discovery, scanning, tracking, outreach, importing, and exporting

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
python -m streamlit run dashboard.py
```

The dashboard gives you:

- Lead overview metrics
- Lead discovery by industry/location
- Lead filtering by status, score, and keyword
- Manual website scan form
- Lead status management
- Outreach generator
- Bulk CSV import and scan
- CSV download/export

---

## Discover leads without manually entering websites

Use the dashboard tab:

```text
Discover Leads
```

Enter:

```text
Industry: Hotel
Location: Akure
Extra keywords: booking contact
```

Wireless Bot will search for candidate business websites. You can review the candidates, then click:

```text
Audit and Save These Candidates
```

---

## Quick CLI use

Discover possible websites:

```bash
python -m clienthunter.cli discover "Hotel" --location "Akure" --keywords "booking contact" --limit 10
```

Discover, audit, and save leads automatically:

```bash
python -m clienthunter.cli discover "Hotel" --location "Akure" --keywords "booking contact" --limit 10 --save
```

Audit one website manually:

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
│   ├── discovery.py
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
│   ├── test_database_flow.py
│   └── test_discovery.py
├── dashboard.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Current discovery limitation

The discovery feature uses public web search result pages and filters likely business websites. Results may include false positives, directories, old pages, or irrelevant websites. Always review important leads before outreach.

For a stronger production version, connect a proper search API later.

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
