"""
browser_manager.py - Chromeブラウザ管理モジュール

実際のGoogle Chromeを起動し、ボット検知を回避する設定を行います。
Chromeプロファイルを保存して、2回目以降のログインを省略できます。
"""

import os
import asyncio
import random
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from dotenv import load_dotenv

load_dotenv()

# 設定値
CHROME_PATH = os.getenv(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
CHROME_PROFILE_DIR = os.getenv(
    "CHROME_PROFILE_DIR",
    "./profiles/kumadai_profile"
)

# よく使われるUser-Agentリスト（Windows + Chrome）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# ボット検知回避のためのJavaScriptコード
STEALTH_JS = """
// navigator.webdriver を隠す
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// Playwrightの痕跡を消す
delete window.__playwright;
delete window.__pw_manual;

// Chrome オブジェクトを偽装する
if (!window.chrome) {
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };
}

// permission情報を自然に見せる
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// plugins情報を追加（本物のChromeっぽく）
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
    configurable: true
});

// languages設定
Object.defineProperty(navigator, 'languages', {
    get: () => ['ja-JP', 'ja', 'en-US', 'en'],
    configurable: true
});
"""


class BrowserManager:
    """
    Chromeブラウザを管理するクラス。
    プロファイルを保存し、ボット検知を回避する設定を行います。
    """

    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self._user_agent = random.choice(USER_AGENTS)

        # プロファイル保存先を絶対パスに変換
        self.profile_dir = Path(CHROME_PROFILE_DIR).resolve()
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> Page:
        """
        Chromeを起動してページオブジェクトを返す。
        プロファイルが存在する場合は再利用する。
        """
        self.playwright = await async_playwright().start()

        # Chromeが存在するか確認
        chrome_path = Path(CHROME_PATH)
        if not chrome_path.exists():
            # よくある別のパスを試す
            alt_paths = [
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Users\Owner\AppData\Local\Google\Chrome\Application\chrome.exe",
            ]
            for alt in alt_paths:
                if Path(alt).exists():
                    chrome_path = Path(alt)
                    break
            else:
                print(f" Chromeが見つかりません。Playwrightのデフォルトブラウザを使用します。")
                chrome_path = None

        # ブラウザ起動オプション
        # 注意: --user-data-dir は user_data_dir 引数で渡すため args に含めない
        launch_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",  # 重要：自動化フラグを隠す
            "--disable-infobars",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={random.randint(1200, 1400)},{random.randint(800, 900)}",
        ]

        try:
            if chrome_path:
                # 実際のChromeを使用（persistent_contextでプロファイル保存）
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    executable_path=str(chrome_path),
                    headless=True,  # 画面非表示（バックグラウンド実行）
                    args=launch_args,
                    user_agent=self._user_agent,
                    viewport={"width": random.randint(1200, 1400), "height": random.randint(800, 900)},
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                    accept_downloads=True,
                )
            else:
                # ChromeがなければPlaywrightのChromiumを使用
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=True,
                    args=launch_args,
                    user_agent=self._user_agent,
                    viewport={"width": 1280, "height": 900},
                    locale="ja-JP",
                    timezone_id="Asia/Tokyo",
                )

            # ステルス設定を適用
            await self.context.add_init_script(STEALTH_JS)

            # 既存のページを使うか新規作成
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()

            print(f" ブラウザ起動完了（User-Agent: {self._user_agent[:50]}...）")
            return self.page

        except Exception as e:
            print(f" ブラウザ起動エラー: {e}")
            raise

    async def close(self) -> None:
        """ブラウザを安全に終了する"""
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
            print(" ブラウザを終了しました")
        except Exception as e:
            print(f" ブラウザ終了時エラー: {e}")

    async def get_page(self) -> Page:
        """現在のページを返す"""
        return self.page

    async def new_tab(self) -> Page:
        """新しいタブを開く"""
        new_page = await self.context.new_page()
        await self.context.add_init_script(STEALTH_JS)
        return new_page
