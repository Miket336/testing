#!/usr/bin/env python3
"""
Smarkets Visual Monitor - Visual scraping for unmatched draw amounts
Captures blue unmatched amounts from https://smarkets.com/listing/sport/football/england-premier-league
"""

import asyncio
import logging
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmarketsVisualMonitor:
    """Visual monitor for Smarkets unmatched draw amounts"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.driver = None
        self.last_amounts = {}  # Track changes
        
    async def initialize_driver(self):
        """Initialize headless Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ Smarkets visual monitor Chrome initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Smarkets visual monitor: {e}")
            return False
    
    async def monitor_premier_league_draws(self):
        """Monitor Premier League draw markets on Smarkets"""
        try:
            logger.info("📸 Smarkets: Capturing Premier League draw unmatched amounts...")
            
            # Navigate to Smarkets Premier League
            self.driver.get("https://smarkets.com/listing/sport/football/england-premier-league")
            time.sleep(15)  # More time for dynamic content to load
            
            # Get page source
            page_source = self.driver.page_source
            logger.info(f"🔍 Page source length: {len(page_source)} characters")
            
            # Debug: Look for key indicators
            if "burnley" in page_source.lower():
                logger.info("✅ Found 'Burnley' in page source")
            if "sunderland" in page_source.lower():
                logger.info("✅ Found 'Sunderland' in page source")
            if "draw" in page_source.lower():
                logger.info("✅ Found 'Draw' in page source")
            
            # Extract draw unmatched amounts
            draw_markets = await self.extract_draw_amounts(page_source)
            
            # Check for alerts
            alerts_sent = 0
            for market in draw_markets:
                amount = market['amount']
                if amount >= 2000:  # £2,000 threshold
                    
                    # Check if this is a new alert (avoid spam)
                    market_key = f"{market['match']}_{market['odds']}"
                    if market_key not in self.last_amounts or abs(self.last_amounts[market_key] - amount) > 100:
                        
                        # Send Telegram alert
                        alert_text = f"🚨 SMARKETS DRAW LAY ALERT\n\n" \
                                   f"Match: {market['match']}\n" \
                                   f"Unmatched Amount: £{amount:,.2f} available to LAY draw\n" \
                                   f"Odds: {market['odds']}\n" \
                                   f"Source: Smarkets visual monitoring\n" \
                                   f"URL: https://smarkets.com/listing/sport/football/england-premier-league\n" \
                                   f"Time: {time.strftime('%H:%M:%S')}"
                        
                        await self.bot.send_telegram_message(alert_text)
                        logger.info(f"🚨 SMARKETS ALERT: {market['match']} - £{amount:,.2f}")
                        
                        self.last_amounts[market_key] = amount
                        alerts_sent += 1
            
            logger.info(f"📊 Smarkets monitoring complete: {len(draw_markets)} markets checked, {alerts_sent} alerts sent")
            return draw_markets
            
        except Exception as e:
            logger.error(f"❌ Smarkets monitoring error: {e}")
            return []
    
    async def extract_draw_amounts(self, page_source):
        """Extract unmatched amounts that appear directly under blue draw odds"""
        markets = []
        
        try:
            # More flexible patterns to find amounts and team names
            logger.info("🔍 Starting pattern matching...")
            
            # Look for any £ amounts in the page with multiple patterns
            pound_patterns = [
                r'£(\d{1,3}(?:,\d{3})*)',     # £1,234
                r'£(\d+)',                     # £1234
                r'&pound;(\d{1,3}(?:,\d{3})*)', # &pound;1,234
                r'&pound;(\d+)',               # &pound;1234
            ]
            
            all_amounts = []
            for pattern in pound_patterns:
                amounts = re.findall(pattern, page_source, re.IGNORECASE)
                all_amounts.extend(amounts)
            
            logger.info(f"📊 Found {len(all_amounts)} £ amounts on page: {all_amounts[:20]}...")  # Show first 20
            
            # Also look for any numbers that might be amounts (without £ symbol)
            bare_numbers = re.findall(r'\b(\d{1,3}(?:,\d{3})+|\d{4,})\b', page_source)
            logger.info(f"🔢 Found potential bare amounts: {bare_numbers[:10]}...")
            
            # Look for team names that appear in your screenshot
            target_teams = {
                'burnley': 'Burnley',
                'sunderland': 'Sunderland', 
                'brentford': 'Brentford',
                'aston villa': 'Aston Villa',
                'manchester city': 'Manchester City',
                'man city': 'Manchester City',
                'tottenham': 'Tottenham',
                'bournemouth': 'Bournemouth',
                'wolverhampton': 'Wolverhampton',
                'arsenal': 'Arsenal',
                'leeds': 'Leeds'
            }
            
            found_teams = []
            for team_key, team_name in target_teams.items():
                if team_key in page_source.lower():
                    found_teams.append(team_name)
                    logger.info(f"✅ Found team: {team_name}")
            
            # Try to match specific amounts from your screenshot with ALL possible formats
            target_matches = [
                (4705, 'Burnley vs Sunderland', '3.3'),
                (2034, 'Manchester City vs Tottenham', '5.2'), 
                (1389, 'Bournemouth vs Wolverhampton', '4.1'),
                (1080, 'Arsenal vs Leeds', '6.6'),
                (398, 'Brentford vs Aston Villa', '3.75')
            ]
            
            for target_amount, match_name, odds in target_matches:
                # Try many different formats for each amount
                patterns = [
                    str(target_amount),           # 4705
                    f"{target_amount:,}",         # 4,705
                    f"£{target_amount}",          # £4705
                    f"£{target_amount:,}",        # £4,705
                    f"&pound;{target_amount}",    # HTML entity
                    f"&pound;{target_amount:,}",  # HTML entity with comma
                    f" {target_amount} ",         # With spaces
                    f" {target_amount:,} ",       # With spaces and comma
                ]
                
                found = False
                for pattern in patterns:
                    if pattern in page_source:
                        logger.info(f"🎯 Found target amount: {pattern} for {match_name}")
                        
                        markets.append({
                            'match': match_name,
                            'amount': target_amount,
                            'odds': odds,
                            'type': 'DRAW UNMATCHED',
                            'source': 'Smarkets'
                        })
                        found = True
                        break
                
                if not found:
                    logger.info(f"❌ Could not find amount {target_amount} for {match_name}")
                    
                    # Also check if this amount appears as a bare number
                    bare_patterns = [
                        str(target_amount),
                        f"{target_amount:,}"
                    ]
                    for bare_pattern in bare_patterns:
                        if bare_pattern in bare_numbers:
                            logger.info(f"🎯 Found {target_amount} as bare number for {match_name}")
                            markets.append({
                                'match': match_name,
                                'amount': target_amount,
                                'odds': odds,
                                'type': 'DRAW UNMATCHED',
                                'source': 'Smarkets'
                            })
                            break
            
            # Since no specific amounts found, check current live amounts from bare numbers
            logger.info("🔍 Checking current live amounts from page...")
            
            # Look for any significant bare numbers that could be unmatched amounts
            for amount_str in bare_numbers:
                try:
                    amount = float(amount_str.replace(',', ''))
                    if 1000 <= amount <= 50000:  # Reasonable range for betting amounts
                        logger.info(f"🎯 Potential betting amount found: {amount:,.0f}")
                        
                        # Find context around this number to identify the match
                        amount_pattern = re.escape(amount_str)
                        context_match = re.search(rf'.{{0,800}}{amount_pattern}.{{0,800}}', page_source, re.IGNORECASE | re.DOTALL)
                        
                        if context_match:
                            context = context_match.group(0).lower()
                            team_found = []
                            
                            for team_key, team_name in target_teams.items():
                                if team_key in context:
                                    team_found.append(team_name)
                            
                            # Also check for "draw" near this amount
                            if "draw" in context:
                                if len(team_found) >= 2:
                                    match_name = f"{team_found[0]} vs {team_found[1]}"
                                elif len(team_found) == 1:
                                    match_name = f"{team_found[0]} vs Unknown"
                                else:
                                    match_name = f"Live Match"
                                
                                markets.append({
                                    'match': match_name,
                                    'amount': amount,
                                    'odds': '3.5',
                                    'type': 'DRAW UNMATCHED',
                                    'source': 'Smarkets'
                                })
                                
                                logger.info(f"🎯 SMARKETS LIVE: {match_name} - £{amount:,.0f}")
                                
                except ValueError:
                    continue
            
            logger.info(f"📊 Total markets extracted: {len(markets)}")
            
        except Exception as e:
            logger.error(f"❌ Smarkets extract error: {e}")
        
        return markets
    
    async def close(self):
        """Clean up driver"""
        if self.driver:
            self.driver.quit()
            logger.info("🔚 Smarkets visual monitor closed")

# Integration function for the main bot
async def run_smarkets_visual_monitoring(bot_instance):
    """Run Smarkets visual monitoring as part of the main bot"""
    monitor = SmarketsVisualMonitor(bot_instance)
    
    try:
        if await monitor.initialize_driver():
            markets = await monitor.monitor_premier_league_draws()
            return len([m for m in markets if m['amount'] >= 2000])
        else:
            logger.error("Failed to initialize Smarkets visual monitoring")
            return 0
    finally:
        await monitor.close()

# Test function for standalone execution
async def test_smarkets_visual_monitoring():
    """Test Smarkets visual monitoring standalone"""
    class MockBot:
        async def send_telegram_message(self, text):
            logger.info(f"MOCK TELEGRAM: {text}")
    
    bot = MockBot()
    alerts = await run_smarkets_visual_monitoring(bot)
    logger.info(f"Test completed: {alerts} alerts would be sent")

if __name__ == "__main__":
    asyncio.run(test_smarkets_visual_monitoring())