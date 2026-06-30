#!/usr/bin/env python3

import sys
import json
import csv
import re
import ssl
import time
import signal
import asyncio
import argparse
import urllib.parse
from collections import defaultdict

import aiohttp
from bs4 import BeautifulSoup, Comment


# ─── Colors ──────────────────────────────────────────────────────────────────

class C:
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


# ─── Secret patterns ─────────────────────────────────────────────────────────

SECRET_PATTERNS = {
    "AWS Access Key":     r'AKIA[0-9A-Z]{16}',
    "AWS Secret Key":     r'(?i)aws[_\-]?secret[_\-]?(?:access[_\-]?)?key[\s"\']*[:=][\s"\']*[A-Za-z0-9+/]{40}',
    "Generic API Key":    r'(?i)(api[_\-]?key|apikey)[\s"\']*[:=][\s"\']*[A-Za-z0-9_\-]{20,}',
    "Bearer Token":       r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
    "Private Key":        r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
    "Hardcoded Password": r'(?i)(?:password|passwd|pwd)[\s"\']*[:=][\s"\']*["\'][^"\']{4,}["\']',
    "GitHub Token":       r'gh[pousr]_[A-Za-z0-9]{36}',
    "Slack Token":        r'xox[baprs]-[0-9A-Za-z\-]{10,48}',
    "Google API Key":     r'AIza[0-9A-Za-z\-_]{35}',
    "JWT":                r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
    "Email Address":      r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    "Internal IPv4":      r'\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b',
}


# ─── Tech fingerprints ───────────────────────────────────────────────────────

TECH_FINGERPRINTS = {
    "WordPress":    {"html": [r'wp-content/', r'wp-includes/', r'/wp-json/'],   "headers": [],                                   "cookies": []},
    "Drupal":       {"html": [r'Drupal\.settings', r'/sites/default/files/'],   "headers": [r'X-Generator.*Drupal'],             "cookies": []},
    "Joomla":       {"html": [r'/components/com_', r'Joomla'],                  "headers": [],                                   "cookies": []},
    "Laravel":      {"html": [],                                                 "headers": [],                                   "cookies": [r'laravel_session', r'XSRF-TOKEN']},
    "Django":       {"html": [],                                                 "headers": [],                                   "cookies": [r'csrftoken', r'sessionid']},
    "ASP.NET":      {"html": [r'__VIEWSTATE', r'__EVENTVALIDATION'],            "headers": [r'X-AspNet-Version', r'X-Powered-By.*ASP\.NET'], "cookies": [r'ASP\.NET_SessionId']},
    "PHP":          {"html": [],                                                 "headers": [r'X-Powered-By.*PHP'],               "cookies": [r'PHPSESSID']},
    "Next.js":      {"html": [r'__NEXT_DATA__', r'/_next/static/'],             "headers": [],                                   "cookies": []},
    "Nuxt.js":      {"html": [r'__NUXT__', r'/_nuxt/'],                         "headers": [],                                   "cookies": []},
    "React":        {"html": [r'data-reactroot', r'_reactFiber', r'__REACT_DEVTOOLS'], "headers": [],                           "cookies": []},
    "Vue.js":       {"html": [r'__vue__', r'data-v-[a-f0-9]'],                  "headers": [],                                   "cookies": []},
    "Angular":      {"html": [r'ng-version=', r'_nghost', r'ng-app'],           "headers": [],                                   "cookies": []},
    "jQuery":       {"html": [r'jquery[\.\-](?:\d|min)'],                       "headers": [],                                   "cookies": []},
    "Bootstrap":    {"html": [r'bootstrap(?:\.min)?\.(?:js|css)'],              "headers": [],                                   "cookies": []},
    "Ruby/Rails":   {"html": [r'csrf-token', r'authenticity_token'],            "headers": [],                                   "cookies": [r'_session_id']},
    "Cloudflare":   {"html": [],                                                 "headers": [r'CF-Ray', r'Server.*cloudflare'],   "cookies": [r'__cf_bm', r'cf_clearance']},
    "nginx":        {"html": [],                                                 "headers": [r'Server.*nginx'],                   "cookies": []},
    "Apache":       {"html": [],                                                 "headers": [r'Server.*Apache'],                  "cookies": []},
    "IIS":          {"html": [],                                                 "headers": [r'Server.*Microsoft-IIS'],           "cookies": []},
}


