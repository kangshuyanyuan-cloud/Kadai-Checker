"""
scraper.py - カレンダーから直近の課題リンクを抽出して巡回するスクレイパー
"""

import os
import asyncio
from typing import List, Dict, Any
from playwright.async_api import Page
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from human_behavior import HumanBehavior
from parser import sort_assignments, extract_deadline_from_text, normalize_deadline

load_dotenv()
MOODLE_URL = os.getenv("MOODLE_URL", "https://md.kumamoto-u.ac.jp/").rstrip("/")

class MoodleScraper:
    def __init__(self, page: Page):
        self.page = page
        self.human = HumanBehavior(page)
        self.all_assignments: List[Dict[str, Any]] = []
        self.visited_urls = set()

    async def run(self) -> List[Dict[str, Any]]:
        print("\n=== Moodle課題収集（カレンダー・直近イベント版）を開始します ===\n")
        
        # 1. カレンダーの「直近のイベント」ページに移動
        print("[Step 1] カレンダー（直近のイベント）へアクセス...")
        upcoming_url = f"{MOODLE_URL}/calendar/view.php?view=upcoming"
        await self.page.goto(upcoming_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await self.human.simulate_reading()

        # HTMLからイベントのリンクを抽出
        html = await self.page.content()
        soup = BeautifulSoup(html, "lxml")
        
        event_links = []
        # Moodleカレンダーのイベントリスト内のリンクを探す
        for event_div in soup.select(".eventlist .event"):
            title_tag = event_div.select_one(".name.d-inline-block")
            link_tag = event_div.select_one("a.card-link") # "活動に移動する" などのリンク
            
            title = title_tag.get_text(strip=True) if title_tag else "不明なイベント"
            
            href = ""
            if link_tag and link_tag.get("href"):
                href = link_tag.get("href")
            else:
                # リンクが見つからない場合はイベント内の他のリンクを探す
                for a in event_div.select("a[href]"):
                    h = a.get("href", "")
                    if "mod/" in h or "assign" in h or "quiz" in h:
                        href = h
                        break
            
            # カレンダーイベントに書かれている日付情報を探す
            deadline_text = "不明"
            date_div = event_div.select_one(".row .col-11[dir='ltr']")
            if not date_div:
                date_div = event_div.select_one(".date, .dimmed_text, div.mt-1")
            
            if date_div:
                deadline_text = date_div.get_text(strip=True)
            else:
                text_lines = event_div.get_text(separator="\n").split("\n")
                for line in text_lines:
                    line = line.strip()
                    if "年" in line and "月" in line and "日" in line:
                        deadline_text = line
                        break
                    elif "本日," in line or "明日," in line:
                        deadline_text = line
                        break
                        
            # ★「開始予定」のイベントを除外する
            if "開始" in title or "開始" in deadline_text:
                continue

            
            # コース名を探す
            course_name = "不明"
            course_tag = event_div.select_one(".col-11 a[href*='course/view.php']")
            if course_tag:
                course_name = course_tag.get_text(strip=True)
            elif "コースイベント" in event_div.get_text():
                text = event_div.get_text(separator="\n").split("\n")
                for i, line in enumerate(text):
                    if "コースイベント" in line and i+1 < len(text):
                        course_name = text[i+1].strip()
                        break
                        
            if href and href not in [x["url"] for x in event_links]:
                event_links.append({
                    "title": title[:80],
                    "url": href,
                    "course": course_name,
                    "deadline_from_calendar": deadline_text
                })
        
        print(f"  カレンダーから {len(event_links)} 件のイベントリンクを発見しました\n")

        # 2. 各イベントリンクを踏んで課題の詳細を取得
        print("[Step 2] 課題リンクを1つずつ開いて提出状況を確認します...")
        for i, link_info in enumerate(event_links, 1):
            url = link_info["url"]
            print(f"  [{i}/{len(event_links)}] {link_info['title'][:40]} へアクセス中...")
            
            if url in self.visited_urls:
                continue
            self.visited_urls.add(url)
            
            try:
                await self.page.goto(url, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # 詳細ページから情報取得
                page_html = await self.page.content()
                page_soup = BeautifulSoup(page_html, "lxml")
                full_text = page_soup.get_text(" ", strip=True)
                
                # --- 詳細ページから期限を直接取得（確実な方法） ---
                deadline_text = "不明"
                
                # 正規表現を使って、全テキストから直接「2026年 06月 2日(火曜日) 10:50」のような日付を抜く
                import re
                
                # 「終了予定: 〇年〇月〇日」などを探す
                match = re.search(r"(終了予定|期限|due|締切|提出期限|終了).*?(\d{4}年\s*\d{1,2}月\s*\d{1,2}日.*?\d{1,2}:\d{1,2})", full_text, re.IGNORECASE)
                if match:
                    deadline_text = match.group(2).strip()
                else:
                    # キーワードがなくても日付らしいものがあればそれを採用する（開始予定は除く）
                    match2 = re.search(r"(?<!開始予定:\s)(\d{4}年\s*\d{1,2}月\s*\d{1,2}日.*?\d{1,2}:\d{1,2})", full_text)
                    if match2:
                        deadline_text = match2.group(1).strip()
                
                # 3. カレンダーから取得した情報をフォールバックとして使う
                if deadline_text == "不明":
                    deadline_text = link_info.get("deadline_from_calendar", "不明")
                        
                deadline = deadline_text

                # 提出状況を確認
                submitted = False
                submitted_keywords = ["提出済", "提出済み", "Submitted", "評定済み"]
                for kw in submitted_keywords:
                    if kw in full_text:
                        submitted = True
                        break
                
                atype = "assignment"
                if "quiz" in url: atype = "quiz"
                elif "feedback" in url: atype = "feedback"
                elif "forum" in url: atype = "forum"
                
                self.all_assignments.append({
                    "course": link_info["course"],
                    "title": link_info["title"],
                    "deadline": deadline,
                    "submitted": submitted,
                    "type": atype,
                    "url": url,
                })
                
            except Exception as e:
                print(f"    エラー: {e}")

        # 締切順にソート
        sorted_assignments = sort_assignments(self.all_assignments)
        
        print(f"\n完了！カレンダーから {len(sorted_assignments)} 件の課題情報を収集しました")
        return sorted_assignments
