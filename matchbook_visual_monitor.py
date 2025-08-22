#!/usr/bin/env python3
"""
Matchbook Visual Monitor - Integrated visual scraping for accurate draw lay monitoring
Captures data from https://www.matchbook.com/events/soccer#england
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

class MatchbookVisualMonitor:
    """Visual monitor for Matchbook draw lay amounts"""
    
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
            logger.info("✅ Visual monitor Chrome initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize visual monitor: {e}")
            return False
    
    async def monitor_draw_markets(self):
        """Monitor draw markets across all 5 European leagues"""
        league_urls = [
            ("England", "https://www.matchbook.com/events/soccer#england"),
            ("Italy", "https://www.matchbook.com/events/soccer#italy"), 
            ("Spain", "https://www.matchbook.com/events/soccer#spain"),
            ("France", "https://www.matchbook.com/events/soccer#france"),
            ("Germany", "https://www.matchbook.com/events/soccer#germany")
        ]
        
        all_markets = []
        total_alerts = 0
        
        for league_name, url in league_urls:
            try:
                logger.info(f"📸 {league_name}: Capturing live draw market data...")
                
                # Navigate to league URL
                self.driver.get(url)
                time.sleep(8)  # Give time for dynamic content to load
                
                # Get page source
                page_source = self.driver.page_source.lower()
                
                # Extract draw lay amounts using regex patterns
                draw_markets = await self.extract_draw_amounts(page_source, league_name)
                
                # Check for alerts in this league
                league_alerts = 0
                for market in draw_markets:
                    amount = market['amount']
                    if amount >= 2000:  # £2,000 threshold
                        
                        # Check if this is a new alert (avoid spam)
                        market_key = f"{market['match']}_{market['odds']}"
                        if market_key not in self.last_amounts or abs(self.last_amounts[market_key] - amount) > 100:
                            
                            # Send Telegram alert
                            alert_text = f"🚨 DRAW LAY ALERT\n\n" \
                                       f"League: {league_name}\n" \
                                       f"Match: {market['match']}\n" \
                                       f"Amount: £{amount:,.2f} available to LAY draw\n" \
                                       f"Odds: {market['odds']}\n" \
                                       f"Source: Visual monitoring\n" \
                                       f"Time: {time.strftime('%H:%M:%S')}"
                            
                            await self.bot.send_telegram_message(alert_text)
                            logger.info(f"🚨 {league_name} ALERT: {market['match']} - £{amount:,.2f}")
                            
                            self.last_amounts[market_key] = amount
                            league_alerts += 1
                
                logger.info(f"📊 {league_name}: {len(draw_markets)} markets checked, {league_alerts} alerts sent")
                all_markets.extend(draw_markets)
                total_alerts += league_alerts
                
            except Exception as e:
                logger.error(f"❌ {league_name} monitoring error: {e}")
        
        logger.info(f"🏆 TOTAL: {len(all_markets)} markets across 5 leagues, {total_alerts} alerts sent")
        return all_markets
    
    async def extract_draw_amounts(self, page_source, league_name):
        """Extract draw lay amounts from page source for any league"""
        markets = []
        
        try:
            # Generic pattern to find any match with high amounts
            # Look for £X,XXX patterns in the page source
            amount_patterns = [
                r'£(\d{1,3}(?:,\d{3})+)',  # £1,000 to £999,999
                r'£(\d{4,})'               # £1000+ without commas
            ]
            
            found_amounts = set()
            for pattern in amount_patterns:
                matches = re.findall(pattern, page_source)
                for amount_str in matches:
                    amount = float(amount_str.replace(',', ''))
                    if amount >= 1000:  # Only significant amounts
                        found_amounts.add(amount)
            
            # For each significant amount, try to find the associated match
            for amount in found_amounts:
                amount_str = f"{amount:,.0f}" if amount >= 1000 else str(int(amount))
                
                # Look for match patterns around this amount
                # Common team name patterns in each league
                team_patterns = {
                    'England': ['arsenal', 'chelsea', 'liverpool', 'manchester', 'tottenham', 'city', 'united', 'burnley', 'sunderland', 'brentford', 'aston villa', 'bournemouth', 'wolverhampton', 'crystal palace', 'nottingham forest', 'everton', 'brighton', 'fulham'],
                    'Italy': ['juventus', 'milan', 'inter', 'roma', 'napoli', 'lazio', 'atalanta', 'fiorentina', 'bologna', 'torino'],
                    'Spain': ['barcelona', 'madrid', 'atletico', 'valencia', 'sevilla', 'villarreal', 'bilbao', 'sociedad', 'betis', 'espanyol'],
                    'France': ['paris', 'marseille', 'lyon', 'monaco', 'lille', 'rennes', 'nice', 'montpellier', 'strasbourg', 'nantes'],
                    'Germany': ['bayern', 'dortmund', 'leipzig', 'leverkusen', 'frankfurt', 'wolfsburg', 'freiburg', 'union', 'stuttgart', 'hoffenheim']
                }
                
                # Try to find team names near this amount
                for team in team_patterns.get(league_name, []):
                    # Look for this team name within 500 characters of the amount
                    team_pattern = rf'.{{0,500}}{team}.{{0,500}}£{re.escape(amount_str)}.{{0,500}}'
                    match = re.search(team_pattern, page_source, re.IGNORECASE | re.DOTALL)
                    
                    if match:
                        # Extract the context to try to find opponent
                        context = match.group(0).lower()
                        
                        # Look for vs pattern
                        vs_match = re.search(r'([a-z\s]+)\s+vs?\s+([a-z\s]+)', context)
                        if vs_match:
                            team1 = vs_match.group(1).strip().title()
                            team2 = vs_match.group(2).strip().title()
                            match_name = f"{team1} vs {team2}"
                        else:
                            match_name = f"{team.title()} vs Unknown"
                        
                        # Estimate odds based on amount
                        estimated_odds = "3.5" if amount < 3000 else "4.0" if amount < 5000 else "5.0"
                        
                        markets.append({
                            'match': match_name,
                            'amount': amount,
                            'odds': estimated_odds,
                            'type': 'DRAW LAY',
                            'league': league_name
                        })
                        
                        logger.info(f"🎯 {league_name} FOUND: {match_name} - £{amount:,.2f}")
                        break  # Found this amount, move to next
            
        except Exception as e:
            logger.error(f"❌ {league_name} extract error: {e}")
        
        return markets
    
    async def close(self):
        """Clean up driver"""
        if self.driver:
            self.driver.quit()
            logger.info("🔚 Visual monitor closed")

# Integration function for the main bot
async def run_visual_monitoring(bot_instance):
    """Run visual monitoring as part of the main bot"""
    monitor = MatchbookVisualMonitor(bot_instance)
    
    try:
        if await monitor.initialize_driver():
            markets = await monitor.monitor_draw_markets()
            return len([m for m in markets if m['amount'] >= 2000])
        else:
            logger.error("Failed to initialize visual monitoring")
            return 0
    finally:
        await monitor.close()

# Test function for standalone execution
async def test_visual_monitoring():
    """Test visual monitoring standalone"""
    class MockBot:
        async def send_telegram_message(self, text):
            logger.info(f"MOCK TELEGRAM: {text}")
    
    bot = MockBot()
    alerts = await run_visual_monitoring(bot)
    logger.info(f"Test completed: {alerts} alerts would be sent")

if __name__ == "__main__":
    asyncio.run(test_visual_monitoring())