import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "backend" / "sources.json"
OUTPUT_FILE = ROOT / "feed.json"
UA = "gongkao-checkin-feed/1.0"


def clean_html(value: str) -> str:
    value = unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)


def node_text(node, names):
    for name in names:
        hit = node.find(name)
        if hit is not None and hit.text:
            return hit.text
    return ""


def parse_xml(raw: bytes, source: dict) -> List[Dict]:
    root = ET.fromstring(raw)
    rows = []
    for item in root.findall(".//item"):
        title = node_text(item, ["title"])
        link = node_text(item, ["link"])
        summary = clean_html(node_text(item, ["description", "summary", "content"]))
        published = node_text(item, ["pubDate", "published", "updated", "date"])
        date = parse_date(published)
        rows.append(make_row(title, summary, link, date, source))
    for entry in root.findall(".//{*}entry"):
        title = node_text(entry, ["{*}title"])
        summary = clean_html(node_text(entry, ["{*}summary", "{*}content"]))
        published = node_text(entry, ["{*}published", "{*}updated"])
        link = ""
        for link_node in entry.findall("{*}link"):
            if link_node.attrib.get("rel", "alternate") == "alternate":
                link = link_node.attrib.get("href", "")
                break
        rows.append(make_row(title, summary, link, parse_date(published), source))
    return rows


def make_row(title, summary, link, date, source):
    return {"title": clean_html(title), "summary": clean_html(summary)[:240], "source": source["name"], "publishedAt": date.strftime("%Y-%m-%d"), "url": link, "tag": source.get("tag", "申论热点"), "_sort": date.timestamp()}


def parse_html(raw: bytes, source: dict) -> List[Dict]:
    html = raw.decode("utf-8", errors="ignore")
    rows = []
    # Generic extraction for public news listing pages. It intentionally stores
    # title/link/date only, avoiding copying full copyrighted article text.
    pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for href, inner in pattern.findall(html):
        title = clean_html(inner)
        if len(title) < 8 or len(title) > 100 or href.startswith(("#", "javascript:", "mailto:")):
            continue
        link = urljoin(source["url"], href)
        if not link.startswith(("http://", "https://")):
            continue
        if any(x in title for x in ["首页", "登录", "注册", "更多", "导航", "视频", "图片"]):
            continue
        rows.append(make_row(title, "来自官方栏目页的最新标题；打开原文查看完整材料。", link, datetime.now(timezone.utc), source))
    return rows


def relevant(row: dict, source: dict) -> bool:
    keys = source.get("keywords", [])
    if not keys:
        return True
    haystack = f"{row.get('title', '')} {row.get('summary', '')}"
    return any(key in haystack for key in keys)


def main():
    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    rows, errors = [], []
    for source in sources:
        url = source.get("url", "")
        if not url or url.startswith("在这里填写"):
            errors.append(f"未配置：{source.get('name', '未命名来源')}")
            continue
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
            kind = source.get("type", "rss").lower()
            fetched = parse_html(raw, source) if kind == "html" else parse_xml(raw, source)
            rows.extend(row for row in fetched if relevant(row, source) and row.get("title") and row.get("url"))
        except Exception as exc:
            errors.append(f"{source.get('name', '未命名来源')}: {exc}")

    deduped = {row["url"]: row for row in rows}
    items = sorted(deduped.values(), key=lambda row: row["_sort"], reverse=True)[:20]
    for item in items:
        item.pop("_sort", None)
    payload = {"updatedAt": datetime.now(timezone.utc).isoformat(), "items": items, "errors": errors}
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {len(items)} 条内容；{len(errors)} 个来源异常")


if __name__ == "__main__":
    main()
