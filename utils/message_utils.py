from typing import Optional, List, Any
from maxapi.types import Message
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.input_media import InputMedia, InputMediaBuffer
from maxapi.types import MessageCreated, MessageCallback


async def update_menu(context, source_message: Any, text: Optional[str] = None,
                      attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None):
    """
    Try to update a single 'menu' message across the conversation.

    Strategy:
    - If context contains 'menu_mid', try to call bot.edit_message(menu_mid, ...).
    - Else try to call source_message.edit(...) (works for callback messages).
    - If both fail, send a new message with source_message.answer(...) and store its mid in context.

    Returns the result of the operation (EditedMessage or SendedMessage) or None.
    """
    try:
        data = await context.get_data() or {}
    except Exception:
        data = {}

    bot = getattr(source_message, 'bot', None) or getattr(source_message, 'message', None) and getattr(source_message.message, 'bot', None)

    menu_mid = data.get('menu_mid')
    # 1) try bot.edit_message by stored mid
    if menu_mid and bot:
        try:
            res = await bot.edit_message(message_id=menu_mid, text=text, attachments=attachments) # type: ignore
            return res
        except Exception:
            # fall through to other options
            pass

    # 2) try to edit the provided source_message (works for callback.message)
    try:
        res = await source_message.edit(text=text, attachments=attachments) # type: ignore
        # store mid in context if possible
        try:
            mid = source_message.body.mid
            data['menu_mid'] = mid
            await context.set_data(data)
        except Exception:
            pass
        return res
    except Exception:
        pass

    # 3) fallback: send new message and remember its mid
    try:
        sent = await source_message.answer(text=text, attachments=attachments) # type: ignore
        try:
            mid = sent.message.mid
            data['menu_mid'] = mid
            await context.set_data(data)
        except Exception:
            pass
        return sent
    except Exception:
        return None
