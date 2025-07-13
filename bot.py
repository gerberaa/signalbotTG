import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import re

from config import BOT_TOKEN, DARK_EMOJIS
from database import Database
from crypto_api import CryptoAPI
from monitor import PriceMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Initialize database and API
db = Database()
crypto_api = CryptoAPI()
monitor = None

# FSM States for adding alerts
class AlertStates(StatesGroup):
    waiting_for_ticker = State()
    waiting_for_type = State()
    waiting_for_price = State()

# FSM States for deleting alerts
class DeleteStates(StatesGroup):
    waiting_for_choice = State()

# Додаємо кнопку в усі місця, де формується головне меню
# (оновлюю два місця: cmd_start, cmd_main_menu, back_to_menu_callback)
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=f"{DARK_EMOJIS['add']} Add Coin")],
        [KeyboardButton(text=f"{DARK_EMOJIS['list']} My Alerts")],
        [KeyboardButton(text=f"{DARK_EMOJIS['coin']} Current Prices")],
        [KeyboardButton(text=f"{DARK_EMOJIS['delete']} Delete Alert")],
        [KeyboardButton(text="⚡ Auto-Alerts")],
        [KeyboardButton(text="❓ Help")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Choose an action..."
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command - user registration"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    first_name = message.from_user.first_name or "Anonymous"
    
    # Register user
    success = db.add_user(user_id, username, first_name)
    
    if success:
        welcome_message = (
            f"{DARK_EMOJIS['bot']} **ShadowPrice Bot**\n\n"
            f"👋 Hello, **{first_name}**! Ready to send you crypto signals.\n\n"
            f"**Use the buttons below to control the bot:**\n"
            f"➕ **Add Coin** - create a new alert\n"
            f"📋 **My Alerts** - view your active alerts\n"
            f"💰 **Current Prices** - see your coins' prices\n"
            f"❌ **Delete Alert** - remove an alert\n"
            f"⚡ **Auto-Alerts** - push notifications for price spikes\n"
            f"❓ **Help** - instructions\n"
            f"🏠 **Main Menu** - return to main menu\n\n"
            f"{DARK_EMOJIS['shadow']} *Dark monitoring enabled*"
        )
        
        # Create main menu keyboard
        await message.answer(welcome_message, parse_mode="Markdown", reply_markup=main_menu_keyboard)
    else:
        await message.answer(f"{DARK_EMOJIS['error']} Registration error. Please try again.")

@dp.message(F.text == "🏠 Main Menu")
async def cmd_main_menu(message: types.Message):
    """Return to main menu"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    first_name = user['first_name'] if user else "User"
    
    welcome_message = (
        f"{DARK_EMOJIS['bot']} **ShadowPrice Bot**\n\n"
        f"👋 Hello, **{first_name}**! Ready to send you crypto signals.\n\n"
        f"**Use the buttons below to control the bot:**\n"
        f"➕ **Add Coin** - create a new alert\n"
        f"📋 **My Alerts** - view your active alerts\n"
        f"💰 **Current Prices** - see your coins' prices\n"
        f"❌ **Delete Alert** - remove an alert\n"
        f"⚡ **Auto-Alerts** - push notifications for price spikes\n"
        f"❓ **Help** - instructions\n"
        f"🏠 **Main Menu** - return to main menu\n\n"
        f"{DARK_EMOJIS['shadow']} *Dark monitoring enabled*"
    )
    
    await message.answer(welcome_message, parse_mode="Markdown", reply_markup=main_menu_keyboard)

@dp.message(F.text == f"{DARK_EMOJIS['add']} Add Coin")
async def cmd_add_alert(message: types.Message, state: FSMContext):
    """Start adding a new alert"""
    await state.set_state(AlertStates.waiting_for_ticker)
    
    await message.answer(
        f"{DARK_EMOJIS['coin']} **Add Coin**\n\n"
        f"Enter the coin ticker (e.g., BTC, ETH, SOL):",
        parse_mode="Markdown"
    )

@dp.message(AlertStates.waiting_for_ticker)
async def process_ticker(message: types.Message, state: FSMContext):
    """Process coin ticker input"""
    ticker = message.text.strip().upper()
    
    # Check for back to menu
    if ticker.lower() in ['back', 'menu', '🏠', 'main menu']:
        await state.clear()
        await cmd_main_menu(message)
        return
    
    # Validate ticker
    if len(ticker) < 2 or len(ticker) > 10:
        await message.answer(
            f"{DARK_EMOJIS['warning']} Ticker must be 2-10 characters. Try again.\n\n"
            f"💡 Type 'back' to return to the menu.",
            parse_mode="Markdown"
        )
        return
    
    await state.update_data(ticker=ticker)
    await state.set_state(AlertStates.waiting_for_type)
    
    # Показуємо прогрес-бар
    loading_msg = await message.answer(
        f"⏳ **Checking price...**\n\nPlease wait, querying CoinGecko...",
        parse_mode="Markdown"
    )
    progress_task = asyncio.create_task(progress_bar_updater(loading_msg))
    try:
        current_price = await crypto_api.get_coin_price(ticker)
        progress_task.cancel()
    except Exception:
        current_price = None
        progress_task.cancel()
    if current_price:
        price_info = f"💰 Current price: ${current_price:,.2f}\n\n"
    else:
        price_info = f"⚠️ Failed to get current price for {ticker}\n\n"
    
    # Create threshold type keyboard with back button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{DARK_EMOJIS['up']} Above", callback_data="type_above"),
            InlineKeyboardButton(text=f"{DARK_EMOJIS['down']} Below", callback_data="type_below")
        ],
        [InlineKeyboardButton(text="🏠 Back to menu", callback_data="back_to_menu")]
    ])
    
    await loading_msg.edit_text(
        f"{DARK_EMOJIS['coin']} **{ticker}**\n"
        f"{price_info}"
        f"Select threshold type:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("type_"))
async def process_threshold_type(callback: types.CallbackQuery, state: FSMContext):
    """Process threshold type selection"""
    threshold_type = callback.data.split("_")[1]
    
    await state.update_data(threshold_type=threshold_type)
    await state.set_state(AlertStates.waiting_for_price)
    
    # Get ticker from state
    data = await state.get_data()
    ticker = data['ticker']
    
    # Get current price for the coin
    current_price = await crypto_api.get_coin_price(ticker)
    
    # Create keyboard with back button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Back to menu", callback_data="back_to_menu")]
    ])
    
    if current_price:
        price_info = f"💰 **Current {ticker} price:** ${current_price:,.2f}\n\n"
    else:
        price_info = f"⚠️ Failed to get current price for {ticker}\n\n"
    
    await callback.message.edit_text(
        f"{DARK_EMOJIS['coin']} **Price Threshold**\n\n"
        f"{price_info}"
        f"Enter your target price (e.g., 30000):\n\n"
        f"💡 Type 'back' to return to the menu.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    """Handle back to menu callback"""
    await state.clear()
    await callback.message.delete()
    
    # Create a new message to simulate the main menu
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    first_name = user['first_name'] if user else "User"
    
    welcome_message = (
        f"{DARK_EMOJIS['bot']} **ShadowPrice Bot**\n\n"
        f"👋 Hello, **{first_name}**! Ready to send you crypto signals.\n\n"
        f"**Use the buttons below to control the bot:**\n"
        f"➕ **Add Coin** - create a new alert\n"
        f"📋 **My Alerts** - view your active alerts\n"
        f"💰 **Current Prices** - see your coins' prices\n"
        f"❌ **Delete Alert** - remove an alert\n"
        f"⚡ **Auto-Alerts** - push notifications for price spikes\n"
        f"❓ **Help** - instructions\n"
        f"🏠 **Main Menu** - return to main menu\n\n"
        f"{DARK_EMOJIS['shadow']} *Dark monitoring enabled*"
    )
    
    await callback.message.answer(welcome_message, parse_mode="Markdown", reply_markup=main_menu_keyboard)

@dp.message(AlertStates.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    """Process price input and save alert"""
    # Check for back to menu
    if message.text.lower() in ['back', 'menu', '🏠', 'main menu']:
        await state.clear()
        await cmd_main_menu(message)
        return
    
    try:
        price = float(message.text.replace(',', ''))
        if price <= 0:
            raise ValueError("Price must be positive")
    except ValueError:
        await message.answer(
            f"{DARK_EMOJIS['warning']} Incorrect price. Enter a number (e.g., 30000).\n\n"
            f"💡 Type 'back' to return to the menu.",
            parse_mode="Markdown"
        )
        return
    
    # Get data from state
    data = await state.get_data()
    ticker = data['ticker']
    threshold_type = data['threshold_type']
    
    # Save alert to database
    user_id = message.from_user.id
    success = db.add_alert(user_id, ticker, threshold_type, price)
    
    if success:
        # Get current price for comparison
        current_price = await crypto_api.get_coin_price(ticker)
        
        # Create success message
        type_text = "above" if threshold_type == "above" else "below"
        emoji = DARK_EMOJIS['up'] if threshold_type == "above" else DARK_EMOJIS['down']
        
        success_message = (
            f"{DARK_EMOJIS['success']} **Coin {ticker} added!**\n\n"
        )
        
        if current_price:
            price_diff = current_price - price
            price_percent = (price_diff / price) * 100
            
            if threshold_type == "above":
                if current_price >= price:
                    status = f"🚨 **THRESHOLD ALREADY MET!**"
                else:
                    status = f"📉 Need +${abs(price_diff):,.2f} ({abs(price_percent):.1f}%)"
            else:  # below
                if current_price <= price:
                    status = f"🚨 **THRESHOLD ALREADY MET!**"
                else:
                    status = f"📈 Need -${abs(price_diff):,.2f} ({price_percent:.1f}%)"
            
            success_message += (
                f"💰 **Current Price:** ${current_price:,.2f}\n"
                f"🎯 **Target Price:** ${price:,.2f}\n"
                f"📊 **Status:** {status}\n\n"
            )
        else:
            success_message += (
                f"🎯 **Target Price:** ${price:,.2f}\n"
                f"⚠️ Failed to get current price\n\n"
            )
        
        success_message += (
            f"{emoji} I will notify you when it will be {type_text} {price:,.0f}$.\n\n"
            f"{DARK_EMOJIS['shadow']} *Monitoring enabled*"
        )
        
        # Create keyboard with main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        
        await message.answer(success_message, parse_mode="Markdown", reply_markup=main_menu_keyboard)
    else:
        await message.answer(f"{DARK_EMOJIS['error']} Saving error. Please try again.")
    
    await state.clear()

@dp.message(F.text == f"{DARK_EMOJIS['list']} My Alerts")
async def cmd_show_alerts(message: types.Message):
    """Show user's alerts"""
    user_id = message.from_user.id
    alerts = db.get_user_alerts(user_id)
    
    if not alerts:
        # Create keyboard with main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        
        await message.answer(
            f"{DARK_EMOJIS['list']} **Your Alerts:**\n\n"
            f"You have no active alerts.\n"
            f"Click the 'Add Coin' button to create your first alert.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    # Create alerts list
    alerts_text = f"{DARK_EMOJIS['list']} **Monitored Coins:**\n\n"
    
    for i, alert in enumerate(alerts, 1):
        type_symbol = ">" if alert['threshold_type'] == "above" else "<"
        emoji = DARK_EMOJIS['up'] if alert['threshold_type'] == "above" else DARK_EMOJIS['down']
        
        alerts_text += (
            f"{i}. {emoji} **{alert['coin_ticker']}** {type_symbol} "
            f"**{alert['threshold_price']:,.0f}$**\n"
        )
    
    alerts_text += f"\n{DARK_EMOJIS['shadow']} *Total: {len(alerts)} alerts*"
    
    # Create keyboard with main menu button
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
        resize_keyboard=True
    )
    
    await message.answer(alerts_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(F.text == f"{DARK_EMOJIS['delete']} Delete Alert")
async def cmd_delete_alert(message: types.Message, state: FSMContext):
    """Start deleting alerts"""
    user_id = message.from_user.id
    alerts = db.get_user_alerts(user_id)
    
    if not alerts:
        # Create keyboard with main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        
        await message.answer(
            f"{DARK_EMOJIS['list']} **Delete Alerts**\n\n"
            f"You have no active alerts.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    await state.set_state(DeleteStates.waiting_for_choice)
    
    # Create delete keyboard
    keyboard_buttons = []
    for i, alert in enumerate(alerts, 1):
        type_symbol = ">" if alert['threshold_type'] == "above" else "<"
        button_text = f"{i}. {alert['coin_ticker']} {type_symbol} {alert['threshold_price']:,.0f}$"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"delete_{alert['id']}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"{DARK_EMOJIS['delete']} **Select an alert to delete:**",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def process_delete_choice(callback: types.CallbackQuery, state: FSMContext):
    """Process alert deletion choice"""
    alert_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    # Delete alert
    success = db.delete_alert(alert_id, user_id)
    
    if success:
        await callback.message.edit_text(
            f"{DARK_EMOJIS['success']} **Alert deleted!**\n\n"
            f"{DARK_EMOJIS['shadow']} *Monitoring updated*",
            parse_mode="Markdown"
        )
        
        # Send main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        await callback.message.answer("Click the button below to return to the menu:", reply_markup=keyboard)
    else:
        await callback.message.edit_text(
            f"{DARK_EMOJIS['error']} **Deletion error**\n\n"
            f"Please try again.",
            parse_mode="Markdown"
        )
    
    await state.clear()

@dp.message(Command("price"))
async def cmd_get_price(message: types.Message):
    """Get current price for a coin"""
    # Extract ticker from command or ask for it
    text = message.text.strip()
    if len(text.split()) > 1:
        ticker = text.split()[1].upper()
    else:
        await message.answer(
            f"{DARK_EMOJIS['coin']} **Current Price**\n\n"
            f"Enter the coin ticker (e.g., /price BTC):",
            parse_mode="Markdown"
        )
        return
    
    # Get price
    price = await crypto_api.get_coin_price(ticker)
    
    if price:
        await message.answer(
            f"{DARK_EMOJIS['coin']} **{ticker}**\n\n"
            f"💰 **Current Price:** ${price:,.2f}\n\n"
            f"{DARK_EMOJIS['shadow']} *ShadowPrice Bot*",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"{DARK_EMOJIS['error']} **Price retrieval error**\n\n"
            f"Coin **{ticker}** not found or API error.",
            parse_mode="Markdown"
        )

@dp.message(Command("prices"))
async def cmd_get_user_prices(message: types.Message):
    """Get current prices for all user's monitored coins"""
    user_id = message.from_user.id
    alerts = db.get_user_alerts(user_id)
    
    if not alerts:
        # Create keyboard with main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        
        await message.answer(
            f"{DARK_EMOJIS['list']} **Your Prices**\n\n"
            f"You have no active alerts.\n"
            f"Click the 'Add Coin' button to create your first alert.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    # Show loading message
    loading_msg = await message.answer(
        f"⏳ **Checking prices...**\n\n"
        f"Please wait, querying CoinGecko...",
        parse_mode="Markdown"
    )
    
    # Прогрес-бар: якщо перевірка триває >3 сек — оновлюємо повідомлення
    progress_task = asyncio.create_task(progress_bar_updater(loading_msg))
    try:
        # Get unique coin tickers
        coin_tickers = list(set(alert['coin_ticker'] for alert in alerts))
        
        # Get current prices for all coins
        prices = await crypto_api.get_multiple_prices(coin_tickers)
        progress_task.cancel()
        
        if not prices:
            await loading_msg.edit_text(
                f"{DARK_EMOJIS['error']} **Price retrieval error**\n\n"
                f"Could not retrieve current prices.\n"
                f"Please try again after a few minutes.",
                parse_mode="Markdown"
            )
            return
        
        # Create detailed price report
        price_report = f"{DARK_EMOJIS['coin']} **Current Prices of Your Coins:**\n\n"
        
        for alert in alerts:
            ticker = alert['coin_ticker']
            current_price = prices.get(ticker)
            threshold_price = alert['threshold_price']
            threshold_type = alert['threshold_type']
            
            if current_price:
                # Calculate price difference and percentage
                price_diff = current_price - threshold_price
                price_percent = (price_diff / threshold_price) * 100
                
                # Determine status emoji and text
                if threshold_type == "above":
                    if current_price >= threshold_price:
                        status_emoji = DARK_EMOJIS['alert']
                        status_text = "🚨 THRESHOLD MET!"
                    else:
                        status_emoji = DARK_EMOJIS['down']
                        status_text = f"📉 Need +${abs(price_diff):,.2f} ({abs(price_percent):.1f}%)"
                else:  # below
                    if current_price <= threshold_price:
                        status_emoji = DARK_EMOJIS['alert']
                        status_text = "🚨 THRESHOLD MET!"
                    else:
                        status_emoji = DARK_EMOJIS['up']
                        status_text = f"📈 Need -${abs(price_diff):,.2f} ({abs(price_percent):.1f}%)"
                
                # Format price with color indicators
                price_report += (
                    f"**{ticker}** {status_emoji}\n"
                    f"💰 **${current_price:,.2f}**\n"
                    f"🎯 Threshold: ${threshold_price:,.2f}\n"
                    f"📊 {status_text}\n\n"
                )
            else:
                price_report += (
                    f"**{ticker}** {DARK_EMOJIS['error']}\n"
                    f"❌ Price unavailable\n\n"
                )
        
        # Add footer
        price_report += f"{DARK_EMOJIS['shadow']} *Updated: {len(prices)}/{len(coin_tickers)} coins*"
        
        # Create keyboard with main menu button
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
            resize_keyboard=True
        )
        
        await loading_msg.edit_text(price_report, parse_mode="Markdown")
        await loading_msg.answer("Click the button below to return to the menu:", reply_markup=keyboard)
        
    except Exception as e:
        progress_task.cancel()
        await loading_msg.edit_text(
            f"{DARK_EMOJIS['error']} **Price retrieval error**\n\n"
            f"Technical error: {str(e)}\n"
            f"Please try again.",
            parse_mode="Markdown"
        )

@dp.message(F.text == f"{DARK_EMOJIS['coin']} Current Prices")
async def cmd_get_user_prices_button(message: types.Message):
    """Handle button click for getting user prices"""
    await cmd_get_user_prices(message)

@dp.message(F.text == "❓ Help")
async def cmd_help_button(message: types.Message):
    """Show help information via button"""
    help_text = (
        f"{DARK_EMOJIS['bot']} **ShadowPrice Bot - Help**\n\n"
        f"**How to use the bot:**\n"
        f"➕ **Add Coin** - create a new alert for price\n"
        f"📋 **My Alerts** - view your active alerts\n"
        f"💰 **Current Prices** - see your coins' prices\n"
        f"❌ **Delete Alert** - remove an alert\n"
        f"🏠 **Main Menu** - return to main menu\n\n"
        f"**Examples of usage:**\n"
        f"• Add an alert when BTC rises above $50,000\n"
        f"• Track when ETH falls below $2,000\n"
        f"• Get current prices of all your coins\n\n"
        f"**Supported coins:**\n"
        f"BTC, ETH, SOL, ADA, XRP, DOT, DOGE, AVAX, MATIC, LINK, UNI, ATOM, LTC, BCH, XLM, ALGO, VET, ICP and many others\n\n"
        f"If something does not work or you found a bug, please contact me: [`@spark_zxc`](https://t.me/spark_zxc)\n\n"
        f"{DARK_EMOJIS['shadow']} *Dark cryptocurrency monitoring*"
    )
    
    # Create keyboard with main menu button
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
        resize_keyboard=True
    )
    
    await message.answer(help_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Show help information"""
    help_text = (
        f"{DARK_EMOJIS['bot']} **ShadowPrice Bot - Help**\n\n"
        f"**Main Commands:**\n"
        f"➕ `/add` - Add a coin for monitoring\n"
        f"📋 `/alerts` - Show your alerts\n"
        f"💰 `/prices` - Current prices of your coins\n"
        f"💰 `/price BTC` - Current price of a specific coin\n"
        f"❌ `/delete` - Delete an alert\n"
        f"❓ `/help` - This help\n\n"
        f"**Examples of usage:**\n"
        f"• Add an alert when BTC rises above $50,000\n"
        f"• Track when ETH falls below $2,000\n"
        f"• Check current price of SOL\n"
        f"• Get current prices of all your coins\n\n"
        f"If something does not work or you found a bug, please contact me: [`@spark_zxc`](https://t.me/spark_zxc)\n\n"
        f"{DARK_EMOJIS['shadow']} *Dark cryptocurrency monitoring*"
    )
    
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("broadcast"))
async def cmd_broadcast_prices(message: types.Message):
    """Admin command to broadcast price updates to all users"""
    # Check if user is admin (you can modify this logic)
    user_id = message.from_user.id
    # For now, allow any user to test this feature
    # In production, you might want to restrict this to specific admin IDs
    
    try:
        users = db.get_all_users()
        if not users:
            await message.answer(
                f"{DARK_EMOJIS['warning']} **No users**\n\n"
                f"There are currently no registered users.",
                parse_mode="Markdown"
            )
            return
        
        # Send loading message
        loading_msg = await message.answer(
            f"{DARK_EMOJIS['coin']} **Price Broadcast...**\n\n"
            f"⏳ Sending price updates to {len(users)} users...",
            parse_mode="Markdown"
        )
        
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                await monitor.send_price_update_to_user(user['user_id'])
                success_count += 1
                await asyncio.sleep(0.1)  # Small delay to avoid rate limiting
            except Exception as e:
                error_count += 1
                print(f"Error sending to user {user['user_id']}: {e}")
        
        await loading_msg.edit_text(
            f"{DARK_EMOJIS['success']} **Broadcast complete!**\n\n"
            f"✅ Success: {success_count} users\n"
            f"❌ Errors: {error_count} users\n\n"
            f"{DARK_EMOJIS['shadow']} *Price updates sent*",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer(
            f"{DARK_EMOJIS['error']} **Broadcast error**\n\n"
            f"Technical error: {str(e)}",
            parse_mode="Markdown"
        )

# === Хендлер для авто-сповіщень (універсальний, emoji/case/space insensitive) ===
@dp.message(lambda msg: msg.text and re.search(r"auto[- ]?alerts", msg.text, re.IGNORECASE))
async def cmd_auto_alerts_menu(message: types.Message, state: FSMContext):
    print("[DEBUG] Auto-alerts handler triggered, text:", message.text)
    user_id = message.from_user.id
    enabled = db.is_global_auto_alert_enabled(user_id)
    if enabled:
        text = (
            "⚡ **Auto-Alerts**\n\n"
            "You receive push notifications for price spikes across popular coins (BTC, ETH, SOL, DOGE, BNB, ADA, XRP, MATIC).\n\n"
            "Click 'Disable' to stop receiving these notifications."
        )
        keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Disable")],[KeyboardButton(text="🏠 Main Menu")]], resize_keyboard=True)
    else:
        text = (
            "⚡ **Auto-Alerts**\n\n"
            "You do not receive push notifications for price spikes across popular coins.\n\n"
            "Click 'Enable' to receive auto-notifications for BTC, ETH, SOL, DOGE, BNB, ADA, XRP, MATIC."
        )
        keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Enable")],[KeyboardButton(text="🏠 Main Menu")]], resize_keyboard=True)
    await state.set_state("auto_alerts_global_toggle")
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# === Обробка кнопок 'Enable'/'Disable' для глобального авто-алерта ===
@dp.message(StateFilter("auto_alerts_global_toggle"), F.text.in_(["Enable", "Disable"]))
async def auto_alerts_toggle(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "Enable":
        db.set_global_auto_alert(user_id, True)
        await message.answer("✅ Auto-Alerts ENABLED!", reply_markup=main_menu_keyboard)
    else:
        db.set_global_auto_alert(user_id, False)
        await message.answer("❌ Auto-Alerts DISABLED!", reply_markup=main_menu_keyboard)
    await state.clear()
    await cmd_main_menu(message)

# === Універсальний хендлер для невідомих команд має бути в самому низу файлу! ===
# (залишаємо handle_unknown як є, але переносимо його в самий кінець)

@dp.message()
async def handle_unknown(message: types.Message):
    """Handle unknown messages"""
    # Create keyboard with main menu button
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Main Menu")]],
        resize_keyboard=True
    )
    
    await message.answer(
        f"{DARK_EMOJIS['warning']} **Unknown command**\n\n"
        f"Use the buttons below to control the bot.\n"
        f"Click 'Main Menu' to return to the main functions.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# Після завершення будь-якої FSM-операції (додавання монети, авто-сповіщення, видалення тощо) — завжди показувати головне меню через cmd_main_menu(message) або reply_markup=main_menu_keyboard
# (оновити відповідні місця у функціях process_price, auto_alerts_toggle, process_delete_choice, тощо)

async def start_monitoring():
    """Start the price monitoring in background"""
    global monitor
    monitor = PriceMonitor(bot)
    await monitor.start_monitoring()

async def main():
    """Main function"""
    print(f"{DARK_EMOJIS['bot']} ShadowPrice Bot starting...")
    
    # Start monitoring in background
    asyncio.create_task(start_monitoring())
    
    # Start bot
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print(f"\n{DARK_EMOJIS['bot']} Bot stopped by user")
    finally:
        if monitor:
            await monitor.stop_monitoring()
        await bot.session.close()

async def progress_bar_updater(msg):
    try:
        await asyncio.sleep(3)
        await msg.edit_text("🔄 **Checking price...**\n\nPlease wait a bit more...", parse_mode="Markdown")
        await asyncio.sleep(4)
        await msg.edit_text("⌛ **A bit more...**\n\nCoinGecko might be slow to respond.", parse_mode="Markdown")
    except Exception:
        pass

# Add logging to all CoinGecko API calls

# Patch: wrap all calls to crypto_api.get_coin_price and crypto_api.get_multiple_prices with logging
import functools

old_get_coin_price = crypto_api.get_coin_price
async def logged_get_coin_price(ticker, *args, **kwargs):
    print(f"[GECKO] Requesting price for: {ticker}")
    try:
        price = await old_get_coin_price(ticker, *args, **kwargs)
        print(f"[GECKO] Price for {ticker}: {price}")
        return price
    except Exception as e:
        print(f"[GECKO] ERROR for {ticker}: {e}")
        raise
crypto_api.get_coin_price = logged_get_coin_price

old_get_multiple_prices = crypto_api.get_multiple_prices
async def logged_get_multiple_prices(tickers, *args, **kwargs):
    print(f"[GECKO] Requesting prices for: {tickers}")
    try:
        prices = await old_get_multiple_prices(tickers, *args, **kwargs)
        print(f"[GECKO] Prices: {prices}")
        return prices
    except Exception as e:
        print(f"[GECKO] ERROR for {tickers}: {e}")
        raise
crypto_api.get_multiple_prices = logged_get_multiple_prices

if __name__ == "__main__":
    asyncio.run(main()) 