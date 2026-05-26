"""
notifier.py - 通知モジュール（将来拡張用）

LINEやDiscord、メール通知を追加しやすい構造にしています。
現時点ではターミナル出力のみ対応。

将来的な追加例:
  - LINE Notify
  - Discord Webhook
  - メール通知
  - Windows Toast通知
"""

import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# 将来的な通知設定（.envに追加してください）
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


class Notifier:
    """
    通知を管理するクラス。
    複数の通知先を一括管理できます。
    """

    def __init__(self):
        self.enabled_channels = []

        # LINE通知が設定されていれば有効化
        if LINE_NOTIFY_TOKEN:
            self.enabled_channels.append("line")

        # Discord通知が設定されていれば有効化
        if DISCORD_WEBHOOK_URL:
            self.enabled_channels.append("discord")

    async def notify_new_assignments(self, assignments: List[Dict[str, Any]]) -> None:
        """
        新しい課題の通知を全チャンネルに送る。
        """
        if not assignments:
            return

        message = self._format_notification_message(assignments)

        for channel in self.enabled_channels:
            if channel == "line":
                await self._send_line_notify(message)
            elif channel == "discord":
                await self._send_discord_notify(message, assignments)

    def _format_notification_message(self, assignments: List[Dict[str, Any]]) -> str:
        """通知メッセージを整形する"""
        lines = [" Moodle課題通知", "=" * 30]

        for a in assignments[:5]:  # 最大5件
            status = "未提出" if not a.get("submitted") else "提出済"
            lines.append(f"{status} {a['title']}")
            if a.get("deadline"):
                lines.append(f"  締切: {a['deadline']}")
            lines.append("")

        if len(assignments) > 5:
            lines.append(f"... 他 {len(assignments) - 5} 件")

        return "\n".join(lines)

    async def _send_line_notify(self, message: str) -> None:
        """
        LINE Notifyに通知を送る。

        使い方:
        1. https://notify-bot.line.me/ でトークンを取得
        2. .envに LINE_NOTIFY_TOKEN=<token> を追加
        """
        try:
            import aiohttp
            url = "https://notify-api.line.me/api/notify"
            headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
            data = {"message": message}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as resp:
                    if resp.status == 200:
                        print(" LINE通知を送信しました")
                    else:
                        print(f" LINE通知エラー: {resp.status}")
        except ImportError:
            print(" LINE通知にはaiohttp が必要です: pip install aiohttp")
        except Exception as e:
            print(f" LINE通知エラー: {e}")

    async def _send_discord_notify(self, message: str, assignments: List[Dict[str, Any]]) -> None:
        """
        Discord Webhookに通知を送る。

        使い方:
        1. Discordのチャンネル設定  Webhookを作成
        2. .envに DISCORD_WEBHOOK_URL=<url> を追加
        """
        try:
            import aiohttp

            # Discord用のEmbedメッセージを作成
            embeds = []
            for a in assignments[:5]:
                color = 0xFF4444 if not a.get("submitted") else 0x44FF44
                embed = {
                    "title": a["title"],
                    "description": f"コース: {a['course']}",
                    "color": color,
                    "fields": [],
                }

                if a.get("deadline"):
                    embed["fields"].append({
                        "name": "締切",
                        "value": a["deadline"],
                        "inline": True,
                    })

                embed["fields"].append({
                    "name": "状態",
                    "value": " 未提出" if not a.get("submitted") else " 提出済",
                    "inline": True,
                })

                if a.get("url"):
                    embed["url"] = a["url"]

                embeds.append(embed)

            payload = {
                "content": " Moodle課題情報",
                "embeds": embeds,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(DISCORD_WEBHOOK_URL, json=payload) as resp:
                    if resp.status in (200, 204):
                        print(" Discord通知を送信しました")
                    else:
                        print(f" Discord通知エラー: {resp.status}")

        except ImportError:
            print(" Discord通知にはaiohttp が必要です: pip install aiohttp")
        except Exception as e:
            print(f" Discord通知エラー: {e}")
