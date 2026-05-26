import asyncio
import os
import re
import subprocess
import time
from datetime import datetime, timedelta

from browser_manager import BrowserManager
from scraper import MoodleScraper

os.environ["PYTHONIOENCODING"] = "utf-8"

# スクリプトのディレクトリ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def parse_deadline_to_datetime(deadline_str: str):
    """
    "2026年 06月 2日(火曜日) 10:50" のような文字列から datetime オブジェクトを作成する
    """
    if not deadline_str or deadline_str == "不明":
        return None
        
    # 年、月、日、時、分を抽出
    match = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日.*?(\d{1,2}):(\d{1,2})", deadline_str)
    if match:
        year, month, day, hour, minute = map(int, match.groups())
        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None
    return None

def show_notification(title: str, msg: str):
    """Windows標準の吹き出し通知を表示する（確実に動く方法）"""
    ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$balloon = New-Object System.Windows.Forms.NotifyIcon
$balloon.Icon = [System.Drawing.SystemIcons]::Information
$balloon.BalloonTipTitle = "{title}"
$balloon.BalloonTipText = "{msg}"
$balloon.Visible = $true
$balloon.ShowBalloonTip(10000)
Start-Sleep -Seconds 5
$balloon.Dispose()
'''
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

async def main():
    browser_mgr = BrowserManager()
    try:
        page = await browser_mgr.start()
        
        # ログイン処理
        from login import login
        is_logged_in = await login(page)
        
        if not is_logged_in:
            show_notification("Moodle: エラー", "ログインに失敗しました。手動でログインしてください。")
            return

        scraper = MoodleScraper(page)
        assignments = await scraper.run()

        # 未提出の課題をフィルタリング
        unsubmitted = [a for a in assignments if not a.get("submitted")]
        
        now = datetime.now()
        urgent_tasks = []
        
        for a in unsubmitted:
            deadline_str = a.get("deadline", "")
            dt = parse_deadline_to_datetime(deadline_str)
            
            if dt:
                # 現在時刻より未来、かつ24時間以内かどうか
                time_diff = dt - now
                if timedelta(seconds=0) < time_diff <= timedelta(hours=24):
                    urgent_tasks.append((a, dt, time_diff))
                    
        if urgent_tasks:
            # 期限が近い順にソート
            urgent_tasks.sort(key=lambda x: x[1])
            
            # 通知文面の作成
            count = len(urgent_tasks)
            top_task, top_dt, _ = urgent_tasks[0]
            
            if count == 1:
                title = "Moodle: 期限が近い課題があります"
                msg = f"{top_task['title']} - 期限: {top_dt.strftime('%m/%d %H:%M')}"
            else:
                title = f"Moodle: {count}件の課題が24時間以内"
                msg = f"{top_task['title']} - 期限: {top_dt.strftime('%m/%d %H:%M')}"
            
            show_notification(title, msg)

        else:
            # --- 24時間以内の課題がなかった場合の通知 ---
            show_notification("Moodle: チェック完了", "期限が24時間以内の課題はありません")

    except Exception as e:
        import traceback
        with open(os.path.join(BASE_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Error: {e}\n")
            f.write(traceback.format_exc() + "\n")
    finally:
        await browser_mgr.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        pass
