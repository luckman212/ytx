#!/usr/bin/env python3

import os
import sys
import re
import json
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs, urlencode
from datetime import timedelta, datetime

YOUTUBE_API = "https://www.googleapis.com/youtube/v3/videos"
TIMEOUT = 5
YOUTUBE_RE = re.compile(r"""
(
    https?://                # protocol
    (?:www\.)?               # optional www.
    (?:
        youtube\.com/        # YouTube domain
        (?:
            watch\?v=|       # watch URL
            embed/|          # embed URL
            shorts/          # shorts URL
        )
        [\w-]+               # video ID
        (?:[&?]\S*)?         # optional params
    |
        youtu\.be/           # shortened domain
        [\w-]+               # video ID
        (?:\?\S*)?           # optional params
    )
)
""", re.VERBOSE)

def get_clipboard():
    try:
        result = subprocess.run(['/usr/bin/pbpaste'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""

def get_secret_from_1password(identifier, field_label):
    try:
        proc = subprocess.run(
            ["op", "item", "get", identifier, "--format", "json"],
            check=True,
            capture_output=True,
            text=True
        )
        item = json.loads(proc.stdout)
        for field in item.get("fields", []):
            if field.get("label") == field_label:
                return field.get("value")
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving 1Password item: {e}", file=sys.stderr)
    return None

def check_apikey():
    if API_KEY:
        return
    if in_alfred():
        json_output = { "items": [{
            "title": "API key missing or invalid. Check workflow configuration!",
            "icon": { "path": "api-err.png" },
            "valid": False
        }]}
        print(json.dumps(json_output, indent=4))
    else:
        print("API key missing or invalid (export 'YTX_API_KEY' before running)", file=sys.stderr)
    sys.exit()

def extract_youtube_links(text):
    return list(set(YOUTUBE_RE.findall(text))) if text else []

def get_youtube_metadata(video_id):
    check_apikey()
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "key": API_KEY,
    }
    url = YOUTUBE_API + "?" + urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            status_code = response.getcode()
            if status_code != 200:
                return {"Error": f"API request failed with status {status_code}"}
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"Error": f"HTTP error: {e.code} {e.reason}"}
    except urllib.error.URLError as e:
        return {"Error": f"Network error: {e.reason}"}
    except Exception as e:
        return {"Error": f"Unexpected error: {e}"}
    
    if "items" not in data or not data["items"]:
        return {"Error": f"Invalid video ID: {video_id}"}

    #print(json.dumps(data, indent=4))
    video_data = data["items"][0]
    
    vid = video_data["id"]
    title = video_data["snippet"]["title"]
    chan_title = video_data["snippet"]["channelTitle"]
    post_date = video_data["snippet"]["publishedAt"].split("T")[0]
    view_count = int(video_data["statistics"]["viewCount"])
    duration = video_data["contentDetails"]["duration"]

    # Convert duration from ISO 8601 to HH:MM:SS
    duration_seconds = parse_iso8601_duration(duration)
    duration_str = format_duration(duration_seconds)

    short_url = f'https://youtu.be/{vid}'
    md_link = f'[{title}]({short_url})'
    md_extended_link = f'[{title} ({duration_str})]({short_url}) - {post_date}'

    return {
        "Video ID": vid,
        "Title": title,
        "Channel": chan_title,
        "Post Date": post_date,
        "View Count": view_count,
        "Video Length": duration_str,
        "Short URL": short_url,
        "Markdown Link": md_link,
        "Extended Link": md_extended_link,
    }

def parse_iso8601_duration(duration):
    match = re.match(r'PT(\d+H)?(\d+M)?(\d+S)?', duration)
    if not match:
        return 0
    hours = int(match.group(1)[:-1]) if match.group(1) else 0
    minutes = int(match.group(2)[:-1]) if match.group(2) else 0
    seconds = int(match.group(3)[:-1]) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds

def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"

