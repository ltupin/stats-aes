#!/usr/bin/env python3
"""Scrape superfamicom.org game list and export enriched Japan-only game data.

Writes a CSV file with columns:
english_title,japanese_title,producer,serial,date,category
"""
import csv
import re
import time
import urllib.request
from html import unescape

BASE = 'https://superfamicom.org'
LIST_URL = BASE + '/game-list'
OUT_FILE = 'superfamicom_japan_games.csv'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='ignore')


def clean_text(value):
    text = re.sub(r'<[^>]+>', ' ', value or '')
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_list_links(html):
    pat = re.compile(r'<a[^>]+href="(/info/[^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
    seen = set()
    out = []
    for m in pat.finditer(html):
        path = m.group(1)
        name_html = m.group(2)
        name = clean_text(name_html)
        if path not in seen:
            seen.add(path)
            out.append((path, name))
    return out


def page_has_japan(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    return bool(re.search(r'Country\b.*?Japan\b', text, re.IGNORECASE | re.DOTALL))


def extract_title(html, fallback=None):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return clean_text(m.group(1)) or fallback
    return fallback


def extract_japanese_title(html):
    matches = re.findall(r'<h3[^>]*class=["\'][^"\']*original[^"\']*["\'][^>]*>(.*?)</h3>', html, re.DOTALL | re.IGNORECASE)
    parts = []
    for block in matches:
        for line in re.split(r'<br\s*/?>', block, flags=re.IGNORECASE):
            text = clean_text(line)
            if text:
                parts.append(text)
    if len(parts) >= 2:
        return parts[1]
    if parts:
        return parts[0]
    return ''


def extract_producer(html):
    m = re.search(r'<h3[^>]*class=["\']producer["\'][^>]*>(.*?)</h3>', html, re.DOTALL | re.IGNORECASE)
    return clean_text(m.group(1)) if m else ''


def extract_serial(html):
    m = re.search(r'<h3[^>]*class=["\']serial["\'][^>]*>(.*?)</h3>', html, re.DOTALL | re.IGNORECASE)
    return clean_text(m.group(1)) if m else ''


def extract_dates_and_category(html):
    matches = re.findall(r'<h4[^>]*class=["\']date["\'][^>]*>(.*?)</h4>', html, re.DOTALL | re.IGNORECASE)
    values = [clean_text(m) for m in matches if clean_text(m)]
    if not values:
        return '', ''
    date_value = values[0]
    category = values[1] if len(values) > 1 else ''
    return date_value, category


def main():
    print('Fetching game list pages...')
    links = []
    seen_paths = set()
    page = 1
    while True:
        page_url = LIST_URL if page == 1 else f'{LIST_URL}/{page}'
        try:
            list_html = fetch(page_url)
        except Exception as exc:
            print(f'Error fetching list page {page}: {exc}')
            break
        page_links = extract_list_links(list_html)
        new = 0
        for path, name in page_links:
            if path not in seen_paths:
                seen_paths.add(path)
                links.append((path, name))
                new += 1
        print(f'Page {page}: found {len(page_links)} links, {new} new')
        if new == 0:
            break
        page += 1
        time.sleep(0.15)
    print(f'Total candidate links: {len(links)}')

    results = []
    for idx, (path, link_name) in enumerate(links, 1):
        url = BASE + path
        try:
            page_html = fetch(url)
        except Exception as exc:
            print(f'Error fetching {url}: {exc}')
            continue
        if not page_has_japan(page_html):
            continue

        title = extract_title(page_html, fallback=link_name)
        japanese_title = extract_japanese_title(page_html)
        producer = extract_producer(page_html)
        serial = extract_serial(page_html)
        date_value, category = extract_dates_and_category(page_html)
        results.append([title, japanese_title, producer, serial, date_value, category])

        if idx % 100 == 0 or idx == len(links):
            print(f'Processed {idx}/{len(links)} pages')
        time.sleep(0.15)

    with open(OUT_FILE, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['english_title', 'japanese_title', 'producer', 'serial', 'date', 'category'])
        writer.writerows(results)

    print(f'Wrote {len(results)} rows to {OUT_FILE}')


if __name__ == '__main__':
    main()
