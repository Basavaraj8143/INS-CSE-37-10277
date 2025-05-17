from flask import Flask, request, render_template, send_file, redirect, url_for, flash, Response, jsonify
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import re
import csv
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages
logging.basicConfig(level=logging.INFO)

# Store progress globally (in production, use a proper task queue like Celery)
email_fetch_progress = {'current': 0, 'total': 0}

# Store the path to the latest uploaded websites file for email fetching
latest_websites_file = {'path': None}

def normalize_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def scrape_email(url):
    try:
        emails_found = set()

        # Fetch homepage
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract emails from homepage mailto links
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
        for link in mailto_links:
            email = link['href'].replace('mailto:', '').strip()
            emails_found.add(email)

        # Extract emails from homepage text
        homepage_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.text)
        emails_found.update(homepage_emails)

        # Find all contact-related links with improved pattern matching
        contact_links = set()
        contact_keywords = ['contact', 'about', 'support', 'help', 'info', 'reach', 'connect', 'get-in-touch']
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].lower()
            text = a_tag.get_text().lower()
            
            # Check both href and link text for contact-related keywords
            if any(keyword in href or keyword in text for keyword in contact_keywords):
                if not href.startswith('mailto:'):
                    contact_links.add(href)

        base_url = normalize_url(url)

        # Visit each contact-related page and scrape emails
        for link in contact_links:
            # Construct full URL if relative
            if link.startswith('/'):
                contact_url = base_url + link
            elif link.startswith('http'):
                contact_url = link
            else:
                contact_url = base_url + '/' + link

            try:
                contact_response = requests.get(contact_url, timeout=5)
                contact_soup = BeautifulSoup(contact_response.text, 'html.parser')

                # Look for contact-specific sections
                contact_sections = contact_soup.find_all(['div', 'section'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in contact_keywords))
                
                # Extract emails from contact sections first
                for section in contact_sections:
                    # Emails from mailto links in contact section
                    mailto_links = section.find_all('a', href=re.compile(r'^mailto:', re.I))
                    for link in mailto_links:
                        email = link['href'].replace('mailto:', '').strip()
                        emails_found.add(email)

                    # Emails from raw text in contact section
                    section_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', section.text)
                    emails_found.update(section_emails)

                # If no emails found in specific sections, search the whole page
                if not emails_found:
                    # Emails from mailto links
                    mailto_links = contact_soup.find_all('a', href=re.compile(r'^mailto:', re.I))
                    for link in mailto_links:
                        email = link['href'].replace('mailto:', '').strip()
                        emails_found.add(email)

                    # Emails from raw text
                    contact_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', contact_soup.text)
                    emails_found.update(contact_emails)

            except Exception as e:
                logging.warning(f"Failed to fetch contact page {contact_url}: {e}")

        if emails_found:
            return ', '.join(sorted(emails_found))
        else:
            return "No email found"

    except Exception as e:
        logging.warning(f"Error scraping email from {url}: {e}")
        return "Error scraping email"

def process_url(url, filter_active=False, filter_fast=False):
    try:
        response = requests.get(url, timeout=10)

        if filter_fast and response.elapsed.total_seconds() > 5:
            return {"domain": url, "email": "Excluded (slow loading)", "status": "Excluded"}

        if filter_active and response.status_code != 200:
            return {"domain": url, "email": "Excluded (inactive)", "status": "Excluded"}

        email = scrape_email(url)
        status = "Active" if response.status_code == 200 else f"Status {response.status_code}"

        return {"domain": url, "email": email, "status": status}

    except Exception as e:
        logging.warning(f"Error accessing {url}: {e}")
        return {"domain": url, "email": "Error accessing site", "status": "Error"}

def fetch_websites(query, count):
    """Fetch only website URLs based on search query"""
    raw_urls = list(search(query, num_results=count))
    return [normalize_url(u) for u in raw_urls]

def check_shopify(url):
    """Check if a website is a Shopify store"""
    try:
        response = requests.get(url, timeout=5)
        return 'myshopify.com' in response.text or 'shopify.com' in response.text
    except:
        return False

