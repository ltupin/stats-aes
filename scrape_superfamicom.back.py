#!/usr/bin/env python3
"""Scrape superfamicom.org game list and output games released in Japan.

Writes CSV file `superfamicom_japan_games.csv` with one game name per row.
"""
import re
import csv
import time
import urllib.request
from html import unescape

BASE = 'https://superfamicom.org'
LIST_URL = BASE + '/game-list'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8', errors='ignore')

def extract_list_links(html):
    # capture links like <a ... href="/info/slug">Game Name</a>
    pat = re.compile(r'<a[^>]+href="(/info/[^"]+)"[^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
    seen = set()
    out = []
    for m in pat.finditer(html):
        path = m.group(1)
        name_html = m.group(2)
        # strip any inner tags from the link text
        name = re.sub(r'<[^>]+>', '', name_html).strip()
        name = unescape(name)
        if path not in seen:
            seen.add(path)
            out.append((path, name))
    return out

def page_has_japan(html):
    # strip tags and search for Country ... Japan to match structures like
    # <strong>Country</strong> <code>Japan</code>
    text = re.sub(r'<[^>]+>', ' ', html)
    return bool(re.search(r'Country\b.*?Japan\b', text, re.IGNORECASE | re.DOTALL))

def extract_title(html, fallback=None):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return unescape(t)
    return fallback

def main():
    print('Fetching game list pages...')
    links = []
    seen_paths = set()
    page = 1
    while True:
        page_url = LIST_URL if page == 1 else f"{LIST_URL}/{page}"
        try:
            list_html = fetch(page_url)
        except Exception as e:
            print(f'Error fetching list page {page}:', e)
            break
        page_links = extract_list_links(list_html)
        # add only new links
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
    for i, (path, link_name) in enumerate(links, 1):
        url = BASE + path
        try:
            page = fetch(url)
        except Exception as e:
            print(f'Error fetching {url}:', e)
            continue
        if page_has_japan(page):
            title = extract_title(page, fallback=link_name)
            results.append(title)
            print(f'[{i}/{len(links)}] Japan: {title}')
        else:
            print(f'[{i}/{len(links)}] Skip (non-Japan): {link_name}')
        time.sleep(0.15)

    out_file = 'superfamicom_japan_games.csv'
    with open(out_file, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for name in results:
            w.writerow([name])

    print(f'Wrote {len(results)} games to {out_file}')

if __name__ == '__main__':
    main()
