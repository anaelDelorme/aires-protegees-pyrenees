#!/usr/bin/env python3
"""Verify that GitHub Pages actually serves the atlas and its required assets."""
import argparse
import json
import hashlib
from pathlib import Path
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def verify(base_url):
    base_url = base_url.rstrip('/') + '/'

    def fetch(path):
        request = Request(urljoin(base_url, path), headers={'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f'{path}: HTTP {response.status}')
            return response.read()

    expected_root = Path(__file__).resolve().parents[1] / 'site'

    def exact(path):
        payload = fetch(path)
        local_path = expected_root / (path or 'index.html')
        if hashlib.sha256(payload).digest() != hashlib.sha256(local_path.read_bytes()).digest():
            raise ValueError(f'{path or 'index.html'}: public content differs from the deployed commit')
        return payload

    html = exact('').decode('utf-8')
    if 'id="map"' not in html or 'app.js' not in html:
        raise ValueError('Pages does not serve the atlas index')
    data = json.loads(exact('data/areas.geojson'))
    if data.get('type') != 'FeatureCollection' or not data.get('features'):
        raise ValueError('Published GeoJSON is missing or empty')
    for asset in ('app.js', 'style.css', 'vendor/leaflet.js', 'vendor/leaflet.css'):
        if not exact(asset):
            raise ValueError(f'Empty asset: {asset}')
    print(f'Public atlas verified: {base_url} ({len(data["features"])} records)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--attempts', type=int, default=12)
    parser.add_argument('--delay', type=float, default=10)
    args = parser.parse_args()
    if args.attempts < 1 or args.delay < 0:
        parser.error('attempts must be positive and delay nonnegative')
    for attempt in range(args.attempts):
        try:
            verify(args.url)
            break
        except Exception as error:
            if attempt == args.attempts - 1:
                raise
            print(f'Publication not ready ({attempt + 1}/{args.attempts}): {error}', flush=True)
            time.sleep(args.delay)