def check_site_speed(url):
    """Check if site loads within 5 seconds"""
    try:
        response = requests.get(url, timeout=5)
        return response.elapsed.total_seconds() <= 5
    except:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_websites', methods=['POST'])
def fetch_websites_route():
    country = request.form.get('country', '').strip()
    state = request.form.get('state', '').strip()
    keyword = request.form.get('keyword', '').strip()
    count = int(request.form.get('count', 10))

    query = f"{keyword} {state} {country}".strip()
    logging.info(f"Search query: {query} | Count: {count}")

    # Fetch only websites
    websites = fetch_websites(query, count)
    
    # Save to CSV
    with open('websites.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['website'])
        writer.writerows([[url] for url in websites])

    return redirect(url_for('index'))

@app.route('/filter', methods=['POST'])
def filter_websites():
    file = request.files.get('csv_file')
    exclude_file = request.files.get('exclude_file')
    
    if not file:
        flash('No file uploaded')
        return redirect(url_for('index'))

    filter_active = request.form.get('filter_active') == 'on'
    filter_fast = request.form.get('filter_fast') == 'on'
    only_shopify = request.form.get('only_shopify') == 'on'

    # Read excluded websites if provided
    excluded_websites = set()
    if exclude_file and exclude_file.filename:
        exclude_csv = csv.DictReader(io.StringIO(exclude_file.read().decode('utf-8')))
        excluded_websites = set(row['website'] for row in exclude_csv if 'website' in row)

    # Read and filter websites
    csv_reader = csv.DictReader(io.StringIO(file.stream.read().decode('utf-8')))
    filtered_websites = []
    
    for row in csv_reader:
        website = row['website']
        if website in excluded_websites:
            continue
        # If no filters are checked, just add the website
        if not (filter_active or filter_fast or only_shopify):
            filtered_websites.append({'website': website})
            continue
        # Otherwise, apply filters
        if filter_active:
            try:
                response = requests.get(website, timeout=5)
                if response.status_code != 200:
                    continue
            except:
                continue
        if filter_fast and not check_site_speed(website):
            continue
        if only_shopify and not check_shopify(website):
            continue
        filtered_websites.append({'website': website})

    # Prepare filtered CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['website'])
    writer.writeheader()
    writer.writerows(filtered_websites)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=filtered_websites.csv"}
    )

def background_fetch_emails(websites_file_path):
    with open(websites_file_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        websites = [row['website'] for row in csv_reader]

    email_fetch_progress['current'] = 0
    email_fetch_progress['total'] = len(websites)
    results = []
    for website in websites:
        try:
            email = scrape_email(website)
            results.append({'website': website, 'email': email})
        except Exception as e:
            results.append({'website': website, 'email': 'Error fetching email'})
        email_fetch_progress['current'] += 1
    with open('emails.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['website', 'email'])
        writer.writeheader()
        writer.writerows(results)
    # Reset progress after done
    email_fetch_progress['current'] = email_fetch_progress['total']

@app.route('/fetch_emails', methods=['POST'])
def fetch_emails():
    file = request.files.get('websites_csv')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400
    # Save uploaded file to a temp location
    temp_path = 'websites_for_email.csv'
    file.save(temp_path)
    latest_websites_file['path'] = temp_path
    # Start background thread
    thread = threading.Thread(target=background_fetch_emails, args=(temp_path,))
    thread.start()
    return jsonify({'status': 'started'})

@app.route('/fetch_progress')
def fetch_progress():
    if email_fetch_progress['total'] == 0:
        progress = 0
    else:
        progress = (email_fetch_progress['current'] / email_fetch_progress['total']) * 100
    return jsonify({
        'progress': round(progress, 1),
        'status': 'completed' if progress >= 100 else 'processing'
    })

@app.route('/download/<file_type>')
def download_file(file_type):
    if file_type == 'websites':
        return send_file('websites.csv', as_attachment=True)
    elif file_type == 'emails':
        return send_file('emails.csv', as_attachment=True)
    else:
        return 'Invalid file type', 400

if __name__ == '__main__':
    app.run(debug=True)
