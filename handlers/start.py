"""
Start command handler.
"""
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import Database

logger = logging.getLogger(__name__)
db = Database()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    try:
        user = update.effective_user
        if not user:
            # Defensive: if no user info, just acknowledge
            await (update.effective_message or update.callback_query.message).reply_text(
                "Hello! How can I help you?"
            )
            return

        # Track user (username/first/last may be None)
        await db.track_user(
            user_id=user.id,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
        )

        # Check subscription status
        is_subscribed = await db.is_user_subscribed(user.id)

        welcome_text = (
            f"👋 Welcome, {user.first_name or ''}!\n\n"
            "I'm your media product catalog bot. I help you browse and search "
            "products from our catalog.\n\n"
            "Use /menu to view all products or simply type what you're looking for!\n\n"
            "DM @OTplug_Ghost TO ORDER"
        )

        keyboard_buttons = [[InlineKeyboardButton("📋 View Catalog", callback_data="categories")]]

        # Add resubscribe button only for users who have unsubscribed
        if not is_subscribed:
            keyboard_buttons.append(
                [InlineKeyboardButton("🔔 Resubscribe to Notifications", callback_data="toggle_notifications")]
            )

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        # Send plain text (no parse_mode) to avoid entity parsing issues with user names
        if update.effective_message:
            await update.effective_message.reply_text(welcome_text, reply_markup=keyboard)
        else:
            # fallback
            await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text, reply_markup=keyboard)

        logger.info(f"User {user.id} started the bot")
    except Exception as e:
        logger.exception("Error in start_command: %s", e)
        try:
            if update.effective_message:
                await update.effective_message.reply_text("❌ An error occurred while processing /start")
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ An error occurred while processing /start")
        except Exception:
            logger.exception("Failed to notify user after start_command error")


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - enable product notifications."""
    try:
        user = update.effective_user
        if not user:
            return

        user_id = user.id

        # Track user
        await db.track_user(
            user_id=user_id,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
        )

        # Enable notifications
        await db.set_user_notifications(user_id, True)

        # Send plain text to avoid markdown parsing issues
        await (update.effective_message or context.bot.send_message)(
            chat_id=update.effective_chat.id,
            text=(
                "🔔 Notifications Enabled!\n\n"
                "You will now receive notifications when new products are added to the catalog.\n\n"
                "Use /unsubscribe to stop receiving notifications."
            ),
        )

        logger.info(f"User {user_id} subscribed to notifications")
    except Exception as e:
        logger.exception("Error in subscribe_command: %s", e)
        try:
            if update.effective_message:
                await update.effective_message.reply_text("❌ Failed to enable notifications")
        except Exception:
            logger.exception("Failed to notify user after subscribe_command error")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command - disable product notifications."""
    try:
        user = update.effective_user
        if not user:
            return

        user_id = user.id

        # Disable notifications
        await db.set_user_notifications(user_id, False)

        await (update.effective_message or context.bot.send_message)(
            chat_id=update.effective_chat.id,
            text=(
                "🔕 Notifications Disabled\n\n"
                "You will no longer receive notifications about new products.\n\n"
                "Use /subscribe to enable notifications again."
            ),
        )

        logger.info(f"User {user_id} unsubscribed from notifications")
    except Exception as e:
        logger.exception("Error in unsubscribe_command: %s", e)
        try:
            if update.effective_message:
                await update.effective_message.reply_text("❌ Failed to disable notifications")
        except Exception:
            logger.exception("Failed to notify user after unsubscribe_command error")