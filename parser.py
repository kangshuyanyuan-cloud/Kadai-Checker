"""
parser.py - Moodle課題情報パースモジュール

取得したHTMLから課題情報を抽出・整理します。
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup


# 課題を示すキーワード（日本語・英語）
ASSIGNMENT_KEYWORDS = [
    "課題", "レポート", "提出", "assignment", "quiz", "小テスト",
    "forum", "アンケート", "survey", "締切", "due", "期限",
    "ワークシート", "worksheet", "テスト", "試験"
]

# 日付パターン（様々な形式に対応）
DATE_PATTERNS = [
    r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日.*?\d{2}:\d{2}", # 2026年 06月 2日(火曜日) 10:50 など
    r"\d{4}年\s*\d{1,2}月\s*\d{1,2}日",               # 2024年5月28日
    r"\d{4}/\d{1,2}/\d{1,2}",               # 2024/5/28
    r"\d{4}-\d{1,2}-\d{1,2}",               # 2024-05-28
    r"\d{1,2}月\d{1,2}日",                   # 5月28日
    r"\d{1,2}/\d{1,2}\s*\d{2}:\d{2}",       # 5/28 23:59
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",       # ISO形式
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,\s*\d+\s+\w+\s+\d{4}",  # 英語日付
]


def extract_deadline_from_text(text: str) -> Optional[str]:
    """
    テキストから締切日時を抽出する。
    """
    if not text:
        return None

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group().strip()

    # "締切", "due", "期限", "終了予定" の後ろの日付を探す
    deadline_keywords = ["締切", "期限", "due", "until", "まで", "終了予定"]
    for keyword in deadline_keywords:
        idx = text.lower().find(keyword.lower())
        if idx != -1:
            # キーワードの後ろ50文字を検索
            after_text = text[idx:idx+50]
            for pattern in DATE_PATTERNS:
                match = re.search(pattern, after_text)
                if match:
                    return match.group().strip()

    return None


def normalize_deadline(deadline_str: Optional[str]) -> Optional[str]:
    """
    締切日時を統一形式（YYYY-MM-DD HH:MM）に変換する。
    """
    if not deadline_str:
        return None

    current_year = datetime.now().year

    # 変換パターンを試す
    parse_formats = [
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日%H:%M",
        "%Y年%m月%d日",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M",
        "%m月%d日 %H:%M",
        "%m月%d日",
    ]

    for fmt in parse_formats:
        try:
            # 年なしの場合は現在の年を追加
            if "%Y" not in fmt:
                dt = datetime.strptime(f"{current_year}年 {deadline_str}", f"%Y年 {fmt}")
            else:
                dt = datetime.strptime(deadline_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue

    # パース失敗時はそのまま返す
    return deadline_str


def is_assignment_related(text: str) -> bool:
    """
    テキストが課題関連かどうか判定する。
    """
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in ASSIGNMENT_KEYWORDS)


def determine_assignment_type(text: str, url: str = "") -> str:
    """
    課題のタイプを判定する。
    """
    text_lower = text.lower()
    url_lower = url.lower()

    if "quiz" in text_lower or "quiz" in url_lower or "小テスト" in text_lower:
        return "quiz"
    elif "forum" in text_lower or "forum" in url_lower or "掲示板" in text_lower:
        return "forum"
    elif "survey" in text_lower or "survey" in url_lower or "アンケート" in text_lower:
        return "survey"
    elif "assignment" in url_lower or "課題" in text_lower or "レポート" in text_lower:
        return "assignment"
    elif "choice" in url_lower:
        return "choice"
    else:
        return "assignment"


def determine_submission_status(text: str) -> bool:
    """
    提出状況を判定する（True = 提出済み）。
    """
    submitted_keywords = ["提出済", "提出済み", "submitted", "完了", "完成"]
    not_submitted_keywords = ["未提出", "not submitted", "提出が必要", "未完了"]

    text_lower = text.lower()

    # 未提出キーワードがあれば未提出
    if any(kw.lower() in text_lower for kw in not_submitted_keywords):
        return False

    # 提出済みキーワードがあれば提出済み
    if any(kw.lower() in text_lower for kw in submitted_keywords):
        return True

    # どちらでもなければ未提出と仮定
    return False


def parse_assignments_from_html(html: str, course_name: str, base_url: str = "") -> List[Dict[str, Any]]:
    """
    コースページのHTMLから課題情報を抽出する。

    Args:
        html: ページのHTML文字列
        course_name: コース名
        base_url: ページのURL（相対URLを絶対URLに変換するため）

    Returns:
        課題情報のリスト
    """
    soup = BeautifulSoup(html, "lxml")
    assignments = []

    # ---- 方法1: activityリストから取得（Moodleの標準構造）----
    activity_items = soup.select(
        "li.activity, "
        ".activityinstance, "
        "div[class*='activity'], "
        "li[class*='modtype']"
    )

    for item in activity_items:
        try:
            # 要素名を取得
            name_elem = item.select_one(
                ".instancename, .activitytitle, "
                "span.instancename, a .instancename"
            )
            if not name_elem:
                # リンクテキストを使用
                link = item.select_one("a")
                if link:
                    name_elem = link

            if not name_elem:
                continue

            title = name_elem.get_text(strip=True)

            # 課題関連かどうか確認
            if not is_assignment_related(title) and not is_assignment_related(str(item)):
                continue

            # URL取得
            link = item.select_one("a[href]")
            url = link["href"] if link else ""

            # 全テキストから日付を探す
            full_text = item.get_text(" ", strip=True)
            deadline = normalize_deadline(extract_deadline_from_text(full_text))

            # 課題タイプ判定
            assignment_type = determine_assignment_type(title, url)

            # モジュールタイプをクラス名から判定
            for cls in item.get("class", []):
                if "assign" in cls:
                    assignment_type = "assignment"
                    break
                elif "quiz" in cls:
                    assignment_type = "quiz"
                    break
                elif "forum" in cls:
                    assignment_type = "forum"
                    break

            # 提出状況
            submitted = determine_submission_status(full_text)

            assignments.append({
                "course": course_name,
                "title": title,
                "deadline": deadline or "",
                "submitted": submitted,
                "type": assignment_type,
                "url": url,
            })

        except Exception:
            continue

    # ---- 方法2: calendar / upcoming eventsから取得 ----
    event_items = soup.select(
        ".event, "
        "[data-region='event-item'], "
        ".calendarwrapper .event, "
        "[class*='upcoming'] .event"
    )

    for event in event_items:
        try:
            title_elem = event.select_one("a, .name, h3, h4")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title:
                continue

            full_text = event.get_text(" ", strip=True)
            deadline = normalize_deadline(extract_deadline_from_text(full_text))

            link = event.select_one("a[href]")
            url = link["href"] if link else ""

            submitted = determine_submission_status(full_text)
            assignment_type = determine_assignment_type(title, url)

            # 重複チェック
            if not any(a["title"] == title and a["course"] == course_name for a in assignments):
                assignments.append({
                    "course": course_name,
                    "title": title,
                    "deadline": deadline or "",
                    "submitted": submitted,
                    "type": assignment_type,
                    "url": url,
                })

        except Exception:
            continue

    return assignments


def parse_course_list_from_html(html: str, base_url: str = "") -> List[Dict[str, str]]:
    """
    マイコースページやダッシュボードからコース一覧を取得する。

    Returns:
        [{"name": コース名, "url": コースURL}, ...]
    """
    soup = BeautifulSoup(html, "lxml")
    courses = []

    # コース一覧のセレクタ（Moodleのバージョンによって異なる）
    course_selectors = [
        "a[href*='course/view.php']",
        ".coursename a",
        "[data-region='course-content'] a",
        ".course-listitem a",
        "h3.coursename a",
        ".course-card-title a",
        ".dashboard-card-title a",
        "[class*='course-title'] a",
    ]

    seen_urls = set()

    for selector in course_selectors:
        links = soup.select(selector)
        for link in links:
            href = link.get("href", "")
            name = link.get_text(strip=True)

            if not href or not name:
                continue

            # course/view.phpを含むURLのみ対象
            if "course/view.php" not in href:
                continue

            # 重複除外
            if href in seen_urls:
                continue

            seen_urls.add(href)
            courses.append({"name": name, "url": href})

    return courses


def sort_assignments(assignments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    課題を以下の順番でソートする：
    1. 未提出を上に
    2. 締切が近い順
    3. 締切なしは最後
    """
    def sort_key(a: Dict[str, Any]):
        # 未提出を上に（Falseが先）
        submitted_order = 1 if a.get("submitted", False) else 0

        # 締切日時でソート
        deadline_str = a.get("deadline", "")
        if deadline_str:
            try:
                dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
                return (submitted_order, dt)
            except ValueError:
                try:
                    dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                    return (submitted_order, dt)
                except ValueError:
                    pass

        # 締切なしは最後
        return (submitted_order, datetime.max)

    return sorted(assignments, key=sort_key)