# ─── Banner ──────────────────────────────────────────────────────────────────

def display_banner():
    print(f"""{C.RED}
________                        ____
`MMMMMMM 68b                   6MMMMb
 MM     Y89                  6M'    `
 MM      ___ ___  __   ____   MM         ____  ___  __    ___  __ ____
 MM   ,  `MM `MM 6MM  6MMMMb  YM.       6MMMMb.`MM 6MM  6MMMMb `M6MMMMb
 MMMMMM   MM  MM69 " 6M'  `Mb  YMMMMb  6M'   Mb MM69 " 8M'  `Mb MM'  `Mb
 MM   `   MM  MM'    MM    MM      `Mb MM    `' MM'        ,oMM MM    MM
 MM       MM  MM     MMMMMMMM       MM MM       MM     ,6MM9'MM MM    MM
 MM       MM  MM     MM             MM MM       MM     MM'   MM MM    MM
 MM       MM  MM     YM    d9 L    ,M9 YM.   d9 MM     MM.  ,MM MM.  ,M9
_MM_     _MM__MM_     YMMMM9  MYMMMM9   YMMMM9 _MM_    `YMMM9'YbMMYMMM9
{C.RESET}
                   {C.BOLD}FireScrap{C.RESET} — Web Scraping Made Easy
""")


def bye(sig, frame):
    print(f"\n{C.YELLOW}[!] Interrupted.{C.RESET}")
    sys.exit(0)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def resolve_url(href: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def same_domain(url: str, base_url: str) -> bool:
    try:
        return urllib.parse.urlparse(url).netloc == urllib.parse.urlparse(base_url).netloc
    except Exception:
        return False


def print_section(title: str, data, color=C.CYAN):
    print(f"\n{color}{C.BOLD}[{title}]{C.RESET}")
    print(f"{C.DIM}{'─' * 60}{C.RESET}")
    if isinstance(data, list):
        for item in data:
            print(f"  {item}")
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"  {C.BOLD}{k}:{C.RESET} {v}")
    else:
        print(f"  {data}")


def load_urls_from_file(file_path: str) -> list:
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"{C.RED}[!] File not found: {file_path}{C.RESET}")
        sys.exit(1)
    except OSError as e:
        print(f"{C.RED}[!] Error reading file: {e}{C.RESET}")
        sys.exit(1)


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def build_ssl_context(no_verify: bool):
    if no_verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return True


