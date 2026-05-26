"""
main.py - 熊本大学Moodle自動課題収集ツール メインエントリポイント

使い方:
    python main.py           # 通常実行
    python main.py --debug   # デバッグモード

必要なもの:
    pip install -r requirements.txt
    playwright install chromium
"""

import asyncio
import argparse
import json
import csv
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Windows日本語環境でのUTF-8出力を強制
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from colorama import init, Fore, Style
from dotenv import load_dotenv

from browser_manager import BrowserManager
from login import login
from scraper import MoodleScraper
from notifier import Notifier

# Windows用のcolorama初期化
init(autoreset=True, convert=True)

# .envを読み込む
load_dotenv()


# ====== 表示用の設定 ======

def print_banner():
    """起動バナーを表示する"""
    print()
    print("=" * 50)
    print("  [KumaMoodle] 熊本大学 Moodle 課題収集ツール")
    print("  KumaMoodle Scraper v1.0")
    print("=" * 50)


def print_assignment(assignment: Dict[str, Any], index: int) -> None:
    """
    1つの課題を見やすく表示する。
    """
    submitted = assignment.get("submitted", False)
    title = assignment.get("title", "（タイトル不明）")
    course = assignment.get("course", "（コース不明）")
    deadline = assignment.get("deadline", "")
    assignment_type = assignment.get("type", "assignment")
    url = assignment.get("url", "")

    # 提出状況に応じて色を変える
    if submitted:
        status_str = f"{Fore.GREEN}[提出済み]{Style.RESET_ALL}"
        title_color = Fore.WHITE
    else:
        status_str = f"{Fore.RED}[未提出]{Style.RESET_ALL}"
        title_color = Fore.YELLOW

    # 締切が近い場合（3日以内）は赤で強調
    deadline_display = deadline or "締切なし / 不明"
    if deadline:
        try:
            formats = ["%Y-%m-%d %H:%M", "%Y-%m-%d"]
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(deadline, fmt)
                    break
                except ValueError:
                    continue

            if dt:
                now = datetime.now()
                days_left = (dt - now).days
                if days_left < 0:
                    deadline_display = f"{Fore.RED}{deadline} (期限切れ！){Style.RESET_ALL}"
                elif days_left <= 1:
                    deadline_display = f"{Fore.RED}{deadline} (明日まで！){Style.RESET_ALL}"
                elif days_left <= 3:
                    deadline_display = f"{Fore.YELLOW}{deadline} (あと{days_left}日){Style.RESET_ALL}"
                else:
                    deadline_display = f"{deadline} (あと{days_left}日)"
        except Exception:
            pass

    # 課題タイプ
    type_labels = {
        "assignment": "[課題]",
        "quiz": "[小テスト]",
        "forum": "[フォーラム]",
        "survey": "[アンケート]",
        "choice": "[選択]",
    }
    type_label = type_labels.get(assignment_type, "[課題]")

    print(f"\n{Fore.CYAN}{'-' * 50}{Style.RESET_ALL}")
    print(f"  {type_label} {title_color}{title}{Style.RESET_ALL}")
    print(f"  コース: {course}")
    print(f"  締切: {deadline_display}")
    print(f"  状態: {status_str}")
    print(f"  タイプ: {assignment_type}")
    if url:
        print(f"  URL: {Fore.BLUE}{url}{Style.RESET_ALL}")


def display_assignments(assignments: List[Dict[str, Any]]) -> None:
    """
    全課題を見やすく表示する。
    未提出を上に、締切順に表示。
    """
    if not assignments:
        print(f"\n{Fore.YELLOW}課題が見つかりませんでした。{Style.RESET_ALL}")
        print("  -> ログインに成功しているか確認してください")
        print("  -> コースに課題が登録されているか確認してください")
        return

    # 未提出と提出済みに分類
    not_submitted = [a for a in assignments if not a.get("submitted", False)]
    submitted_list = [a for a in assignments if a.get("submitted", False)]

    print(f"\n{Fore.CYAN}{'=' * 50}")
    print(f"  課題一覧サマリー")
    print(f"{'=' * 50}{Style.RESET_ALL}")
    print(f"  合計: {len(assignments)} 件")
    print(f"  {Fore.RED}未提出: {len(not_submitted)} 件{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}提出済み: {len(submitted_list)} 件{Style.RESET_ALL}")

    # 未提出の課題を表示
    if not_submitted:
        print(f"\n{Fore.RED}{'=' * 50}")
        print(f"  [未提出の課題] ({len(not_submitted)} 件)")
        print(f"{'=' * 50}{Style.RESET_ALL}")
        for i, assignment in enumerate(not_submitted, 1):
            print_assignment(assignment, i)

    # 提出済みの課題を表示
    if submitted_list:
        print(f"\n{Fore.GREEN}{'=' * 50}")
        print(f"  [提出済みの課題] ({len(submitted_list)} 件)")
        print(f"{'=' * 50}{Style.RESET_ALL}")
        for i, assignment in enumerate(submitted_list, 1):
            print_assignment(assignment, i)

    print(f"\n{Fore.CYAN}{'=' * 50}{Style.RESET_ALL}")


