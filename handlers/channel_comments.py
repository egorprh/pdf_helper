import json
import logging
import os
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from filters.admin_only import AdminOnly
from filters.private_only import PrivateOnly

logger = logging.getLogger(__name__)

channel_comments_router = Router()


def _channels_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / "channels.json"


def load_channels() -> List[Dict[str, Any]]:
    """Load channel configs from channels.json."""
    path = _channels_file_path()
    if not path.exists():
        logger.warning("channels.json not found at %s", path)
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.error("channels.json root is not a list")
            return []
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load channels.json: %s", exc)
        return []


def save_channels(channels: List[Dict[str, Any]]) -> bool:
    """Persist channel configs to channels.json (atomic write)."""
    path = _channels_file_path()
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save channels.json: %s", exc)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return False


def find_channel_by_id(
    channels: List[Dict[str, Any]], channel_id: int
) -> Optional[Dict[str, Any]]:
    for ch in channels:
        try:
            if int(ch.get("id")) == int(channel_id):
                return ch
        except (TypeError, ValueError):
            continue
    return None


@channel_comments_router.message(
    F.is_automatic_forward, F.sender_chat.type == "channel"
)
async def on_auto_forward_message(message: Message) -> None:
    """Handle auto-forwarded messages in the linked discussion chat.

    Telegram создаёт в связанном чате сервисное сообщение (auto forward) для поста канала.
    Комментарии, которые считаются \"комментами к посту\", — это именно ответы на это сообщение.
    """
    # Нас интересуют только авто-перенаправленные сообщения из каналов
    if not message.is_automatic_forward:
        return
    if not message.sender_chat or message.sender_chat.type != "channel":
        return

    channel_id = message.sender_chat.id
    discussion_chat_id = message.chat.id
    logger.info(
        "Auto-forward from channel %s appeared in chat %s, message_id=%s",
        channel_id,
        discussion_chat_id,
        message.message_id,
    )

    channels = load_channels()
    logger.info("Loaded %d channels from channels.json (auto-forward)", len(channels))

    channel_cfg = find_channel_by_id(channels, channel_id)
    if not channel_cfg:
        logger.info("No config found for channel_id=%s (auto-forward)", channel_id)
        return

    text = (channel_cfg.get("text") or "").strip()
    if not text:
        logger.info(
            "Empty comment text for channel_id=%s, skipping (auto-forward)", channel_id
        )
        return

    try:
        logger.info(
            "Sending reply-comment in discussion chat %s to message_id=%s",
            discussion_chat_id,
            message.message_id,
        )
        # Ответом на авто-перенаправленное сообщение — это и есть \"комментарий к посту\"
        await message.reply(text)
        logger.info(
            "Reply-comment sent successfully to discussion chat %s", discussion_chat_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to send reply-comment in discussion chat %s (channel %s): %s",
            discussion_chat_id,
            channel_id,
            exc,
        )


def _build_channels_list_text(channels: List[Dict[str, Any]]) -> str:
    if not channels:
        return "Список каналов пуст. Добавьте записи в channels.json."

    lines: List[str] = ["Доступные каналы:"]
    for ch in channels:
        cid = ch.get("id")
        name = ch.get("name") or ""
        lines.append(f"ID: <code>{cid}</code> — {name}")
    return "\n".join(lines)