def build_headers(args) -> dict:
    headers = {
        "User-Agent": args.user_agent,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for h in args.header:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers


async def fetch_url(url: str, session: aiohttp.ClientSession, args) -> tuple:
    try:
        start = time.time()
        kwargs = {"allow_redirects": True, "timeout": aiohttp.ClientTimeout(total=args.timeout)}
        if args.proxy:
            kwargs["proxy"] = args.proxy

        async with session.get(url, **kwargs) as resp:
            elapsed = round(time.time() - start, 3)

            if resp.status >= 400:
                print(f"  {C.RED}[!] HTTP {resp.status}: {url}{C.RESET}")
                return None, {}, {}, [], ""

            text = await resp.text(errors="replace")
            soup = BeautifulSoup(text, "lxml")

            meta = {
                "url": str(resp.url),
                "status_code": resp.status,
                "response_time_s": elapsed,
                "content_type": resp.headers.get("Content-Type", ""),
                "server": resp.headers.get("Server", ""),
                "x_powered_by": resp.headers.get("X-Powered-By", ""),
            }

            raw_headers = dict(resp.headers)
            set_cookie_headers = resp.headers.getall("Set-Cookie", [])

            if args.verbose:
                print(f"  {C.DIM}[{resp.status}] {elapsed}s | {meta['server']}{C.RESET}")

            return soup, meta, raw_headers, set_cookie_headers, text

    except aiohttp.ClientSSLError as e:
        print(f"  {C.RED}[!] SSL error (try --no-verify): {e}{C.RESET}")
    except aiohttp.ClientError as e:
        print(f"  {C.RED}[!] Connection error: {e}{C.RESET}")
    except asyncio.TimeoutError:
        print(f"  {C.RED}[!] Timeout: {url}{C.RESET}")
    except Exception as e:
        print(f"  {C.RED}[!] Unexpected error: {e}{C.RESET}")

    return None, {}, {}, [], ""


# ─── Extractors ───────────────────────────────────────────────────────────────

def extract_all(soup: BeautifulSoup, base_url: str) -> dict:
    links = list(dict.fromkeys(
        resolve_url(a["href"], base_url)
        for a in soup.find_all("a", href=True)
        if not a["href"].startswith(("javascript:", "mailto:", "#"))
    ))

    images = list(dict.fromkeys(
        resolve_url(img["src"], base_url)
        for img in soup.find_all("img", src=True)
    ))

    js_files = list(dict.fromkeys(
        resolve_url(s["src"], base_url)
        for s in soup.find_all("script", src=True)
    ))

    forms = [
        {
            "action": resolve_url(form.get("action") or "", base_url),
            "method": form.get("method", "get").upper(),
            "inputs": [
                {
                    "name":  inp.get("name", ""),
                    "type":  inp.get("type", "text"),
                    "value": inp.get("value", ""),
                }
                for inp in form.find_all("input")
            ],
            "textareas": [ta.get("name", "") for ta in form.find_all("textarea")],
            "selects":   [sel.get("name", "") for sel in form.find_all("select")],
        }
        for form in soup.find_all("form")
    ]

    comments = [
        str(c).strip()
        for c in soup.find_all(string=lambda t: isinstance(t, Comment))
        if str(c).strip()
    ]

    meta_tags = {
        (tag.get("name") or tag.get("property", "")): tag.get("content", "")
        for tag in soup.find_all("meta")
        if tag.get("name") or tag.get("property")
    }

    tables = [
        [
            [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
            for row in table.find_all("tr")
        ]
        for table in soup.find_all("table")
    ]

    headings = {
        f"h{i}": [h.get_text(strip=True) for h in soup.find_all(f"h{i}")]
        for i in range(1, 7)
    }

    return {
        "title":     soup.title.string.strip() if soup.title and soup.title.string else "No Title",
        "links":     links,
        "images":    images,
        "js_files":  js_files,
        "headings":  headings,
        "tables":    tables,
        "forms":     forms,
        "comments":  comments,
        "meta_tags": meta_tags,
    }


def scan_secrets(raw_html: str) -> list:
    findings = []
    for name, pattern in SECRET_PATTERNS.items():
        for match in set(re.findall(pattern, raw_html)):
            val = match if isinstance(match, str) else match[0]
            findings.append({"type": name, "value": val[:120]})
    return findings


def fingerprint_tech(raw_html: str, raw_headers: dict, cookie_headers: list) -> list:
    headers_str = " ".join(f"{k}: {v}" for k, v in raw_headers.items())
    cookies_str = " ".join(cookie_headers)
    detected = []

    for tech, patterns in TECH_FINGERPRINTS.items():
        matched = any(re.search(p, raw_html, re.IGNORECASE) for p in patterns["html"])
        if not matched:
            matched = any(re.search(p, headers_str, re.IGNORECASE) for p in patterns["headers"])
        if not matched:
            matched = any(re.search(p, cookies_str, re.IGNORECASE) for p in patterns["cookies"])
        if matched:
            detected.append(tech)

    return detected


def analyze_cookies(cookie_headers: list) -> list:
    results = []
    for header in cookie_headers:
        parts = [p.strip() for p in header.split(";")]
        name_value = parts[0].split("=", 1)
        if len(name_value) < 1:
            continue
        name = name_value[0].strip()
        attrs = [p.lower() for p in parts[1:]]

        secure   = any(a == "secure" for a in attrs)
        httponly = any(a == "httponly" for a in attrs)
        samesite = next((a.split("=", 1)[1] for a in attrs if a.startswith("samesite=")), "")

        issues = []
        if not secure:   issues.append("missing Secure")
        if not httponly: issues.append("missing HttpOnly")
        if not samesite: issues.append("missing SameSite")

        results.append({
            "name":     name,
            "secure":   secure,
            "httponly": httponly,
            "samesite": samesite,
            "issues":   issues,
        })
    return results


async def fetch_robots(base_url: str, session: aiohttp.ClientSession, args) -> dict:
    parsed = urllib.parse.urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    result = {}

    for path in ["/robots.txt", "/sitemap.xml"]:
        url = root + path
        try:
            kwargs = {"timeout": aiohttp.ClientTimeout(total=args.timeout)}
            if args.proxy:
                kwargs["proxy"] = args.proxy
            async with session.get(url, **kwargs) as resp:
                if resp.status == 200:
                    result[path] = await resp.text(errors="replace")
        except Exception:
            pass

    return result


# ─── Core scraper ─────────────────────────────────────────────────────────────

async def scrape_url(url: str, session: aiohttp.ClientSession, args, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        print(f"\n{C.GREEN}[*]{C.RESET} {C.BOLD}{url}{C.RESET}")

        soup, meta, raw_headers, cookie_headers, raw_html = await fetch_url(url, session, args)
        if soup is None:
            return None

        base_url = meta.get("url", url)
        data = extract_all(soup, base_url)
        entry = {"url": url, "metadata": meta, "data": {}}

        if args.links or args.all_info:
            print_section("Links", data["links"])
            entry["data"]["links"] = data["links"]

        if args.images or args.all_info:
            print_section("Images", data["images"])
            entry["data"]["images"] = data["images"]

        if args.js or args.all_info:
            print_section("JavaScript Files", data["js_files"])
            entry["data"]["js_files"] = data["js_files"]

        if args.tables or args.all_info:
            print_section("Tables", data["tables"])
            entry["data"]["tables"] = data["tables"]

        if args.headers or args.all_info:
            flat = [h for level in data["headings"].values() for h in level]
            print_section("Headings", flat)
            entry["data"]["headings"] = data["headings"]

        if args.forms or args.all_info:
            print_section("Forms", data["forms"])
            entry["data"]["forms"] = data["forms"]

        if args.comments or args.all_info:
            print_section("HTML Comments", data["comments"])
            entry["data"]["comments"] = data["comments"]

        if args.meta_tags or args.all_info:
            print_section("Meta Tags", data["meta_tags"])
            entry["data"]["meta_tags"] = data["meta_tags"]

        if args.secrets or args.all_info:
            secrets = scan_secrets(raw_html)
            if secrets:
                print_section(
                    "Possible Secrets",
                    [f"{C.RED}{s['type']}{C.RESET}: {s['value']}" for s in secrets],
                    C.RED,
                )
            else:
                print(f"\n{C.DIM}  [secrets] Nothing found.{C.RESET}")
            entry["data"]["secrets"] = secrets

        if args.fingerprint or args.all_info:
            techs = fingerprint_tech(raw_html, raw_headers, cookie_headers)
            print_section("Tech Stack", techs if techs else ["Nothing detected"], C.MAGENTA)
            entry["data"]["tech_stack"] = techs

        if args.cookies or args.all_info:
            cookie_info = analyze_cookies(cookie_headers)
            print_section("Cookie Security", [], C.YELLOW)
            if cookie_info:
                for c in cookie_info:
                    issues_str = (
                        ", ".join(f"{C.RED}{i}{C.RESET}" for i in c["issues"])
                        if c["issues"] else f"{C.GREEN}OK{C.RESET}"
                    )
                    print(f"  {C.BOLD}{c['name']}{C.RESET} → {issues_str}")
            else:
                print(f"  {C.DIM}No cookies set.{C.RESET}")
            entry["data"]["cookies"] = cookie_info

        if args.robots or args.all_info:
            robots_data = await fetch_robots(base_url, session, args)
            for path, content in robots_data.items():
                preview = content[:600] + ("..." if len(content) > 600 else "")
                print_section(path, preview)
            entry["data"]["robots"] = robots_data

        if args.verbose:
            print_section("Response Metadata", meta)

        return entry


# ─── Spider mode ─────────────────────────────────────────────────────────────

async def spider(start_url: str, session: aiohttp.ClientSession, args, semaphore: asyncio.Semaphore) -> list:
    visited: set = set()
    results: list = []
    current_level = [start_url]

    for depth in range(args.depth + 1):
        if not current_level:
            break

        print(f"\n{C.MAGENTA}{C.BOLD}[spider] depth={depth} — {len(current_level)} URL(s){C.RESET}")

        tasks = [
            scrape_url(url, session, args, semaphore)
            for url in current_level
            if url not in visited
        ]
        visited.update(current_level)

        level_results = await asyncio.gather(*tasks)
        next_level = []

        for entry in level_results:
            if not entry:
                continue
            results.append(entry)
            if depth < args.depth:
                for link in entry.get("data", {}).get("links", []):
                    if (
                        link not in visited
                        and same_domain(link, start_url)
                        and link.startswith("http")
                    ):
                        next_level.append(link)

        current_level = list(dict.fromkeys(next_level))

    return results


# ─── Output ──────────────────────────────────────────────────────────────────

def print_summary(results: list):
    totals: dict = defaultdict(int)
    secret_count = 0
    techs: set = set()

    for r in results:
        d = r.get("data", {})
        totals["links"]    += len(d.get("links", []))
        totals["images"]   += len(d.get("images", []))
        totals["js_files"] += len(d.get("js_files", []))
        totals["forms"]    += len(d.get("forms", []))
        totals["comments"] += len(d.get("comments", []))
        secret_count       += len(d.get("secrets", []))
        techs.update(d.get("tech_stack", []))

    print(f"\n{C.BOLD}{'═' * 60}{C.RESET}")
    print(f"{C.BOLD}  SUMMARY  —  {len(results)} URL(s) scraped{C.RESET}")
    print(f"{C.BOLD}{'═' * 60}{C.RESET}")
    for key, count in totals.items():
        if count:
            print(f"  {key:<12} {count}")
    if secret_count:
        print(f"  {'secrets':<12} {C.RED}{C.BOLD}{secret_count} ← review these{C.RESET}")
    if techs:
        print(f"  {'tech stack':<12} {', '.join(sorted(techs))}")
    print()


def save_output(file_path: str, data: list, fmt: str):
    try:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            if fmt == "json":
                json.dump(data, f, indent=2, ensure_ascii=False)

            elif fmt == "csv":
                writer = csv.writer(f)
                writer.writerow(["source_url", "type", "value"])
                for entry in data:
                    url = entry["url"]
                    d = entry.get("data", {})
                    for link in d.get("links", []):
                        writer.writerow([url, "link", link])
                    for img in d.get("images", []):
                        writer.writerow([url, "image", img])
                    for js in d.get("js_files", []):
                        writer.writerow([url, "js_file", js])
                    for s in d.get("secrets", []):
                        writer.writerow([url, f"secret:{s['type']}", s["value"]])

            else:  # txt
                for entry in data:
                    f.write(f"URL: {entry['url']}\n")
                    f.write(json.dumps(entry["data"], indent=2, ensure_ascii=False))
                    f.write("\n" + "─" * 60 + "\n")

        print(f"{C.GREEN}[+]{C.RESET} Saved to '{file_path}' ({fmt})")
    except OSError as e:
        print(f"{C.RED}[!] Error saving output: {e}{C.RESET}")


# ─── Entry point ─────────────────────────────────────────────────────────────

async def main_async(args):
    ssl_ctx = build_ssl_context(args.no_verify)
    connector = aiohttp.TCPConnector(ssl=ssl_ctx, limit=args.concurrency * 2)
    headers = build_headers(args)

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        semaphore = asyncio.Semaphore(args.concurrency)
        all_results = []

        if args.spider:
            all_results = await spider(args.url, session, args, semaphore)
        else:
            urls = load_urls_from_file(args.archive) if args.archive else [args.url]
            tasks = [scrape_url(url, session, args, semaphore) for url in urls]
            all_results = [r for r in await asyncio.gather(*tasks) if r]

        print_summary(all_results)

        if args.output:
            save_output(args.output, all_results, args.fmt)


def main():
    signal.signal(signal.SIGINT, bye)
    display_banner()

    parser = argparse.ArgumentParser(
        prog="fireScrap.py",
        usage="%(prog)s [url] [options]",
        description="Async web scraping & recon tool.",
        epilog=(
            "examples:\n"
            "  fireScrap.py https://target.com -l -i --secrets --fp\n"
            "  fireScrap.py -a urls.txt -ai --proxy http://127.0.0.1:8080\n"
            "  fireScrap.py https://target.com --spider --depth 2 -l -js\n"
            "  fireScrap.py https://target.com -f -c --cookies --no-verify -v\n"
            "  fireScrap.py https://target.com --robots -o results.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("url",       nargs="?", help="Target URL.")
    parser.add_argument("-a", "--archive", metavar="FILE", help="File with list of URLs (one per line).")

    extract = parser.add_argument_group("extraction")
    extract.add_argument("-l",  "--links",      action="store_true", help="Extract all links.")
    extract.add_argument("-i",  "--images",     action="store_true", help="Extract all images.")
    extract.add_argument("-js", "--js",         action="store_true", help="Extract JavaScript files.")
    extract.add_argument("-t",  "--tables",     action="store_true", help="Extract tables.")
    extract.add_argument("-he", "--headers",    action="store_true", help="Extract headings (h1-h6).")
    extract.add_argument("-f",  "--forms",      action="store_true", help="Extract forms and inputs.")
    extract.add_argument("-c",  "--comments",   action="store_true", help="Extract HTML comments.")
    extract.add_argument("-m",  "--meta-tags",  action="store_true", dest="meta_tags", help="Extract meta tags.")
    extract.add_argument("-ai", "--all-info",   action="store_true", dest="all_info",  help="Extract everything.")

    recon = parser.add_argument_group("recon")
    recon.add_argument("--secrets",              action="store_true", help="Scan for secrets, API keys, passwords.")
    recon.add_argument("--fp", "--fingerprint",  action="store_true", dest="fingerprint", help="Detect tech stack.")
    recon.add_argument("--cookies", "-ck",       action="store_true", help="Analyze cookie security flags.")
    recon.add_argument("--robots",               action="store_true", help="Fetch robots.txt and sitemap.xml.")

    spider_grp = parser.add_argument_group("spider")
    spider_grp.add_argument("--spider", action="store_true", help="Crawl recursively within same domain.")
    spider_grp.add_argument("--depth",  type=int, default=2, metavar="N", help="Max spider depth (default: 2).")

    out = parser.add_argument_group("output")
    out.add_argument("-o", "--output",  metavar="FILE", help="Save results to file.")
    out.add_argument("--format",        choices=["json", "txt", "csv"], default="json", dest="fmt",
                     help="Output format (default: json).")
    out.add_argument("-v", "--verbose", action="store_true", help="Show response metadata per request.")

    net = parser.add_argument_group("network")
    net.add_argument("--timeout",     type=int,   default=10, metavar="SEC", help="Request timeout (default: 10s).")
    net.add_argument("--delay",       type=float, default=0,  metavar="SEC", help="Delay between requests.")
    net.add_argument("--concurrency", type=int,   default=10, metavar="N",   help="Max concurrent requests (default: 10).")
    net.add_argument("--proxy",       metavar="URL",   help="Proxy URL (e.g. http://127.0.0.1:8080).")
    net.add_argument("--no-verify",   action="store_true", dest="no_verify", help="Disable SSL verification.")
    net.add_argument("-H", "--header", action="append", default=[], metavar="'Key: Val'",
                     help="Custom header, repeatable.")
    net.add_argument("--user-agent",  dest="user_agent", metavar="UA",
                     default=(
                         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0.0.0 Safari/537.36"
                     ), help="Custom User-Agent.")

    args = parser.parse_args()

    if not args.url and not args.archive:
        print(f"{C.RED}[!] Provide a URL or --archive FILE.{C.RESET}\n")
        parser.print_help()
        sys.exit(1)

    if args.spider and not args.url:
        print(f"{C.RED}[!] --spider requires a single URL, not --archive.{C.RESET}")
        sys.exit(1)

    extraction_flags = [
        args.links, args.images, args.js, args.tables, args.headers,
        args.forms, args.comments, args.meta_tags, args.all_info,
        args.secrets, args.fingerprint, args.cookies, args.robots,
    ]
    if not any(extraction_flags):
        print(f"{C.YELLOW}[!] No extraction flag set — defaulting to --all-info.{C.RESET}")
        args.all_info = True

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