def save_json(assignments: List[Dict[str, Any]], filepath: str = "assignments.json") -> None:
    """課題情報をJSONファイルに保存する"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(assignments, f, ensure_ascii=False, indent=2)
        print(f"JSON に保存しました: {filepath}")
    except Exception as e:
        print(f"JSON保存エラー: {e}")


def save_csv(assignments: List[Dict[str, Any]], filepath: str = "assignments.csv") -> None:
    """課題情報をCSVファイルに保存する"""
    try:
        fieldnames = ["course", "title", "deadline", "submitted", "type", "url"]

        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for assignment in assignments:
                # submittedをYes/Noに変換
                row = assignment.copy()
                row["submitted"] = "Yes" if row.get("submitted") else "No"
                writer.writerow({k: row.get(k, "") for k in fieldnames})

        print(f"CSV に保存しました: {filepath}")
    except Exception as e:
        print(f"CSV保存エラー: {e}")


async def main():
    """メイン処理"""
    # コマンドライン引数の処理
    parser = argparse.ArgumentParser(
        description="熊本大学Moodle課題自動収集ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモード（詳細ログを表示）",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="ファイルへの保存をスキップ",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="出力ディレクトリ（デフォルト: カレントディレクトリ）",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="JSON結果の出力先パス（機械読み取り用）",
    )
    args = parser.parse_args()

    # バナー表示
    print_banner()
    print(f"  実行日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print()

    # 環境変数チェック
    if not os.getenv("KUMADAI_ID"):
        print(f"{Fore.RED}エラー: .envファイルにKUMADAI_IDが設定されていません{Style.RESET_ALL}")
        sys.exit(1)

    if not os.getenv("KUMADAI_PASSWORD"):
        print(f"{Fore.RED}エラー: .envファイルにKUMADAI_PASSWORDが設定されていません{Style.RESET_ALL}")
        sys.exit(1)

    # ブラウザマネージャーを初期化
    browser_mgr = BrowserManager()
    assignments = []

    try:
        # Chromeを起動
        print("ブラウザを起動中...")
        page = await browser_mgr.start()

        # ログイン処理
        login_success = await login(page)

        if not login_success:
            print(f"\n{Fore.RED}ログインに失敗しました。{Style.RESET_ALL}")
            print("  確認してください:")
            print("  1. .envのKUMADAI_IDとKUMADAI_PASSWORDが正しいか")
            print("  2. Moodleサイトにアクセスできるか")
            print("  3. debug_login_page.png を確認してください")
            print()
            input("Enterキーを押すとブラウザを終了します...")
            await browser_mgr.close()
            sys.exit(1)

        # 課題収集
        scraper = MoodleScraper(page)
        assignments = await scraper.run()

        # 結果を表示
        display_assignments(assignments)

        # ファイルに保存
        if not args.no_save:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(exist_ok=True)

            json_path = output_dir / "assignments.json"
            csv_path = output_dir / "assignments.csv"

            save_json(assignments, str(json_path))
            save_csv(assignments, str(csv_path))

        # json-outputオプションがあればそこにも書き出す
        if args.json_output:
            save_json(assignments, args.json_output)

        # 通知送信（設定されている場合）
        notifier = Notifier()
        unsubmitted = [a for a in assignments if not a.get("submitted", False)]
        if unsubmitted:
            await notifier.notify_new_assignments(unsubmitted)

        print(f"\n{Fore.CYAN}完了！ブラウザを閉じるにはEnterキーを押してください...{Style.RESET_ALL}")
        input()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}中断されました{Style.RESET_ALL}")

    except Exception as e:
        print(f"\n{Fore.RED}予期しないエラー: {e}{Style.RESET_ALL}")
        if args.debug:
            import traceback
            traceback.print_exc()

    finally:
        # ブラウザを終了
        await browser_mgr.close()

    return assignments


if __name__ == "__main__":
    asyncio.run(main())
