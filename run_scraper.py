"""
run_scraper.py - 課題収集メインスクリプト（実行用）
"""
import asyncio
import sys
import os
import json

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

os.chdir(r'C:\Users\Owner\.gemini\antigravity\scratch\kumadai-moodle')
sys.path.insert(0, r'C:\Users\Owner\.gemini\antigravity\scratch\kumadai-moodle')


async def run():
    from dotenv import load_dotenv
    load_dotenv()

    from browser_manager import BrowserManager
    from login import login
    from scraper import MoodleScraper

    browser_mgr = BrowserManager()

    try:
        print("ブラウザを起動中...")
        page = await browser_mgr.start()

        print("ログイン処理開始...")
        login_success = await login(page)

        if not login_success:
            print("LOGIN_FAILED")
            await browser_mgr.close()
            return []

        print("ログイン成功！課題収集を開始します...")
        scraper = MoodleScraper(page)
        assignments = await scraper.run()

        # 結果をJSONで保存
        with open("assignments_result.json", "w", encoding="utf-8") as f:
            json.dump(assignments, f, ensure_ascii=False, indent=2)

        print(f"\nDONE: {len(assignments)} 件の課題を収集しました")
        print("assignments_result.json に保存しました")

        # 結果を表示
        print("\n" + "=" * 60)
        print("  課題一覧")
        print("=" * 60)

        not_submitted = [a for a in assignments if not a.get("submitted", False)]
        submitted = [a for a in assignments if a.get("submitted", False)]

        print(f"  合計: {len(assignments)} 件")
        print(f"  未提出: {len(not_submitted)} 件")
        print(f"  提出済み: {len(submitted)} 件")

        if not_submitted:
            print("\n--- 未提出 ---")
            for a in not_submitted:
                print(f"  [{a['type']}] {a['title'][:50]}")
                print(f"    コース: {a['course'][:50]}")
                print(f"    締切: {a['deadline'] or '不明'}")
                print(f"    URL: {a['url']}")
                print()

        if submitted:
            print("\n--- 提出済み ---")
            for a in submitted:
                print(f"  [{a['type']}] {a['title'][:50]}")
                print(f"    コース: {a['course'][:50]}")
                print(f"    締切: {a['deadline'] or '不明'}")
                print()

        print("Enterキーを押すとブラウザを閉じます...")
        input()
        await browser_mgr.close()
        return assignments

    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        await browser_mgr.close()
        return []


if __name__ == "__main__":
    asyncio.run(run())
