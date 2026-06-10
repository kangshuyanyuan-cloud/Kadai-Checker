"""
unified_check.py - Moodle課題チェッカー（統合版）

PC起動時にバックグラウンドでMoodleをスクレイピングし、
1. 24時間以内に期限がある課題があればWindows通知を表示
2. ターミナルに課題一覧を表示（タスクバーに最小化された状態で待機）
3. 番号入力でブラウザから課題ページを開ける

これにより、通知を見たらタスクバーのターミナルをクリックするだけで
即座に課題一覧を確認できる（再スクレイピング不要）。
"""

import asyncio
import ctypes
import os
import re
import sys
import webbrowser
from datetime import datetime, timedelta

try:
    from winotify import Notification, audio
    HAS_WINOTIFY = True
except ImportError:
    HAS_WINOTIFY = False

from browser_manager import BrowserManager
from scraper import MoodleScraper

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")


def _get_console_hwnd():
    """コンソールウィンドウのハンドルを取得する"""
    try:
        kernel32 = ctypes.windll.kernel32
        return kernel32.GetConsoleWindow()
    except Exception:
        return None


def position_window_bottom_right():
    """コンソールウィンドウを画面右下に小さく配置する"""
    try:
        user32 = ctypes.windll.user32
        hwnd = _get_console_hwnd()
        if not hwnd:
            return

        # 画面の解像度を取得
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        # ウィンドウサイズ（大体のピクセル数）
        win_w = 600
        win_h = 500

        # 右下へ配置
        x = screen_w - win_w - 50
        y = screen_h - win_h - 100

        user32.MoveWindow(hwnd, x, y, win_w, win_h, True)
    except Exception:
        pass


def minimize_to_taskbar():
    """コンソールウィンドウをタスクバーに最小化する"""
    try:
        user32 = ctypes.windll.user32
        hwnd = _get_console_hwnd()
        if not hwnd:
            return

        # SW_MINIMIZE = 6
        user32.ShowWindow(hwnd, 6)
    except Exception:
        pass

# スクリプトのディレクトリ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# コンソール用の色コード（Windowsの新しいターミナルで動作）
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


# ============================================================
#  Windows通知（ポップアップ）
# ============================================================

def show_notification(title: str, msg: str, add_taskbar_hint: bool = True):
    """Windowsのトースト通知を表示する（winotify使用）"""
    # タスクバーに最小化されていることを通知メッセージに追加
    display_msg = msg
    if add_taskbar_hint:
        display_msg = msg + "\nタスクバーのアイコンをクリックして確認できます"

    if not HAS_WINOTIFY:
        # winotifyがない場合はターミナルに表示するだけ
        print(f"  [通知] {title}: {msg}")
        return

    try:
        toast = Notification(
            app_id="Moodle課題チェッカー",
            title=title,
            msg=display_msg,
            duration="long",
        )
        
        # 通知に「課題を確認する」ボタンを追加
        restore_vbs = os.path.join(BASE_DIR, "restore_window.vbs")
        toast.add_actions(label="課題を確認する", launch=restore_vbs)

        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception as e:
        # 通知が失敗してもプログラムは止めない
        print(f"  [通知エラー] {e}")
        print(f"  [通知] {title}: {msg}")


# ============================================================
#  期限チェック（24時間以内かどうか）
# ============================================================

def parse_deadline_to_datetime(deadline_str: str):
    """
    "2026年 06月 2日(火曜日) 10:50" のような文字列から datetime を作成する
    """
    if not deadline_str or deadline_str == "不明":
        return None

    match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(\d{1,2}):(\d{1,2})", deadline_str)
    if match:
        year, month, day, hour, minute = map(int, match.groups())
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None
    return None


def find_urgent_tasks(assignments):
    """未提出かつ24時間以内に期限がある課題を抽出する"""
    unsubmitted = [a for a in assignments if not a.get("submitted")]
    now = datetime.now()
    urgent = []

    for a in unsubmitted:
        dt = parse_deadline_to_datetime(a.get("deadline", ""))
        if dt:
            time_diff = dt - now
            if timedelta(seconds=0) < time_diff <= timedelta(hours=24):
                urgent.append((a, dt, time_diff))

    urgent.sort(key=lambda x: x[1])
    return urgent


# ============================================================
#  ターミナル表示
# ============================================================

