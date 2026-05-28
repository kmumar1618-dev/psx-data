#!/usr/bin/env python3
"""
NCCPL UIN Wise Settlement Downloader
Connects to YOUR already-running Chrome via remote debugging.
No bot detection. No cookies needed.

BEFORE RUNNING:
1. Launch Chrome with: 
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory="Profile 10"
2. Manually open https://www.nccpl.com.pk/market-information
3. Wait for page to fully load
4. Then run this script

Usage:
  python.exe download_uin.py --date 2026-05-11
  python.exe download_uin.py --from 2026-04-01 --to 2026-05-11
  python.exe download_uin.py --today
"""

import argparse
import time
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ─────────────────────────────────────────────
MARKET_URL   = "https://www.nccpl.com.pk/market-information"
DOWNLOAD_DIR = Path.home() / "Documents" / "psx-data" / "UIN_Settlement"
CDP_URL      = "http://localhost:9222"  # Remote debugging port
# ───────────────────────────────────────────────────────

def is_trading_day(d):
    return d.weekday() < 5

def date_range(start, end):
    current = start
    while current <= end:
        if is_trading_day(current):
            yield current
        current += timedelta(days=1)

def download_one_date(page, target_date, download_dir):
    date_str = str(target_date)

    try:
        # ── Navigate to market information page ────────
        print(f"  → Loading page...")
        page.goto(MARKET_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # ── Check if Cloudflare blocked us ─────────────
        if "just a moment" in page.title().lower():
            print(f"  ⚠  Cloudflare block — please solve it in the browser window")
            input("     Press ENTER here once page is loaded in browser...")

        # ── Click Unlisted TFC / Settlement section ────
        print(f"  → Finding settlement section...")

        # Try multiple possible tab names
        tab_found = False
        for tab_text in ["Unlisted TFC Report/Settlement", "Settlement", "Sett Info UIN Wise", "UIN Wise"]:
            try:
                tab = page.get_by_text(tab_text, exact=False).first
                if tab.is_visible():
                    tab.click()
                    page.wait_for_timeout(2000)
                    tab_found = True
                    print(f"  → Clicked tab: '{tab_text}'")
                    break
            except:
                continue

        if not tab_found:
            # Print all visible text to help debug
            print(f"  ⚠  Could not find settlement tab. Visible links:")
            links = page.locator("a, button, li").all()
            for l in links:
                txt = l.inner_text().strip()
                if txt and len(txt) < 50:
                    print(f"     - '{txt}'")
            return False

        # ── Click "Sett Info UIN Wise" sub-tab ─────────
        for subtab_text in ["Sett Info UIN Wise", "UIN Wise", "UIN"]:
            try:
                subtab = page.get_by_text(subtab_text, exact=False).first
                if subtab.is_visible():
                    subtab.click()
                    page.wait_for_timeout(2000)
                    print(f"  → Clicked subtab: '{subtab_text}'")
                    break
            except:
                continue

        # ── Select date from dropdown ──────────────────
        print(f"  → Selecting date: {date_str}")
        selects = page.locator("select").all()
        date_selected = False

        for select in selects:
            try:
                # Try selecting by value (YYYY-MM-DD format)
                select.select_option(value=date_str)
                date_selected = True
                print(f"  → Date selected by value")
                break
            except:
                pass

        if not date_selected:
            # Print available options for debugging
            print(f"  ⚠  Could not select date. Available dropdown options:")
            for select in selects:
                opts = select.locator("option").all()
                for o in opts[:5]:
                    print(f"     value='{o.get_attribute('value')}' text='{o.inner_text().strip()}'")
            return False

        page.wait_for_timeout(1500)

        # ── Click Export button ────────────────────────
        print(f"  → Clicking Export...")
        with page.expect_download(timeout=30000) as dl_info:
            for btn_text in ["Export", "export", "Download", "CSV"]:
                try:
                    btn = page.get_by_role("button", name=btn_text, exact=False).first
                    if btn.is_visible():
                        btn.click()
                        print(f"  → Clicked button: '{btn_text}'")
                        break
                except:
                    continue

        download = dl_info.value
        save_path = download_dir / f"Sett-Info-UIN-Wise_{date_str}.csv"
        download.save_as(save_path)
        print(f"  ✅ Saved: {save_path.name}")
        return True

    except PlaywrightTimeout as e:
        print(f"  ❌ Timeout: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  help="Single date e.g. 2026-05-11")
    parser.add_argument("--from",  dest="start", help="Start date e.g. 2026-04-01")
    parser.add_argument("--to",    dest="end",   help="End date e.g. 2026-05-11")
    parser.add_argument("--today", action="store_true", help="Download today")
    args = parser.parse_args()

    if args.today:
        dates = [date.today()]
    elif args.date:
        dates = [date.fromisoformat(args.date)]
    elif args.start and args.end:
        dates = list(date_range(
            date.fromisoformat(args.start),
            date.fromisoformat(args.end)
        ))
    else:
        print("Usage:")
        print("  python.exe download_uin.py --today")
        print("  python.exe download_uin.py --date 2026-05-11")
        print("  python.exe download_uin.py --from 2026-04-01 --to 2026-05-11")
        return

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n📅 Dates to download : {len(dates)}")
    print(f"📁 Saving to         : {DOWNLOAD_DIR}")
    print(f"🔌 Connecting to     : Chrome on port 9222\n")
    print("─" * 45)

    success = 0
    skipped = 0
    failed  = 0

    with sync_playwright() as p:
        # Connect to YOUR already-running Chrome
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            print("✅ Connected to your Chrome browser\n")
        except Exception as e:
            print(f"❌ Could not connect to Chrome: {e}")
            print("\nMake sure Chrome is running with:")
            print('  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --profile-directory="Profile 10"')
            return

        # Use existing context (your real browser session)
        context = browser.contexts[0]
        context.set_default_timeout(30000)

        # Set download path
        context.set_default_timeout(30000)
        page = context.new_page()

        for i, d in enumerate(dates, 1):
            print(f"[{i}/{len(dates)}] {d} ({d.strftime('%A')})")

            existing = DOWNLOAD_DIR / f"Sett-Info-UIN-Wise_{d}.csv"
            if existing.exists():
                print(f"  ⏭  Already exists, skipping")
                skipped += 1
                continue

            result = download_one_date(page, d, DOWNLOAD_DIR)
            if result:
                success += 1
            else:
                failed += 1

            if i < len(dates):
                time.sleep(1.5)

        page.close()

    print("\n" + "═" * 45)
    print(f"  ✅ Downloaded : {success}")
    print(f"  ⏭  Skipped   : {skipped}")
    print(f"  ❌ Failed     : {failed}")
    print(f"  📁 Folder     : {DOWNLOAD_DIR}")
    print("═" * 45)

if __name__ == "__main__":
    main()
