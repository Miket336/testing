"""
Smarkets API client for fetching draw liability data.
"""

import asyncio
import logging
from typing import Dict, Optional
import aiohttp
import json
import os
import psycopg2
from datetime import datetime

logger = logging.getLogger(__name__)


class SmarketsAPI:
    """Client for interacting with Smarkets betting exchange API."""
    
    def __init__(self, username: str, password: str, bot=None, threshold=6000):
        self.username = username
        self.password = password
        self.base_url = "https://api.smarkets.com"
        self.session = None
        self.session_token = None
        self.bot = bot  # Reference to bot for immediate alerts
        self.threshold = threshold
        
    async def initialize(self):
        """Initialize the API client and authenticate."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'DrawLiabilityBot/1.0'
            }
        )
        
        if self.username and self.password:
            await self.authenticate()
        else:
            logger.warning("Smarkets credentials not provided - running in limited mode")
    
    async def authenticate(self):
        """Authenticate with Smarkets API."""
        try:
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            async with self.session.post(
                f"{self.base_url}/v3/sessions/",
                json=auth_data
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    self.session_token = data.get('token')
                    
                    # Update session headers with auth token
                    self.session.headers.update({
                        'Authorization': f'Session-Token {self.session_token}'
                    })
                    
                    logger.info("Successfully authenticated with Smarkets")
                else:
                    error_text = await response.text()
                    logger.error(f"Smarkets authentication failed: {response.status} - {error_text}")
                    
        except Exception as e:
            logger.error(f"Error authenticating with Smarkets: {e}")
    
    async def get_draw_liability(self) -> Optional[Dict]:
        """
        Get current draw liability data from Smarkets.
        Returns dictionary with liability information or None if error.
        """
        try:
            if not self.session:
                await self.initialize()
            
            logger.info("Smarkets: Starting to fetch events...")
            # Get all available football matches (new, live, upcoming, suspended)
            events_url = f"{self.base_url}/v3/events/"
            params = {
                'type': 'football_match',
                'state': 'upcoming', 
                'limit': 10  # Just a few matches to check values
            }
            
            async with self.session.get(events_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch events: {response.status}")
                    return None
                
                events_data = await response.json()
                events = events_data.get('events', [])
                logger.info(f"Smarkets: Found {len(events)} events to process")
                
                total_liability = 0.0
                draw_markets_count = 0
                
                # Process each event to find draw markets
                for event in events:
                    event_id = event.get('id')
                    event_name = event.get('name', 'Unknown Event')
                    event_state = event.get('state', 'Unknown')
                    logger.info(f"Smarkets: Processing event '{event_name}' (State: {event_state})")
                    
                    if not event_id:
                        continue
                    
                    # Get markets for this event
                    markets_url = f"{self.base_url}/v3/events/{event_id}/markets/"
                    
                    try:
                        async with self.session.get(markets_url) as market_response:
                            if market_response.status == 200:
                                markets_data = await market_response.json()
                                markets = markets_data.get('markets', [])
                                
                                # Look for match odds markets (containing draw)
                                for market in markets:
                                    market_type = market.get('market_type', {}).get('name', '')
                                    # Only process main match result markets for speed
                                    if market_type in ['WINNER_3_WAY', 'MATCH_ODDS', 'FULL_TIME_RESULT']:
                                        logger.info(f"Smarkets: Found draw market for '{event_name}' - Market: {market_type}")
                                        
                                        # Get contracts (selections) for this market
                                        market_id = market.get('id')
                                        contracts_url = f"{self.base_url}/v3/markets/{market_id}/contracts/"
                                        contracts_params = {
                                            'include': 'prices',
                                            'depth': '3'
                                        }
                                        
                                        async with self.session.get(contracts_url, params=contracts_params) as contracts_response:
                                            logger.info(f"Smarkets: Contracts response status for '{event_name}': {contracts_response.status}")
                                            if contracts_response.status == 200:
                                                contracts_data = await contracts_response.json()
                                                contracts = contracts_data.get('contracts', [])
                                                logger.info(f"Smarkets: Found {len(contracts)} contracts for '{event_name}': {[c.get('name', '') for c in contracts]}")
                                                
                                                # Find the draw contract
                                                for contract in contracts:
                                                    contract_name = contract.get('name', '').lower()
                                                    logger.info(f"Smarkets: Checking contract '{contract_name}' for draw in '{event_name}'")
                                                    if 'draw' in contract_name or 'tie' in contract_name:
                                                        logger.info(f"Smarkets: Found draw contract '{contract_name}' in '{event_name}'")
                                                        
                                                        # Use correct quotes endpoint from API documentation
                                                        contract_id = contract.get('id')
                                                        market_id = contract.get('market_id')
                                                        
                                                        # Use the correct /quotes/ endpoint from their API docs
                                                        quotes_url = f"{self.base_url}/v3/markets/{market_id}/quotes/"
                                                        
                                                        async with self.session.get(quotes_url) as quotes_response:
                                                            logger.info(f"Smarkets: Quotes API response for '{event_name}': {quotes_response.status}")
                                                            if quotes_response.status == 200:
                                                                quotes_data = await quotes_response.json()
                                                                logger.info(f"Smarkets: Quotes data for market {market_id}: {quotes_data}")
                                                                
                                                                # Look for this contract's quote data - quotes are indexed by contract_id
                                                                contract_quotes = quotes_data.get(str(contract_id))
                                                                if contract_quotes and 'offers' in contract_quotes:
                                                                    offers = contract_quotes['offers']
                                                                    logger.info(f"Smarkets: Offers (lay side) for '{contract_name}' (contract {contract_id}): {offers}")
                                                                    
                                                                    for offer in offers:
                                                                        # Proper Smarkets API conversion (based on official documentation research)
                                                                        raw_quantity = float(offer.get('quantity', 0))
                                                                        raw_price = float(offer.get('price', 0))
                                                                        
                                                                        # CORRECT Smarkets API conversions:
                                                                        # Price is implied probability percentage -> convert to decimal odds
                                                                        odds = 10000 / raw_price if raw_price > 0 else 0
                                                                        # Quantity is in micro-units -> convert to pounds (divide by 100000)
                                                                        quantity = raw_quantity / 100000
                                                                        
                                                                        price = raw_price  # Keep raw for logging
                                                                        
                                                                        if odds > 1 and quantity > 0:
                                                                            liability = quantity * odds  # Liability is unmatched amount * odds for lay bets
                                                                            logger.info(f"Smarkets: RAW API - price: {price}, quantity: {offer.get('quantity', 0)}")
                                                                            logger.info(f"Smarkets: CONVERTED - £{quantity:.2f} at {odds:.2f} odds for '{contract_name}' in '{event_name}' (raw: price={raw_price}, qty={raw_quantity})")
                                                                            total_liability += liability
                                                                            
                                                                            # Send immediate alert if unmatched amount above threshold
                                                                            if self.bot and quantity > self.threshold:
                                                                                alert_message = (
                                                                                    f"🚨 HIGH UNMATCHED ALERT!\n\n"
                                                                                    f"Exchange: Smarkets\n"
                                                                                    f"Event: {event_name}\n"
                                                                                    f"Market: {contract_name}\n"
                                                                                    f"Unmatched: £{quantity:,.2f}\n"
                                                                                    f"Odds: {odds:.2f}\n"
                                                                                    f"Liability if layed: £{liability:,.2f}\n"
                                                                                    f"Threshold: £{self.threshold:,.2f}\n"
                                                                                    f"Excess: £{quantity - self.threshold:,.2f}"
                                                                                )
                                                                                asyncio.create_task(self.bot.send_telegram_message(alert_message))
                                                                    
                                                                    draw_markets_count += 1
                                                                else:
                                                                    logger.info(f"Smarkets: No offers (lay side) found for contract {contract_id} in '{contract_name}'")
                                                            else:
                                                                logger.warning(f"Smarkets: Quotes API failed with status {quotes_response.status}")
                                                        
                                                        # Small delay between market quote requests
                                                        await asyncio.sleep(0.1)
                                    
                                    # Add small delay to avoid rate limiting
                                    await asyncio.sleep(0.05)
                                    
                    except Exception as e:
                        logger.warning(f"Error processing event {event_id}: {e}")
                        continue
                
                logger.info(f"Smarkets: Processed {draw_markets_count} draw markets, Total liability: £{total_liability:,.2f}")
                
                return {
                    'liability': total_liability,
                    'markets_count': draw_markets_count,
                    'exchange': 'smarkets',
                    'timestamp': asyncio.get_event_loop().time()
                }
                
        except asyncio.TimeoutError:
            logger.error("Timeout fetching Smarkets data")
            return None
        except Exception as e:
            logger.error(f"Error fetching Smarkets draw liability: {e}")
            return None
    
    async def get_unmatched_draw_lays(self):
        """Get unmatched lay amounts specifically for draw markets."""
        try:
            logger.info("🎯 Fetching unmatched draw lay amounts...")
            
            # Try multiple approaches to find Premier League events
            logger.info("🔍 Trying different API approaches for Premier League...")
            
            # Approach 1: Try competition filter
            events_url = f"{self.base_url}/v3/events/"
            params = {
                'type': 'football_match',
                'state': 'upcoming', 
                'limit': 1000  # Much higher limit to find more Premier League matches
            }
            
            async with self.session.get(events_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch events: {response.status}")
                    return None
                
                events_data = await response.json()
                all_events = events_data.get('events', [])
                logger.info(f"🔍 Found {len(all_events)} total football events")
                
                # Log first few event names to debug
                for i, event in enumerate(all_events[:5]):
                    logger.info(f"🔍 Sample event {i+1}: {event.get('name', 'No name')}")
                
                # Expanded Premier League team variations for better matching
                premier_league_teams = [
                    'arsenal', 'aston villa', 'brentford', 'brighton', 'burnley', 'chelsea', 
                    'crystal palace', 'everton', 'fulham', 'liverpool', 'luton', 'manchester city', 
                    'manchester united', 'newcastle', 'nottingham forest', 'sheffield united', 
                    'tottenham', 'west ham', 'wolverhampton', 'bournemouth',
                    # Add variations
                    'man city', 'man utd', 'man united', 'spurs', 'wolves', 
                    'brighton & hove albion', 'crystal palace fc', 'nottm forest',
                    'west ham united', 'tottenham hotspur', 'liverpool fc', 'arsenal fc',
                    'chelsea fc', 'manchester city fc', 'manchester united fc'
                ]
                
                # Filter for Premier League events only
                premier_league_events = []
                for event in all_events:
                    event_name = event.get('name', '').lower()
                    # Check if event contains Premier League teams
                    if any(team in event_name for team in premier_league_teams):
                        premier_league_events.append(event)
                        logger.info(f"✅ Premier League event found: {event.get('name', 'Unknown')}")
                
                events = premier_league_events
                logger.info(f"🎯 Found {len(events)} Premier League events out of {len(all_events)} total events")
                
                # Clear existing data and store all new data
                self._clear_old_data()
                
                draw_markets = []
                total_events_processed = 0
                
                # Process each event to find draw markets and store in database
                for event in events:
                    total_events_processed += 1
                    if total_events_processed % 10 == 0:
                        logger.info(f"📊 Processed {total_events_processed}/{len(events)} events...")
                    event_id = event.get('id')
                    event_name = event.get('name', 'Unknown Event')
                    
                    if not event_id:
                        continue
                    
                    # Get markets for this event
                    markets_url = f"{self.base_url}/v3/events/{event_id}/markets/"
                    
                    try:
                        async with self.session.get(markets_url) as market_response:
                            if market_response.status == 200:
                                markets_data = await market_response.json()
                                markets = markets_data.get('markets', [])
                                
                                # Focus ONLY on main match result markets
                                for market in markets:
                                    market_type = market.get('market_type', {}).get('name', '')
                                    # Only process main match result markets (not corners, cards, etc.)
                                    if market_type in ['WINNER_3_WAY', 'MATCH_ODDS', 'FULL_TIME_RESULT', 'MATCH_RESULT']:
                                        logger.info(f"✅ Processing match result market: {market_type} for {event_name}")
                                        
                                        # Get contracts (selections) for this market
                                        market_id = market.get('id')
                                        contracts_url = f"{self.base_url}/v3/markets/{market_id}/contracts/"
                                        contracts_params = {
                                            'include': 'prices',
                                            'depth': '3'
                                        }
                                        
                                        async with self.session.get(contracts_url, params=contracts_params) as contracts_response:
                                            if contracts_response.status == 200:
                                                contracts_data = await contracts_response.json()
                                                contracts = contracts_data.get('contracts', [])
                                                
                                                # Find the draw contract
                                                for contract in contracts:
                                                    contract_name = contract.get('name', '').lower()
                                                    if 'draw' in contract_name or 'tie' in contract_name:
                                                        
                                                        # Get quotes for this draw contract
                                                        contract_id = contract.get('id')
                                                        quotes_url = f"{self.base_url}/v3/markets/{market_id}/quotes/"
                                                        
                                                        async with self.session.get(quotes_url) as quotes_response:
                                                            if quotes_response.status == 200:
                                                                quotes_data = await quotes_response.json()
                                                                
                                                                # Look for this contract's quote data
                                                                contract_quotes = quotes_data.get(str(contract_id))
                                                                if contract_quotes and 'offers' in contract_quotes:
                                                                    offers = contract_quotes['offers']
                                                                    
                                                                    for offer in offers:
                                                                        raw_quantity = float(offer.get('quantity', 0))
                                                                        raw_price = float(offer.get('price', 0))
                                                                        
                                                                        # Convert Smarkets API values (same as working code)
                                                                        odds = 10000 / raw_price if raw_price > 0 else 0
                                                                        unmatched_amount = raw_quantity / 100000
                                                                        
                                                                        if unmatched_amount >= 100:  # Store all significant amounts
                                                                            market_data = {
                                                                                'event_name': event_name,
                                                                                'market_name': market_type,
                                                                                'contract_name': contract.get('name', 'Draw'),
                                                                                'unmatched_amount': unmatched_amount,
                                                                                'odds': round(odds, 2),
                                                                                'contract_id': contract_id
                                                                            }
                                                                            
                                                                            # Store in database
                                                                            self._store_market_data(market_data)
                                                                            draw_markets.append(market_data)
                                                                            
                                                                            if unmatched_amount >= 1000:  # Log significant amounts
                                                                                logger.info(f"🎯 Draw lay: {event_name} - £{unmatched_amount:,.2f} at {odds:.2f}")
                                        
                                        # Small delay between requests
                                        await asyncio.sleep(0.1)
                    
                    except Exception as e:
                        logger.warning(f"Error processing event {event_id}: {e}")
                        continue
                
                # Filter from database for amounts over £2k
                high_value_markets = self._get_high_value_markets(2000)
                
                logger.info(f"📊 Stored {len(draw_markets)} Premier League draw lay markets in database")
                logger.info(f"🎯 Found {len(high_value_markets)} Premier League markets with unmatched amounts over £2,000")
                
                if len(high_value_markets) == 0 and len(draw_markets) > 0:
                    # Show top 3 highest amounts for context
                    top_markets = self._get_high_value_markets(0)[:3]
                    logger.info("📈 Top Premier League draw lay amounts available:")
                    for market in top_markets:
                        logger.info(f"   💷 {market['event_name']}: £{market['unmatched_amount']:,.2f}")
                
                return {'markets': high_value_markets}
            
        except Exception as e:
            logger.error(f"Error getting unmatched draw lays: {e}")
            return None
    
    def _get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    
    def _clear_old_data(self):
        """Clear old market data from database."""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM draw_lay_markets WHERE created_at < NOW() - INTERVAL '1 hour'")
                    conn.commit()
                    logger.info("🗑️ Cleared old market data from database")
        except Exception as e:
            logger.error(f"Error clearing old data: {e}")
    
    def _store_market_data(self, market_data):
        """Store market data in database."""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO draw_lay_markets 
                        (event_name, market_name, contract_name, unmatched_amount, odds, contract_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        market_data['event_name'],
                        market_data['market_name'],
                        market_data['contract_name'],
                        market_data['unmatched_amount'],
                        market_data['odds'],
                        market_data['contract_id']
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error storing market data: {e}")
    
    def _get_high_value_markets(self, threshold):
        """Get markets with unmatched amounts over threshold from database."""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT event_name, market_name, contract_name, unmatched_amount, odds, contract_id
                        FROM draw_lay_markets 
                        WHERE unmatched_amount >= %s
                        ORDER BY unmatched_amount DESC
                    """, (threshold,))
                    
                    results = cur.fetchall()
                    markets = []
                    for row in results:
                        markets.append({
                            'event_name': row[0],
                            'market_name': row[1], 
                            'contract_name': row[2],
                            'unmatched_amount': float(row[3]),
                            'odds': float(row[4]),
                            'contract_id': row[5]
                        })
                        logger.info(f"🎯 HIGH VALUE: {row[0]} - £{float(row[3]):,.2f} at {float(row[4]):.2f}")
                    
                    return markets
        except Exception as e:
            logger.error(f"Error getting high value markets: {e}")
            return []
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