def display_assignments(assignments):
    """課題一覧をターミナルにキレイに表示する"""
    unsubmitted = [a for a in assignments if not a.get("submitted")]
    submitted = [a for a in assignments if a.get("submitted")]

    print(f"\n\n{'=' * 60}")
    print(f" {YELLOW}☆ 見つかった課題一覧 ☆{RESET}")
    print(f"{'=' * 60}")

    print(f"\n{RED}【まだ提出していない課題】 ({len(unsubmitted)}件){RESET}")
    if not unsubmitted:
        print("  ありません！完璧です！")
    for i, a in enumerate(unsubmitted):
        deadline = a.get("deadline") or "不明"
        print(f"\n  [{i + 1}] ■ {a['title']}")
        print(f"    科目: {a['course']}")
        print(f"    期限: {RED}{deadline}{RESET}")
        print(f"    URL:  {CYAN}{a['url']}{RESET}")

    offset = len(unsubmitted)
    print(f"\n\n{GREEN}【提出済みの課題】 ({len(submitted)}件){RESET}")
    if not submitted:
        print("  ありません。")
    for i, a in enumerate(submitted):
        deadline = a.get("deadline") or "不明"
        print(f"\n  [{offset + i + 1}] ■ {a['title']}")
        print(f"    科目: {a['course']}")
        print(f"    期限: {deadline}")
        print(f"    URL:  {CYAN}{a['url']}{RESET}")

    print(f"\n{'=' * 60}\n")

    return unsubmitted + submitted


def interactive_mode(all_tasks):
    """番号入力でブラウザから課題ページを開ける対話モード"""
    if not all_tasks:
        print("課題がないため、対話モードをスキップします。")
        input("\nEnterキーを押すと終了します...")
        return

    while True:
        print("\n" + "-" * 60)
        print(f"リンクを開きたい場合は、課題の【番号】(1～{len(all_tasks)})を入力してEnterを押してください。")
        print("終了する場合は、何も入力せずにそのままEnterを押してください。")
        choice = input("番号を入力 (終了はEnter): ").strip()
        if not choice:
            break
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(all_tasks):
                # & を含むURLが壊れるのを防ぐ
                safe_url = all_tasks[idx]['url'].split('&')[0]
                print(f"ブラウザで開きます: {safe_url}")
                webbrowser.open(safe_url)
            else:
                print("正しい番号を入力してください。")
        else:
            print("数字を入力してください。")


# ============================================================
#  メイン処理
# ============================================================

async def main():
    # ターミナルのタイトルを設定
    os.system("title Moodle 課題チェッカー")
    # ANSIエスケープシーケンスを有効化
    os.system("color")
    # ウィンドウを画面右下に配置
    # position_window_bottom_right()

    print(f"{CYAN}=================================================={RESET}")
    print(f"{CYAN}       Moodle 課題チェッカー（統合版）             {RESET}")
    print(f"{CYAN}=================================================={RESET}")
    print(f"  実行日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    print()
    print(f"  Moodleから最新の課題情報を取得しています...")
    print(f"  (ブラウザが裏で動くので少々お待ちください)")
    print()

    assignments = []
    browser_mgr = BrowserManager()

    try:
        # ---- ブラウザ起動 & ログイン & スクレイピング（1回だけ） ----
        page = await browser_mgr.start()

        from login import login
        is_logged_in = await login(page)

        if not is_logged_in:
            print(f"{RED}ログインに失敗しました。{RESET}")
            show_notification("Moodle: エラー", "ログインに失敗しました。")
            input("\nEnterキーを押すと終了します...")
            return

        scraper = MoodleScraper(page)
        assignments = await scraper.run()

    except Exception as e:
        import traceback
        print(f"{RED}エラーが発生しました: {e}{RESET}")
        with open(os.path.join(BASE_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Error: {e}\n")
            f.write(traceback.format_exc() + "\n")
        show_notification("Moodle: エラー", f"課題取得中にエラーが発生しました")
        input("\nEnterキーを押すと終了します...")
        return

    finally:
        # ---- ブラウザを閉じる（メモリ解放）----
        await browser_mgr.close()

    # ---- ここからはブラウザ不要。ターミナル表示 & 通知 ----

    # 24時間以内に期限がある課題をチェック → Windows通知
    urgent_tasks = find_urgent_tasks(assignments)

    if urgent_tasks:
        title = "Moodle: 期限が迫っている課題があります！"
        msg = f"24時間以内に期限を迎える課題が {len(urgent_tasks)} 件あります。"
        show_notification(title, msg)
    else:
        show_notification("Moodle: チェック完了", "期限が24時間以内の課題はありません。")


    all_tasks = display_assignments(assignments)

    # タスクバーのタイトルに未提出件数を表示
    unsubmitted_count = len([a for a in assignments if not a.get("submitted")])
    if unsubmitted_count > 0:
        os.system(f"title Moodle課題チェッカー - 未提出{unsubmitted_count}件")
    else:
        os.system("title Moodle課題チェッカー - 全て提出済み！")

    print(f"{CYAN}チェックが完了しました。{RESET}")
    print(f"{CYAN}このウィンドウはタスクバーに最小化されます。{RESET}")
    print(f"{CYAN}いつでもタスクバーのアイコンをクリックして確認できます。{RESET}")

    # ウィンドウをタスクバーに最小化する
    minimize_to_taskbar()

    # 対話モード（番号入力でブラウザ遷移）
    interactive_mode(all_tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
