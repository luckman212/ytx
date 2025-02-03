#!/usr/bin/env python3

import os
import sys
import re
import json
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs, urlencode
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

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

@dataclass
class YT_Video:
    video_id: str
    title: Optional[str] = None
    timestamp: Optional[str] = None
    channel: Optional[str] = None
    post_date: Optional[str] = None
    view_count: Optional[int] = None
    duration: Optional[str] = None
    short_url: Optional[str] = None
    markdown_link: Optional[str] = None
    extended_link: Optional[str] = None

    @classmethod
    def from_metadata(cls, metadata: dict, timestamp: Optional[str] = None) -> "YT_Video":
        title=metadata.get("Title")
        title_mdsafe = title.translate(str.maketrans("[]", "()"))
        duration = metadata.get("Duration")
        post_date=metadata.get("Post Date")
        short_url = metadata.get("Short URL")
        if timestamp is not None and short_url:
            short_url += f"?t={timestamp}"
        md_link = f'[{title_mdsafe}]({short_url})'
        md_extended_link = f'[{title_mdsafe} ({duration})]({short_url}) - {post_date}'
        return cls(
            video_id=metadata.get("Video ID"),
            title=title,
            timestamp=timestamp,
            channel=metadata.get("Channel"),
            post_date=post_date,
            view_count=metadata.get("View Count"),
            duration=duration,
            short_url=short_url,
            markdown_link=md_link,
            extended_link=md_extended_link,
        )

def get_clipboard():
    try:
        result = subprocess.run(['pbpaste'],
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

    return {
        "Video ID": vid,
        "Title": title,
        "Channel": chan_title,
        "Post Date": post_date,
        "View Count": view_count,
        "Duration": duration_str,
        "Short URL": short_url,
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

def get_video_info(url):
    try:
        parsed_url = urlparse(url)
    except Exception:
        return None, None
    path = parsed_url.path
    netloc = parsed_url.netloc.lower()
    qs = parse_qs(parsed_url.query)
    timestamp = qs.get("t", [None])[0]
    video_id = None
    if path.startswith("/embed/"):
        video_id = path[len("/embed/"):]
    elif path.startswith("/shorts/"):
        video_id = path[len("/shorts/"):]
    elif "youtu.be" in netloc:
        video_id = path[1:]
    elif "youtube.com" in netloc:
        video_id = qs.get("v", [None])[0]
    return video_id, timestamp

def extract_video_id(items):
    videos = {}
    for item in items:
        video_id, timestamp = get_video_info(item)
        if video_id is None:
            continue
        if timestamp is not None:
            timestamp = timestamp.rstrip("s")
        if video_id not in videos:
            videos[video_id] = YT_Video(video_id=video_id, timestamp=timestamp)
    return list(videos.values())

def update_video_metadata(video: YT_Video) -> YT_Video:
    metadata = get_youtube_metadata(video.video_id)
    if "Error" in metadata:
        return video
    updated_video = YT_Video.from_metadata(metadata, timestamp=video.timestamp)
    return updated_video

def in_alfred() -> bool:
    return os.getenv('alfred_workflow_uid') is not None

def show_usage():
    sys.exit('YouTube metadata fetcher\nusage: %s [-acmx] <urls-or-filenames>' % os.path.basename(__file__))

# obtain YTV3 API key
match os.getenv('YTX_KEY_METHOD'):
    case '1PASSWORD':
        UUID = os.getenv('YTX_OP_UUID')
        API_KEY = get_secret_from_1password(UUID, "credential")
    case 'STATIC':
        API_KEY = os.getenv('YTX_API_KEY')
    case _:
        #if running as CLI
        API_KEY = os.getenv('YTX_API_KEY')

if __name__ == "__main__":
    #print(sys.executable, file=sys.stderr)
    found_urls = []
    results = []
    OUTPUT_MODE = 'plain'
    DEBUG = False
    args = sys.argv[1:]

    if in_alfred():
        OUTPUT_MODE = 'alfred'
        tabs = os.getenv('BROWSER_TABS')
        if tabs:
            tabs_obj = json.loads(tabs)
            found_urls.extend([t["url"] for t in tabs_obj])
        else:
            found_urls.extend(extract_youtube_links(get_clipboard()))

    if not args and OUTPUT_MODE == 'plain':
        show_usage()

    for arg in args:
        if arg in ['-h', '--help']:
            show_usage()
        if arg in ['-c', '--clipboard']:
            found_urls.extend(extract_youtube_links(get_clipboard()))
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
        if arg in ['-d', '--debug']:
            DEBUG = True
            continue
        if os.path.exists(arg):
            found_urls.extend(parse_file(arg))
        else:
            found_urls.append(arg)

    video_list = extract_video_id(found_urls)

    if DEBUG:
        print("found_urls:", found_urls)
        for v in video_list:
            print(f'id: {v.video_id!r}, t={v.timestamp!r}')
        sys.exit()

    for video in video_list:
        updated_video = update_video_metadata(video)
        results.append(updated_video)

    # Filter out entries with errors before sorting
    valid_results = [res for res in results if res.post_date is not None]
    sorted_results = sorted(valid_results, key=lambda x: datetime.strptime(x.post_date, "%Y-%m-%d"), reverse=True)

    match OUTPUT_MODE:
        case 'markdown':
            print("\n".join(f"- {item.markdown_link}" for item in sorted_results if item.markdown_link))
        case 'extended':
            print("\n".join(f"- {item.extended_link}" for item in sorted_results if item.extended_link))
        case 'alfred':
            if sorted_results:
                items = [{
                    "title": f'{item.title} ({item.duration})',
                    "arg": item.short_url,
                    "subtitle": f'{item.post_date}',
                    "mods": { "alt": { "subtitle": item.title }}
                } for item in sorted_results if item.title and item.short_url ]
                items.insert(0, {
                    "title": "Copy all items in Markdown link format",
                    "subtitle": f'({len(items)} videos)',
                    "arg": "\n".join(f"- {item.extended_link}" for item in sorted_results if item.extended_link),
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
            print(json.dumps([asdict(item) for item in results], indent=4))
