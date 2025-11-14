from typing import Optional, List, Any
from maxapi.types import Message
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.input_media import InputMedia, InputMediaBuffer
from maxapi.types import MessageCreated, MessageCallback


async def update_menu(
    context,
    source_message: Any,
    text: Optional[str] = None,
    attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
):
    try:
        data = await context.get_data() or {}
    except Exception:
        data = {}

    bot = (
        getattr(source_message, "bot", None)
        or getattr(source_message, "message", None)
        and getattr(source_message.message, "bot", None)
    )

    menu_mid = data.get("menu_mid")
    if menu_mid and bot:
        try:
            res = await bot.edit_message(message_id=menu_mid, text=text, attachments=attachments)  # type: ignore
            return res
        except Exception:
            pass
    try:
        res = await source_message.edit(text=text, attachments=attachments)  # type: ignore
        try:
            mid = source_message.body.mid
            data["menu_mid"] = mid
            await context.set_data(data)
        except Exception:
            pass
        return res
    except Exception:
        pass
    try:
        sent = await source_message.answer(text=text, attachments=attachments)  # type: ignore
        try:
            mid = sent.message.mid
            data["menu_mid"] = mid
            await context.set_data(data)
        except Exception:
            pass
        return sent
    except Exception:
        return None
