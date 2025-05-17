

# 🌐 Web Domain & Email Scraper with Filtering Dashboard

## 🚀 Project Overview

This project is a full-stack web scraping tool that allows users to:
1. *Fetch* websites based on country, city, and industry keywords.
2. *Filter* those websites based on various criteria (active domains, Shopify usage, load speed, and keyword exclusions).
3. *Scrape emails* from the filtered websites.
4. *Download results* from each step as CSV files via an interactive dashboard interface.

---

## 🛠 Features

- 🔍 *Keyword-based Domain Search*
- ✅ *Live Domain Filtering*
- 🛒 *Shopify Platform Detection*
- ⚡ *Fast Load Time Check*
- ✉ *Email Extraction from Webpages*
- 📦 *Downloadable CSVs at Every Step*
- 🎛 *Modern UI Dashboard with Drag & Drop CSV Uploads*

---

## 🖥 Tech Stack

### 🔧 Backend (Python + Flask)
- Flask – API endpoints and routing
- requests – HTTP requests to check live domains and scrape content
- re – Regex for email extraction
- BeautifulSoup (bs4) – HTML parsing
- time – Response time measurement
- csv – Read/write CSV files
- os – File handling

### 💻 Frontend (HTML, CSS, JS)
- Responsive dashboard layout with:
  - Website input panel
  - Filtering panel (with drag-and-drop)
  - Email scraper panel (with drag-and-drop)
  - Results display tab (download buttons + CSV content)

---

## 🧪 How It Works

### 1. *Fetch Websites*
- Enter:
  - Country
  - City Keyword
  - Industry Keyword
  - Result Count
- Submits a request to /fetch
- Returns a CSV (websites.csv) with potential domains

### 2. *Filter Websites*
- Upload websites.csv
- System:
  - Tests for live response
  - Detects Shopify (via script tags or page content)
  - Measures load time
  - Applies exclusion keyword list
- Returns filtered_websites.csv

### 3. *Scrape Emails*
- Upload filtered_websites.csv
- System:
  - Visits homepage and internal links like /contact
  - Extracts emails using regex
- Returns emails.csv with domain + email mapping

### 4. *Result Download*
- Final results displayed in a table
- All CSVs can be downloaded via a dedicated tab

---

## 📁 File Structure

```bash
project/
│
├── app.py                 # Flask backend
├── templates/
│   └── index.html         # Frontend UI
|   |__ result.html
├── static/
│   ├── style.css          # CSS styles
│    
├── websites.csv           # Output from Step 1
├── filtered_websites.csv  # Output from Step 2
├── emails.csv             # Output from Step 3
└── README.md              # You're here!