@channel_comments_router.message(PrivateOnly(), AdminOnly(), Command("set_comment"))
async def set_comment(message: Message) -> None:
    """Admin command to change comment text for a specific channel."""
    text = (message.text or "").strip()
    parts = text.split(maxsplit=2)

    # parts: ["/set_comment", "{channel_id}", "{html text}"]
    if len(parts) < 3:
        channels = load_channels()
        help_text = (
            "Команда для установки комментария к постам канала.\n\n"
            "Пример:\n"
            "<code>/set_comment -1003750090568 &lt;b&gt;Ваш текст&lt;/b&gt;</code>\n\n"
        )
        help_text += _build_channels_list_text(channels)
        await message.answer(help_text)
        return

    channel_id_raw = parts[1]
    html_text = parts[2].strip()

    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        channels = load_channels()
        await message.answer(
            "Некорректный ID канала. ID должен быть числом.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    if not html_text:
        channels = load_channels()
        help_text = (
            "Текст комментария не может быть пустым.\n\n"
            "Пример:\n"
            "<code>/set_comment -1003750090568 &lt;b&gt;Ваш текст&lt;/b&gt;</code>\n\n"
        )
        help_text += _build_channels_list_text(channels)
        await message.answer(help_text)
        return

    channels = load_channels()
    channel_cfg = find_channel_by_id(channels, channel_id)
    if not channel_cfg:
        await message.answer(
            "Канал с таким ID не найден в channels.json.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    channel_cfg["text"] = html_text

    if save_channels(channels):
        name = channel_cfg.get("name") or ""
        await message.answer(
            "Текст комментария обновлён.\n\n"
            f"Канал: <b>{escape(str(name))}</b>\n"
            f"ID: <code>{channel_id}</code>"
        )
    else:
        await message.answer("Не удалось сохранить изменения в channels.json.")


@channel_comments_router.message(
    PrivateOnly(), AdminOnly(), Command("add_comment_channel")
)
async def add_comment_channel(message: Message) -> None:
    """Admin command to add a new channel entry to channels.json."""
    text = (message.text or "").strip()
    parts = text.split(maxsplit=2)

    # parts: ["/add_comment_channel", "{channel_id}", "{name}"]
    if len(parts) < 3:
        channels = load_channels()
        help_text = (
            "Команда для добавления нового канала в список.\n\n"
            "Пример:\n"
            "<code>/add_comment_channel -1003750090568 Ростислав Dept FX Chat</code>\n\n"
            "Не забудьте добавить бота админом в канал и связанный чат"
        )
        help_text += _build_channels_list_text(channels)
        await message.answer(help_text)
        return

    channel_id_raw = parts[1]
    name = parts[2].strip()

    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        channels = load_channels()
        await message.answer(
            "Некорректный ID канала. ID должен быть числом.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    if not name:
        channels = load_channels()
        help_text = (
            "Имя канала не может быть пустым.\n\n"
            "Пример:\n"
            "<code>/add_comment_channel -1003750090568 Ростислав Dept FX Chat</code>\n\n"
        )
        help_text += _build_channels_list_text(channels)
        await message.answer(help_text)
        return

    channels = load_channels()
    existing = find_channel_by_id(channels, channel_id)
    if existing:
        await message.answer(
            "Канал с таким ID уже есть в списке.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    channels.append(
        {
            "id": channel_id,
            "name": name,
            "url": "",
            "text": "",
        }
    )

    if save_channels(channels):
        await message.answer(
            "Канал добавлен в список.\n\n"
            f"Канал: <b>{escape(name)}</b>\n"
            f"ID: <code>{channel_id}</code>"
        )
    else:
        await message.answer("Не удалось сохранить изменения в channels.json.")


@channel_comments_router.message(PrivateOnly(), AdminOnly(), Command("rm_channel"))
async def rm_channel(message: Message) -> None:
    """Admin command to remove a channel entry from channels.json by id."""
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)

    # parts: ["/rm_channel", "{channel_id}"]
    if len(parts) < 2:
        channels = load_channels()
        help_text = (
            "Команда для удаления канала из списка.\n\n"
            "Пример:\n"
            "<code>/rm_channel -1003750090568</code>\n\n"
        )
        help_text += _build_channels_list_text(channels)
        await message.answer(help_text)
        return

    channel_id_raw = parts[1].strip()
    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        channels = load_channels()
        await message.answer(
            "Некорректный ID канала. ID должен быть числом.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    channels = load_channels()
    before_count = len(channels)
    channels = [ch for ch in channels if int(ch.get("id", 0)) != channel_id]

    if len(channels) == before_count:
        await message.answer(
            "Канал с таким ID не найден в channels.json.\n\n"
            + _build_channels_list_text(channels)
        )
        return

    if save_channels(channels):
        await message.answer(
            "Канал удалён из списка.\n\nID: <code>{}</code>".format(channel_id)
        )
    else:
        await message.answer("Не удалось сохранить изменения в channels.json.")


@channel_comments_router.message(
    PrivateOnly(), AdminOnly(), Command("get_comment_channels")
)
async def get_channels(message: Message) -> None:
    """Admin command to send current channels.json as a file."""
    path = _channels_file_path()
    if not path.exists():
        await message.answer("Файл channels.json не найден.")
        return

    try:
        await message.answer_document(
            document=FSInputFile(str(path), filename="channels.json"),
            caption="Текущий файл channels.json",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send channels.json: %s", exc)
        await message.answer("Не удалось отправить файл channels.json.")


@channel_comments_router.message(PrivateOnly(), AdminOnly(), Command("get_raw_html"))
async def get_raw_html(message: Message) -> None:
    """Return raw HTML representation of the replied message."""
    reply = message.reply_to_message
    if not reply:
        await message.answer(
            "Используйте команду в ответ на сообщение, "
            "чтобы получить его HTML-представление."
        )
        return

    raw_html = reply.html_text or reply.text or ""
    if not raw_html:
        await message.answer("Не удалось получить HTML для этого сообщения.")
        return

    escaped = escape(raw_html)
    # Отправляем только код-блок, чтобы Телеграм позволял удобно копировать содержимое
    await message.answer(f"<pre>{escaped}</pre>")
