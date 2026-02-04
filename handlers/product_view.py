"""
Product view handler.
"""
import logging
import json
import inspect
from typing import Any, Dict, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import ContextTypes

from database import Database
from utils.helpers import send_media_message, is_admin
from utils.categories import format_category_info

logger = logging.getLogger(__name__)
db = Database()


async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    """Show a single product with media and details."""
    try:
        product: Optional[Dict[str, Any]] = await db.get_product(product_id)

        if not product:
            if update.callback_query:
                await update.callback_query.answer("❌ Product not found.", show_alert=True)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Product not found.")
            return

        # Get user's pagination state to determine back button behavior
        user_id = update.effective_user.id

        latest_state = await db.get_latest_pagination_state(user_id)

        back_callback = "menu|1"  # Default fallback

        if latest_state and "state_type" in latest_state and "page" in latest_state:
            state_type = latest_state["state_type"]
            page = latest_state["page"]
            query = latest_state.get("query", "")

            if state_type.startswith("subcategory_"):
                parts = state_type.split("_", 2)
                if len(parts) >= 3:
                    category = parts[1]
                    subcategory = parts[2]
                    back_callback = f"subcategory|{category}|{subcategory}|{page}"
                else:
                    back_callback = "menu|1"
            elif state_type.startswith("category_"):
                parts = state_type.split("_", 1)
                if len(parts) >= 2:
                    category = parts[1]
                    back_callback = f"category|{category}|{page}"
                else:
                    back_callback = "menu|1"
            elif state_type == "search":
                if query:
                    safe_query = query.replace("|", "_PIPE_")
                    max_query_len = 64 - 16
                    if len(safe_query) > max_query_len:
                        safe_query = safe_query[:max_query_len]
                    back_callback = f"page|search|{safe_query}|{page}"
                else:
                    back_callback = "menu|1"
            elif state_type == "catalog":
                back_callback = f"menu|{page}"
            else:
                back_callback = "menu|1"
        else:
            # No pagination state found - fallback using product categories
            product_category = product.get("category")
            product_subcategory = product.get("subcategory")

            if product_category and product_subcategory:
                back_callback = f"subcategory|{product_category}|{product_subcategory}|1"
            elif product_category:
                back_callback = f"category|{product_category}|1"

        # Create keyboard
        keyboard_buttons = [[InlineKeyboardButton("🔙 Back to results", callback_data=back_callback)]]

        # is_admin may be sync or async; handle both
        admin_check = is_admin(user_id)
        is_user_admin = await admin_check if inspect.isawaitable(admin_check) else admin_check

        if is_user_admin:
            keyboard_buttons.append(
                [
                    InlineKeyboardButton("🔄 Recategorize", callback_data=f"recategorize|{product_id}"),
                    InlineKeyboardButton("🗑 Delete this product", callback_data=f"delete|{product_id}"),
                ]
            )

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        caption = product.get("caption") or "No description"
        category_info = format_category_info(product.get("category"), product.get("subcategory"))
        full_caption = f"{caption}\n\n📂 {category_info}"

        additional_file_ids = product.get("additional_file_ids")

        if additional_file_ids:
            try:
                file_data = json.loads(additional_file_ids)
                media_list = []

                first_type = product.get("file_type")
                first_id = product.get("file_id")

                if first_type == "photo":
                    media_list.append(InputMediaPhoto(media=first_id, caption=full_caption))
                elif first_type == "video":
                    media_list.append(InputMediaVideo(media=first_id, caption=full_caption))
                else:
                    # fallback to single media send for unsupported first type
                    await send_media_message(
                        context,
                        update.effective_chat.id,
                        first_id,
                        first_type,
                        caption=full_caption,
                        reply_markup=keyboard,
                    )
                    if update.callback_query:
                        await update.callback_query.answer()
                    return

                for item in file_data:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        file_id, file_type = item[0], item[1]
                    elif isinstance(item, dict):
                        file_id = item.get("file_id") or item.get("id") or item.get("file")
                        file_type = item.get("file_type") or item.get("type")
                    else:
                        continue

                    if file_type == "photo":
                        media_list.append(InputMediaPhoto(media=file_id))
                    elif file_type == "video":
                        media_list.append(InputMediaVideo(media=file_id))
                    else:
                        # skip unsupported types in album
                        continue

                if media_list:
                    await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_list)

                    # media groups can't have inline keyboards; send keyboard in a separate message
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="👆 DM TO ORDER:@OTplug_Ghost",
                        reply_markup=keyboard,
                    )

                    if update.callback_query:
                        await update.callback_query.answer()
                    return

            except Exception as e:
                logger.exception("Error sending media group, falling back to single media: %s", e)
                # fall back to single-media path below

        # Single media path (or fallback)
        await send_media_message(
            context,
            update.effective_chat.id,
            product.get("file_id"),
            product.get("file_type"),
            caption=full_caption,
            reply_markup=None,
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="👆 DM TO ORDER:@OTplug_Ghost",
            reply_markup=keyboard,
        )

        if update.callback_query:
            await update.callback_query.answer()

    except Exception as e:
        logger.exception("Error showing product: %s", e)
        # Defensive failure notification
        try:
            if update.callback_query:
                await update.callback_query.answer("❌ An error occurred while loading the product.", show_alert=True)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ An error occurred while loading the product.")
        except Exception:
            logger.exception("Failed to notify user about the product display error")


async def handle_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product button callback."""
    try:
        if not update.callback_query or not update.callback_query.data:
            if update.callback_query:
                await update.callback_query.answer("Invalid callback data", show_alert=True)
            return

        callback_data = update.callback_query.data
        parts = callback_data.split("|")

        if len(parts) == 2 and parts[0] == "product":
            try:
                product_id = int(parts[1])
            except (ValueError, TypeError):
                await update.callback_query.answer("Invalid product id", show_alert=True)
                return
            await show_product(update, context, product_id)
        else:
            await update.callback_query.answer("Invalid callback data", show_alert=True)
    except Exception as e:
        logger.exception("Error handling product callback: %s", e)
        if update.callback_query:
            try:
                await update.callback_query.answer("❌ Internal error", show_alert=True)
            except Exception:
                logger.exception("Failed to answer product callback after error")