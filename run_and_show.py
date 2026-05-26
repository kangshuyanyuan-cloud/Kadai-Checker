import asyncio
import os
import sys
import webbrowser

from browser_manager import BrowserManager
from scraper import MoodleScraper

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

# コンソール用色付けコード（Windowsの新しいターミナルで動作）
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

async def main():
    print(f"{CYAN}=================================================={RESET}")
    print(f"{CYAN}       Moodle 課題チェックツール (自動起動)       {RESET}")
    print(f"{CYAN}=================================================={RESET}\n")

    browser_mgr = BrowserManager()
    try:
        page = await browser_mgr.start()
        
        # ログイン処理（プロファイルを使っているので既にログイン済みのはず）
        from login import login
        is_logged_in = await login(page)
        
        if not is_logged_in:
            print(f"{RED}ログインに失敗しました。手動でMoodleにログインしてください。{RESET}")
            return

        scraper = MoodleScraper(page)
        assignments = await scraper.run()

        # --- 結果表示 ---
        print("\n\n" + "="*60)
        print(f" {YELLOW}☆ 見つかった課題一覧 ☆{RESET}")
        print("="*60)
        
        unsubmitted = [a for a in assignments if not a.get("submitted")]
        submitted = [a for a in assignments if a.get("submitted")]

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

        print("\n" + "="*60 + "\n")

        return unsubmitted + submitted

    except Exception as e:
        print(f"{RED}エラーが発生しました: {e}{RESET}")
        return []
    finally:
        await browser_mgr.close()

if __name__ == "__main__":
    # WindowsでANSIエスケープシーケンスを有効化
    os.system('color')
    all_tasks = []
    try:
        all_tasks = asyncio.run(main())
    except KeyboardInterrupt:
        pass
    
    print("\nチェックが完了しました。")
    if all_tasks:
        while True:
            print("\n------------------------------------------------------------")
            print("リンクを開きたい場合は、課題の【番号】(1～{})を入力してEnterを押してください。".format(len(all_tasks)))
            print("終了する場合は、何も入力せずにそのままEnterを押してください。")
            choice = input("番号を入力 (終了はEnter): ").strip()
            if not choice:
                break
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(all_tasks):
                    # & を含むURLがエクスプローラ経由で壊れるのを防ぐため、一部カットする
                    safe_url = all_tasks[idx]['url'].split('&')[0]
                    print(f"ブラウザで開きます: {safe_url}")
                    webbrowser.open(safe_url)
                else:
                    print("正しい番号を入力してください。")
            else:
                print("数字を入力してください。")