def parse_file(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return extract_youtube_links(file.read())
    except:
        return []

def extract_video_id(items):
    def get_video_id(url):
        try:
            parsed_url = urlparse(url)
        except Exception:
            return None
        path = parsed_url.path
        netloc = parsed_url.netloc.lower()
        if path.startswith("/embed/"):
            return path[len("/embed/"):]
        elif path.startswith("/shorts/"):
            return path[len("/shorts/"):]
        elif "youtu.be" in netloc:
            return path[1:]
        elif "youtube.com" in netloc:
            qs = parse_qs(parsed_url.query)
            return qs.get("v", [None])[0]
        return None
    return list({vid for item in items if (vid := get_video_id(item)) is not None})

def in_alfred() -> bool:
    return os.getenv('alfred_workflow_uid') is not None

def show_usage():
    sys.exit('YouTube metadata fetcher\nusage: %s [-acmx] <urls-or-filenames>' % os.path.basename(__file__))

# obtain YTV3 API key
match os.environ.get('YTX_KEY_METHOD'):
    case '1PASSWORD':
        UUID = os.environ.get('YTX_OP_UUID')
        API_KEY = get_secret_from_1password(UUID, "credential")
    case 'STATIC':
        API_KEY = os.environ.get('YTX_API_KEY')
    case _:
        #if running as CLI
        API_KEY = os.environ.get('YTX_API_KEY')

if __name__ == "__main__":
    #print(sys.executable, file=sys.stderr)
    parsed_args = []
    results = []
    OUTPUT_MODE = 'plain'
    DEBUG = False
    args = sys.argv[1:]

    if in_alfred():
        OUTPUT_MODE = 'alfred'
        parsed_args.extend(extract_youtube_links(get_clipboard()))

    if not args and OUTPUT_MODE == 'plain':
        show_usage()

    for arg in args:
        if arg in ['-h', '--help']:
            show_usage()
        if arg in ['-c', '--clipboard']:
            parsed_args.extend(extract_youtube_links(get_clipboard()))
            continue
        if arg in ['-a', '--alfred']:
            OUTPUT_MODE = 'alfred'
            continue
        if arg in ['-m', '--markdown']:
            OUTPUT_MODE = 'markdown'
            continue
        if arg in ['-x', '--extended']:
            OUTPUT_MODE = 'extended'
            continue
        if arg in ['--debug']:
            DEBUG = True
            continue
        if os.path.exists(arg):
            parsed_args.extend(parse_file(arg))
        else:
            parsed_args.append(arg)

    video_ids = extract_video_id(parsed_args)

    if DEBUG:
        print("parsed_args:", parsed_args)
        print("video_ids:", video_ids)
        sys.exit()

    for video_id in video_ids:
        metadata = get_youtube_metadata(video_id)
        results.append(metadata)

    # Filter out entries with errors before sorting
    valid_results = [res for res in results if "Post Date" in res]
    sorted_results = sorted(valid_results, key=lambda x: datetime.strptime(x["Post Date"], "%Y-%m-%d"), reverse=True)

    match OUTPUT_MODE:
        case 'markdown':
            print("\n".join(f"- {item['Markdown Link']}" for item in sorted_results if 'Markdown Link' in item))
        case 'extended':
            print("\n".join(f"- {item['Extended Link']}" for item in sorted_results if 'Extended Link' in item))
        case 'alfred':
            if sorted_results:
                items = [{
                    "title": f'{item["Title"]} ({item["Video Length"]})',
                    "arg": item["Short URL"],
                    "subtitle": f'{item["Post Date"]}',
                    "mods": { "alt": { "subtitle": item["Title"] }}
                } for item in sorted_results if "Title" in item and "Short URL" in item ]
                items.insert(0, {
                    "title": "Copy all items in Markdown link format",
                    "subtitle": f'({len(items)} videos)',
                    "arg": "\n".join(f"- {item['Extended Link']}" for item in sorted_results if 'Extended Link' in item),
                    "mods": { "alt": {
                        "subtitle": "edit results in TextView",
                        "variables": { "action": "textview" }
                    }},
                    "icon": { "path": "copy-as-markdown.png" },
                    "variables": { "action": "copy" },
                    "quicklookurl": None
                })
                json_output = { "items": items }
            else:
                json_output = { "items": [{
                    "title": "No results from the current clipboard contents!",
                    "valid": False
                }]}
            print(json.dumps(json_output, indent=4))
        case _:
            print(json.dumps(results, indent=4))
