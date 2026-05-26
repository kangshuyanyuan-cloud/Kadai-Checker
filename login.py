"""
login.py - 熊本大学Moodle ログインモジュール（Shibboleth + CAS対応）

認証フロー:
  Moodle → Shibboleth (shib.kumamoto-u.ac.jp) → CAS (cas.kumamoto-u.ac.jp) → Moodle
"""

import os
import asyncio
import random
from playwright.async_api import Page
from dotenv import load_dotenv
from human_behavior import HumanBehavior
from wait_utils import medium_wait, long_wait, short_wait, think_wait

load_dotenv()

MOODLE_URL    = os.getenv("MOODLE_URL", "https://md.kumamoto-u.ac.jp/")
KUMADAI_ID    = os.getenv("KUMADAI_ID", "")
KUMADAI_PASSWORD = os.getenv("KUMADAI_PASSWORD", "")

MOODLE_DOMAIN = "md.kumamoto-u.ac.jp"
SHIB_DOMAIN   = "shib.kumamoto-u.ac.jp"
CAS_DOMAIN    = "cas.kumamoto-u.ac.jp"


async def is_logged_in(page: Page) -> bool:
    """ログイン済みかどうか確認する（MoodleドメインにいればOK）"""
    try:
        url = page.url
        if MOODLE_DOMAIN in url and SHIB_DOMAIN not in url and CAS_DOMAIN not in url:
            return True
        for selector in ["a[href*='logout']", ".usermenu", "#user-menu-toggle"]:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=1500):
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


async def _fill_and_submit(page: Page, human: HumanBehavior,
                           label: str,
                           id_selectors: list, pw_selectors: list,
                           btn_selectors: list) -> bool:
    """汎用ログインフォーム入力・送信ヘルパー"""
    # ID欄を探す
    id_field = None
    for sel in id_selectors:
        try:
            f = page.locator(sel).first
            if await f.is_visible(timeout=2000):
                id_field = f
                print(f"  [{label}] ID欄: {sel}")
                break
        except Exception:
            pass

    # パスワード欄を探す
    pw_field = None
    for sel in pw_selectors:
        try:
            f = page.locator(sel).first
            if await f.is_visible(timeout=2000):
                pw_field = f
                print(f"  [{label}] PW欄: {sel}")
                break
        except Exception:
            pass

    if not id_field or not pw_field:
        print(f"  [{label}] 入力欄が見つかりません")
        return False

    # ID入力（fill() で特殊文字も正確に入力）
    print(f"  [{label}] ID入力中: {KUMADAI_ID}")
    await human.human_click(id_field)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    await id_field.fill("")
    await id_field.fill(KUMADAI_ID)
    await asyncio.sleep(random.uniform(0.2, 0.5))

    await think_wait()

    # パスワード入力（fill() で $s=&4#75 のような特殊文字も正確に入力）
    print(f"  [{label}] パスワード入力中...")
    await human.human_click(pw_field)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    await pw_field.fill("")
    await pw_field.fill(KUMADAI_PASSWORD)
    await asyncio.sleep(random.uniform(0.2, 0.5))

    await think_wait()

    # ログインボタン
    login_btn = None
    for sel in btn_selectors:
        try:
            b = page.locator(sel).first
            if await b.is_visible(timeout=2000):
                login_btn = b
                print(f"  [{label}] ログインボタン: {sel}")
                break
        except Exception:
            pass

    if not login_btn:
        print(f"  [{label}] ログインボタンが見つかりません")
        return False

    await human.human_click(login_btn)
    print(f"  [{label}] 送信完了。リダイレクト待機中...")
    return True


async def handle_shibboleth(page: Page, human: HumanBehavior) -> bool:
    """Shibboleth認証ページを処理する"""
    if SHIB_DOMAIN not in page.url:
        return True  # Shibbolethにいなければスキップ

    print(f"  Shibboleth認証ページ: {page.url}")
    return await _fill_and_submit(
        page, human, "Shibboleth",
        id_selectors=[
            "input[name='j_username']",
            "input[id='username']",
            "input[type='text']",
        ],
        pw_selectors=[
            "input[name='j_password']",
            "input[id='password']",
            "input[type='password']",
        ],
        btn_selectors=[
            "button[name='_eventId_proceed']",
            "input[name='_eventId_proceed']",
            "input[type='submit']",
            "button[type='submit']",
        ],
    )


async def handle_cas(page: Page, human: HumanBehavior) -> bool:
    """CAS認証ページを処理する"""
    if CAS_DOMAIN not in page.url:
        return True  # CASにいなければスキップ

    print(f"  CAS認証ページ: {page.url}")
    
    # ユーザー選択のラジオボタンがあればチェックする
    try:
        radio = page.locator("input[type='radio'][name='username']").first
        if await radio.is_visible(timeout=2000):
            print("  [CAS] ユーザー選択ラジオボタンをクリックします")
            await human.human_click(radio)
            await asyncio.sleep(random.uniform(0.3, 0.7))
    except Exception:
        pass

    # Submitボタンをクリックする
    try:
        submit_btn = page.locator("input[type='submit'][name='submit']").first
        if await submit_btn.is_visible(timeout=2000):
            print("  [CAS] 送信ボタンをクリックします")
            await human.human_click(submit_btn)
            print("  [CAS] 送信完了。リダイレクト待機中...")
            return True
    except Exception:
        pass

    print("  [CAS] 送信ボタンが見つかりませんでした")
    return False


async def login(page: Page) -> bool:
    """
    熊本大学Moodleにログインする。
    Shibboleth → CAS の2段階認証に対応。

    Returns:
        bool: ログイン成功ならTrue
    """
    human = HumanBehavior(page)
    print("Moodleにアクセス中...")

    # まずダッシュボードへ直接アクセス（プロファイル再利用チェック）
    await page.goto(MOODLE_URL.rstrip("/") + "/my/", wait_until="domcontentloaded")
    await asyncio.sleep(2)

    if await is_logged_in(page):
        print("すでにログイン済みです（プロファイル再利用）")
        return True

    print("ログインが必要です...")

    # ログインページへアクセス
    await page.goto(MOODLE_URL.rstrip("/") + "/login/index.php", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    print(f"  現在のURL: {page.url}")

    # --- 最大5ステップの認証ループ ---
    for step in range(5):
        current_url = page.url
        print(f"\n  [Step {step+1}] URL: {current_url}")

        # Moodleに戻れた → 成功
        if MOODLE_DOMAIN in current_url and SHIB_DOMAIN not in current_url and CAS_DOMAIN not in current_url:
            print("  Moodleへのリダイレクト完了！")
            break

        # Shibbolethページ
        if SHIB_DOMAIN in current_url:
            ok = await handle_shibboleth(page, human)
            if not ok:
                await page.screenshot(path="debug_login_fail.png")
                return False
            # リダイレクト待機（最大30秒）
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            await asyncio.sleep(3)
            continue

        # CASページ
        if CAS_DOMAIN in current_url:
            ok = await handle_cas(page, human)
            if not ok:
                await page.screenshot(path="debug_login_fail.png")
                return False
            # リダイレクト待機（最大30秒）
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            await asyncio.sleep(3)
            continue

        # その他（不明なページ） → 少し待ってリトライ
        print(f"  不明なページです。待機してリトライします...")
        await asyncio.sleep(4)

    # 最終確認
    final_url = page.url
    print(f"\n  最終URL: {final_url}")

    if await is_logged_in(page):
        print("ログイン成功！")
        return True
    else:
        print("ログイン失敗。画面を確認してください。")
        try:
            await page.screenshot(path="debug_login_fail.png")
        except Exception:
            pass
        return False
