import asyncio
from typing import List, Dict
from database import Database
from crypto_api import CryptoAPI
from config import CHECK_INTERVAL, DARK_EMOJIS
import time

class PriceMonitor:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.db = Database()
        self.crypto_api = CryptoAPI()
        self.is_running = False
        self.triggered_alerts = set()  # Track triggered alerts to avoid spam
        self.price_history = {}  # {ticker: [(timestamp, price), ...]}
        self.auto_alert_triggered = {}  # {(user_id, ticker): last_alert_time}
    
    async def start_monitoring(self):
        """Start the price monitoring loop"""
        self.is_running = True
        print(f"{DARK_EMOJIS['bot']} ShadowPrice Bot - Monitoring started")
        
        while self.is_running:
            try:
                await self.check_all_alerts()
                await self.check_auto_alerts()
                await asyncio.sleep(CHECK_INTERVAL)
            except Exception as e:
                print(f"{DARK_EMOJIS['error']} Monitoring error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def stop_monitoring(self):
        """Stop the price monitoring loop"""
        self.is_running = False
        await self.crypto_api.close_session()
        print(f"{DARK_EMOJIS['bot']} ShadowPrice Bot - Monitoring stopped")
    
    async def check_all_alerts(self):
        """Check all active alerts for price threshold breaches"""
        try:
            # Get all alerts from database
            alerts = self.db.get_all_alerts()
            if not alerts:
                return
            
            # Group alerts by coin ticker for efficient API calls
            coin_tickers = list(set(alert['coin_ticker'] for alert in alerts))
            
            # Get current prices for all coins
            prices = await self.crypto_api.get_multiple_prices(coin_tickers)
            
            # Check each alert
            for alert in alerts:
                await self.check_single_alert(alert, prices)
                
        except Exception as e:
            print(f"{DARK_EMOJIS['error']} Error checking alerts: {e}")
    
    async def check_single_alert(self, alert: Dict, prices: Dict[str, float]):
        """Check if a single alert has been triggered"""
        try:
            coin_ticker = alert['coin_ticker']
            current_price = prices.get(coin_ticker)
            
            if current_price is None:
                return
            
            threshold_price = alert['threshold_price']
            threshold_type = alert['threshold_type']
            alert_id = alert['id']
            
            # Create unique key for this alert
            alert_key = f"{alert_id}_{coin_ticker}_{threshold_type}_{threshold_price}"
            
            # Check if threshold is breached
            is_triggered = False
            
            if threshold_type == "above" and current_price >= threshold_price:
                is_triggered = True
            elif threshold_type == "below" and current_price <= threshold_price:
                is_triggered = True
            
            # Send notification if triggered and not already sent
            if is_triggered and alert_key not in self.triggered_alerts:
                await self.send_alert_notification(alert, current_price)
                self.triggered_alerts.add(alert_key)
            
            # Remove from triggered set if price is back to normal
            elif not is_triggered and alert_key in self.triggered_alerts:
                self.triggered_alerts.remove(alert_key)
                
        except Exception as e:
            print(f"{DARK_EMOJIS['error']} Error checking alert {alert.get('id', 'unknown')}: {e}")
    
    async def send_alert_notification(self, alert: Dict, current_price: float):
        """Send notification to user about triggered alert"""
        try:
            user_id = alert['user_id']
            coin_ticker = alert['coin_ticker']
            threshold_type = alert['threshold_type']
            threshold_price = alert['threshold_price']
            
            # Create dark-themed message
            if threshold_type == "above":
                message = (
                    f"{DARK_EMOJIS['alert']} **{coin_ticker} pierced {threshold_price:,.0f}$!**\n"
                    f"{DARK_EMOJIS['bell']} Now: **{current_price:,.2f}$**\n"
                    f"{DARK_EMOJIS['up']} The price has risen above the threshold"
                )
            else:
                message = (
                    f"{DARK_EMOJIS['alert']} **{coin_ticker} fell below {threshold_price:,.0f}$!**\n"
                    f"{DARK_EMOJIS['bell']} Now: **{current_price:,.2f}$**\n"
                    f"{DARK_EMOJIS['down']} The price has fallen below the threshold"
                )
            
            # Add dark theme footer
            message += f"\n\n{DARK_EMOJIS['shadow']} *ShadowPrice Bot*"
            
            # Send message
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown"
            )
            
            print(f"{DARK_EMOJIS['alert']} Alert sent to user {user_id}: {coin_ticker} {threshold_type} {threshold_price}")
            
        except Exception as e:
            print(f"{DARK_EMOJIS['error']} Error sending alert notification: {e}")
    
    async def force_check_user_alerts(self, user_id: int):
        """Force check alerts for a specific user (for testing)"""
        try:
            alerts = self.db.get_user_alerts(user_id)
            if not alerts:
                return "No active reminders"
            
            coin_tickers = list(set(alert['coin_ticker'] for alert in alerts))
            prices = await self.crypto_api.get_multiple_prices(coin_tickers)
            
            results = []
            for alert in alerts:
                current_price = prices.get(alert['coin_ticker'])
                if current_price:
                    results.append(f"{alert['coin_ticker']}: ${current_price:,.2f}")
            
            return f"📊 Current prices:\n" + "\n".join(results)
            
        except Exception as e:
            return f"{DARK_EMOJIS['error']} Помилка: {e}"
    
    async def send_price_update_to_user(self, user_id: int):
        """Send periodic price update to user"""
        try:
            alerts = self.db.get_user_alerts(user_id)
            if not alerts:
                return
            
            # Get unique coin tickers
            coin_tickers = list(set(alert['coin_ticker'] for alert in alerts))
            
            # Get current prices
            prices = await self.crypto_api.get_multiple_prices(coin_tickers)
            
            if not prices:
                return
            
            # Create summary message
            summary = f"{DARK_EMOJIS['coin']} **Price update**\n\n"
            
            # Show top 3 most significant changes
            price_changes = []
            for alert in alerts:
                ticker = alert['coin_ticker']
                current_price = prices.get(ticker)
                if current_price:
                    threshold_price = alert['threshold_price']
                    price_diff = current_price - threshold_price
                    price_percent = (price_diff / threshold_price) * 100
                    
                    if alert['threshold_type'] == "above":
                        if current_price >= threshold_price:
                            status = f"🚨 {ticker}: ${current_price:,.2f} (THE THRESHOLD HAS BEEN CROSSED!)"
                        else:
                            status = f"📉 {ticker}: ${current_price:,.2f} (-{abs(price_percent):.1f}%)"
                    else:
                        if current_price <= threshold_price:
                            status = f"🚨 {ticker}: ${current_price:,.2f} (THE THRESHOLD HAS BEEN CROSSED!)"
                        else:
                            status = f"📈 {ticker}: ${current_price:,.2f} (+{price_percent:.1f}%)"
                    
                    price_changes.append((abs(price_percent), status))
            
            # Sort by significance and show top 3
            price_changes.sort(reverse=True)
            for _, status in price_changes[:3]:
                summary += f"{status}\n"
            
            if len(price_changes) > 3:
                summary += f"\n... and more {len(price_changes) - 3} coins"
            
            summary += f"\n\n{DARK_EMOJIS['shadow']} *Automatic update*"
            
            # Send update
            await self.bot.send_message(
                chat_id=user_id,
                text=summary,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            print(f"{DARK_EMOJIS['error']} Error sending price update to user {user_id}: {e}") 

    async def check_auto_alerts(self):
        """Check for price spikes/dumps for auto-alert coins"""
        # 1. Збираємо всіх користувачів з авто-сповіщеннями
        users = self.db.get_all_users()
        user_coins = {}
        for user in users:
            coins = [coin for coin, enabled in self.db.get_auto_alerts(user['user_id']) if enabled]
            if coins:
                user_coins[user['user_id']] = coins
        if not user_coins:
            return
        # 2. Збираємо унікальні монети
        all_coins = set()
        for coins in user_coins.values():
            all_coins.update(coins)
        # 3. Отримуємо поточні ціни
        prices = await self.crypto_api.get_multiple_prices(list(all_coins))
        now = int(time.time())
        # 4. Оновлюємо історію цін
        for ticker, price in prices.items():
            if ticker not in self.price_history:
                self.price_history[ticker] = []
            self.price_history[ticker].append((now, price))
            # Тримаємо тільки останні 15 записів (на 10-15 хвилин)
            self.price_history[ticker] = [p for p in self.price_history[ticker] if now - p[0] <= 900]
        # 5. Перевіряємо спайки/дампи
        for user_id, coins in user_coins.items():
            for ticker in coins:
                history = self.price_history.get(ticker, [])
                if len(history) < 2:
                    continue
                # Знаходимо ціну 10 хвилин тому
                old_prices = [p for p in history if now - p[0] >= 600]
                if not old_prices:
                    continue
                old_price = old_prices[0][1]
                current_price = history[-1][1]
                if old_price == 0:
                    continue
                change = (current_price - old_price) / old_price * 100
                # Якщо зміна більше 5% (вгору або вниз)
                if abs(change) >= 5:
                    # Не спамити: не частіше ніж раз на 30 хвилин
                    key = (user_id, ticker)
                    last_alert = self.auto_alert_triggered.get(key, 0)
                    if now - last_alert < 1800:
                        continue
                    self.auto_alert_triggered[key] = now
                    # Надсилаємо сповіщення
                    direction = f"{DARK_EMOJIS['up']} Shot!" if change > 0 else f"{DARK_EMOJIS['down']} Dump!"
                    emoji = DARK_EMOJIS['alert']
                    msg = (
                        f"{emoji} **{ticker} {direction}**\n"
                        f"Change in 10 minutes: {change:+.2f}%\n"
                        f"Current price: ${current_price:,.2f}\n"
                        f"10 min ago: ${old_price:,.2f}\n\n"
                        f"{DARK_EMOJIS['shadow']} *Auto-notification*"
                    )
                    try:
                        await self.bot.send_message(user_id, msg, parse_mode="Markdown")
                    except Exception as e:
                        print(f"{DARK_EMOJIS['error']} Auto-alert send error: {e}") 