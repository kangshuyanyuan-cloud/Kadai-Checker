"""
browser_manager.py - Chromeブラウザ管理モジュール

実際のGoogle Chromeを起動し、ボット検知を回避する設定を行います。
Chromeプロファイルを保存して、2回目以降のログインを省略できます。
"""

import os
import shutil
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


def _find_chrome() -> Path | None:
    """Chromeの実行ファイルを探す"""
    chrome_path = Path(CHROME_PATH)
    if chrome_path.exists():
        return chrome_path

    # よくある別のパスを試す
    alt_paths = [
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\Owner\AppData\Local\Google\Chrome\Application\chrome.exe",
    ]
    for alt in alt_paths:
        if Path(alt).exists():
            return Path(alt)

    return None


def _clean_profile_locks(profile_dir: Path) -> None:
    """プロファイルのロックファイルを削除する（前回の異常終了対策）"""
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    for lock_name in lock_files:
        lock_path = profile_dir / lock_name
        try:
            if lock_path.exists():
                lock_path.unlink()
                print(f"  ロックファイルを削除しました: {lock_name}")
        except Exception:
            pass


class BrowserManager:
    """
    Chromeブラウザを管理するクラス。
    プロファイルを保存し、ボット検知を回避する設定を行います。
    起動失敗時はプロファイルをリセットして自動リトライします。
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

    async def _launch_context(self, chrome_path: Path | None, use_profile: bool = True) -> BrowserContext:
        """
        ブラウザコンテキストを起動する。

        Args:
            chrome_path: Chromeの実行ファイルパス（Noneの場合はPlaywrightのChromiumを使用）
            use_profile: プロファイルを使うかどうか（壊れた場合はFalseで起動）
        """
        # ブラウザ起動オプション
        launch_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",  # 重要：自動化フラグを隠す
            "--disable-infobars",
            "--disable-extensions",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--ignore-certificate-errors",           # SSL証明書エラーを無視（追加対策）
            "--ignore-ssl-errors=yes",               # SSLエラーを無視（追加対策）
            "--allow-insecure-localhost",             # ローカルのSSLエラーも無視
            f"--window-size={random.randint(1200, 1400)},{random.randint(800, 900)}",
        ]

        user_data_dir = str(self.profile_dir) if use_profile else str(self.profile_dir.parent / "temp_profile")

        common_opts = {
            "user_data_dir": user_data_dir,
            "headless": False,
            "args": launch_args,
            "user_agent": self._user_agent,
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
            "ignore_https_errors": True,  # SSL証明書エラーを無視する
        }

        if chrome_path:
            common_opts["executable_path"] = str(chrome_path)
            common_opts["viewport"] = {"width": random.randint(1200, 1400), "height": random.randint(800, 900)}
            common_opts["accept_downloads"] = True
        else:
            common_opts["viewport"] = {"width": 1280, "height": 900}

        return await self.playwright.chromium.launch_persistent_context(**common_opts)

    async def start(self) -> Page:
        """
        Chromeを起動してページオブジェクトを返す。
        プロファイルが存在する場合は再利用する。
        起動に失敗した場合は、プロファイルをリセットして再試行する。
        """
        self.playwright = await async_playwright().start()

        chrome_path = _find_chrome()
        if not chrome_path:
            print("  Chromeが見つかりません。Playwrightのデフォルトブラウザを使用します。")

        # ロックファイルを削除（前回の異常終了対策）
        _clean_profile_locks(self.profile_dir)

        # --- 試行1: 通常起動（プロファイル付き）---
        try:
            self.context = await self._launch_context(chrome_path, use_profile=True)
        except Exception as e1:
            print(f"  ブラウザ起動失敗（1回目）: {e1}")
            print("  プロファイルをリセットして再試行します...")

            # プロファイルをリセット
            try:
                if self.profile_dir.exists():
                    shutil.rmtree(self.profile_dir, ignore_errors=True)
                self.profile_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            # --- 試行2: プロファイルリセット後の再起動 ---
            try:
                # Playwrightを再起動
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = await async_playwright().start()

                self.context = await self._launch_context(chrome_path, use_profile=True)
            except Exception as e2:
                print(f"  ブラウザ起動失敗（2回目）: {e2}")

                # --- 試行3: Chromeの代わりにPlaywrightのChromiumを使う ---
                if chrome_path:
                    print("  Playwrightのデフォルトブラウザで再試行します...")
                    try:
                        try:
                            await self.playwright.stop()
                        except Exception:
                            pass
                        self.playwright = await async_playwright().start()

                        self.context = await self._launch_context(None, use_profile=False)
                    except Exception as e3:
                        print(f"  ブラウザ起動失敗（3回目）: {e3}")
                        raise RuntimeError(
                            "ブラウザを起動できませんでした。\n"
                            "以下を確認してください:\n"
                            "  1. Google Chromeが正しくインストールされているか\n"
                            "  2. 他のChromeプロセスが動いていないか（タスクマネージャーで確認）\n"
                            "  3. profiles フォルダを手動で削除して再試行\n"
                            f"  元のエラー: {e3}"
                        ) from e3
                else:
                    raise RuntimeError(
                        "ブラウザを起動できませんでした。\n"
                        f"  元のエラー: {e2}"
                    ) from e2

        # ステルス設定を適用
        await self.context.add_init_script(STEALTH_JS)

        # 既存のページを使うか新規作成
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        print(f" ブラウザ起動完了（User-Agent: {self._user_agent[:50]}...）")
        return self.page

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

        # 一時プロファイルを削除
        temp_profile = self.profile_dir.parent / "temp_profile"
        if temp_profile.exists():
            try:
                shutil.rmtree(temp_profile, ignore_errors=True)
            except Exception:
                pass

    async def get_page(self) -> Page:
        """現在のページを返す"""
        return self.page

    async def new_tab(self) -> Page:
        """新しいタブを開く"""
        new_page = await self.context.new_page()
        await self.context.add_init_script(STEALTH_JS)
        return new_page
