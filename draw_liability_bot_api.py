#!/usr/bin/env python3
"""
Telegram bot for monitoring draw liability on Smarkets and Matchbook exchanges.
Sends alerts when liability crosses configurable thresholds.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional

import aiohttp
import json

from exchanges.smarkets_api import SmarketsAPI


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class DrawLiabilityBot:
    """Main bot class for monitoring draw liability across exchanges."""
    
    def __init__(self):
        # Load configuration from environment variables
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Monitoring configuration
        self.liability_threshold = float(os.getenv("LIABILITY_THRESHOLD", "1500"))  # Set to £1,500 to catch Roma vs Bologna
        self.polling_interval = int(os.getenv("POLL_SECONDS", "120"))  # seconds - visual monitoring every 2 minutes
        
        # Exchange API credentials
        self.smarkets_username = os.getenv("SMARKETS_EMAIL", "")
        self.smarkets_password = os.getenv("SMARKETS_PASSWORD", "")
        self.matchbook_username = os.getenv("MATCHBOOK_USERNAME", "")
        self.matchbook_password = os.getenv("MATCHBOOK_PASSWORD", "")
        
        # Initialize exchange APIs with bot reference for immediate alerts
        # Initialize Smarkets API for unmatched draw lay amounts
        self.smarkets_api = SmarketsAPI(self.smarkets_username, self.smarkets_password)
        logger.info("Bot configured for Smarkets API - unmatched draw lay monitoring")
        
        # Bot state
        self.telegram_base_url = f"https://api.telegram.org/bot{self.telegram_token}"
        self.session = None
        self.last_alert_times = {}  # Track when alerts were last sent for each exchange
        
    async def initialize(self):
        """Initialize the Telegram bot and exchange APIs."""
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not self.chat_id:
            raise ValueError("TELEGRAM_CHAT_ID environment variable is required")
        
        # Initialize HTTP session
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        # Initialize Smarkets API
        await self.smarkets_api.initialize()
        logger.info("Smarkets API ready for unmatched draw lay monitoring")
        logger.info("Smarkets API initialized successfully")
    
    async def send_telegram_message(self, text: str):
        """Send a message to Telegram chat."""
        try:
            url = f"{self.telegram_base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    logger.info("Message sent to Telegram successfully")
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send Telegram message: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    async def get_smarkets_liability(self) -> Optional[Dict]:
        """Get draw liability data from Smarkets API with proper conversion factors."""
        try:
            # Use API with correct conversion formulas (much faster and more reliable)
            logger.info("Getting data from Smarkets API with proper conversions...")
            api_data = await self.smarkets_api.get_draw_liability()
            
            if api_data:
                total_liability = api_data.get('total_liability', 0)
                logger.info(f"Smarkets API found total liability: £{total_liability:.2f}")
                return api_data
            else:
                logger.warning("Smarkets API returned no data")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching Smarkets liability: {e}")
            return None
    
    async def get_matchbook_liability(self) -> Optional[Dict]:
        """Get draw liability data from Matchbook."""
        try:
            logger.info("Getting data from Matchbook API...")
            result = await self.matchbook_api.get_draw_liability()
            if result:
                logger.info(f"Matchbook API returned liability: £{result.get('liability', 0):.2f}")
            else:
                logger.warning("Matchbook API returned None")
            return result
        except Exception as e:
            logger.error(f"Error fetching Matchbook liability: {e}")
            return None
    
    async def check_liability_and_alert(self):
        """Check Smarkets for unmatched draw lay amounts."""
        try:
            logger.info("🔍 Starting Smarkets unmatched draw lay monitoring...")
            
            # Get unmatched draw lay amounts from Smarkets API
            draw_data = await self.smarkets_api.get_unmatched_draw_lays()
            
            if draw_data and draw_data.get('markets'):
                alerts_sent = 0
                logger.info(f"🔍 Checking {len(draw_data['markets'])} markets against £{self.liability_threshold} threshold")
                for market in draw_data['markets']:
                    logger.info(f"📊 Market: {market['event_name']} - £{market['unmatched_amount']:.2f}")
                    if market['unmatched_amount'] >= self.liability_threshold:
                        
                        # Send alert for this specific draw lay
                        alert_text = f"🚨 SMARKETS DRAW LAY ALERT\n\n" \
                                   f"Match: {market['event_name']}\n" \
                                   f"Unmatched Lay Amount: £{market['unmatched_amount']:,.2f}\n" \
                                   f"Odds: {market['odds']}\n" \
                                   f"Market: Draw\n" \
                                   f"Source: Smarkets API\n" \
                                   f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        
                        await self.send_telegram_message(alert_text)
                        logger.info(f"🚨 ALERT: {market['event_name']} - £{market['unmatched_amount']:,.2f} unmatched lay")
                        alerts_sent += 1
                
                logger.info(f"Smarkets monitoring complete: {len(draw_data['markets'])} draw markets checked, {alerts_sent} alerts sent")
            else:
                logger.info("No significant unmatched draw lay amounts found")
            
        except Exception as e:
            logger.error(f"Error in Smarkets draw lay monitoring: {e}")
    
    async def send_individual_odds_alert(self, exchange: str, odds_info: dict):
        """Send individual odds alert to Telegram."""
        try:
            amount = odds_info['amount']
            event = odds_info['event']
            odds = odds_info['odds']
            
            alert_message = (
                f"🚨 INDIVIDUAL ODDS ALERT\n\n"
                f"Match: {event}\n"
                f"Exchange: {exchange}\n"
                f"Unmatched at Specific Odds: £{amount:,.2f} at {odds:.2f}\n"
                f"Threshold: £{self.liability_threshold:,.2f}\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await self.send_telegram_message(alert_message)
            logger.info(f"Individual odds alert sent: {event} - £{amount:,.2f} at {odds:.2f}")
            
        except Exception as e:
            logger.error(f"Error sending individual odds alert: {e}")
    
    async def monitoring_loop(self):
        """Main monitoring loop that runs continuously."""
        logger.info(f"Starting monitoring loop with {self.polling_interval}s intervals")
        
        while True:
            try:
                await self.check_liability_and_alert()
                await asyncio.sleep(self.polling_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def run(self):
        """Start the bot and monitoring."""
        try:
            await self.initialize()
            
            # Send startup message
            startup_message = (
                f"🟢 Draw Liability Monitor Started\n\n"
                f"Threshold: £{self.liability_threshold:,.2f}\n"
                f"Polling: Every {self.polling_interval} seconds\n"
                f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await self.send_telegram_message(startup_message)
            
            # Start monitoring
            await self.monitoring_loop()
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            # Cleanup
            if self.session:
                await self.session.close()
            await self.smarkets_api.close()
            await self.smarkets_scraper.close()
            await self.matchbook_api.close()


async def main():
    """Main entry point."""
    bot = DrawLiabilityBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        raise


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
