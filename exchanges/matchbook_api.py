"""
Matchbook API client for fetching draw liability data.
"""

import asyncio
import logging
from typing import Dict, Optional
import aiohttp
import json

logger = logging.getLogger(__name__)


class MatchbookAPI:
    """Client for interacting with Matchbook betting exchange API."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.base_url = "https://www.matchbook.com/edge/rest"
        self.session = None
        self.session_token = None
        
    async def initialize(self):
        """Initialize the API client and authenticate."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'DrawLiabilityBot/1.0'
            }
        )
        
        # DEBUG: Check if credentials are loaded
        logger.info(f"Matchbook credentials status: username={'✅ SET' if self.username else '❌ MISSING'}, password={'✅ SET' if self.password else '❌ MISSING'}")
        
        if self.username and self.password:
            logger.info("🔐 STARTING AUTHENTICATION PROCESS...")
            auth_success = await self.authenticate()
            if not auth_success:
                logger.error("❌ AUTHENTICATION FAILED - Cannot access Premier League data!")
            else:
                logger.info("✅ AUTHENTICATION COMPLETED SUCCESSFULLY!")
        else:
            logger.warning("Matchbook credentials not provided - running in limited mode")
    
    async def authenticate(self):
        """Authenticate with Matchbook API using research-based fixes."""
        try:
            # RESEARCH FIX: Ensure proper JSON encoding as per Stack Overflow solution
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            # CRITICAL FIX: Use explicit Content-Type header as researched
            auth_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # RESEARCH FIX: Use data + json.dumps() approach that was confirmed working
            import json
            
            async with self.session.post(
                f"{self.base_url}/security/session",
                data=json.dumps(auth_data),
                headers=auth_headers
            ) as response:
                logger.info(f"Matchbook auth response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    self.session_token = data.get('session-token')
                    user_id = data.get('user-id')
                    
                    if self.session_token:
                        # CRITICAL FIX: Update session headers with proper session token
                        self.session.headers.update({
                            'session-token': self.session_token,
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        })
                        
                        logger.info(f"✅ AUTHENTICATION SUCCESS! User ID: {user_id}, Session Token: {self.session_token[:10]}...")
                        return True
                    else:
                        logger.error("No session token in response")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ AUTHENTICATION FAILED: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ ERROR AUTHENTICATING: {e}")
            return False
    
    async def get_draw_liability(self) -> Optional[Dict]:
        """
        Get current draw liability data from Matchbook.
        Returns dictionary with liability information or None if error.
        """
        logger.info("🚨 MATCHBOOK METHOD CALLED - Starting get_draw_liability")
        try:
            # AGGRESSIVE DEBUG - Always show current state
            logger.info(f"🔍 DEBUG STATE - Session exists: {self.session is not None}, Token exists: {self.session_token is not None}")
            logger.info(f"🔍 DEBUG TOKEN VALUE: {self.session_token[:10] if self.session_token else 'NONE'}")
            
            # FORCE AUTHENTICATION CHECK - ensure we always authenticate
            if not self.session or not self.session_token:
                logger.info("🔄 FORCING AUTHENTICATION - No session token found")
                await self.initialize()
            else:
                logger.info(f"🔐 Session exists with token: {self.session_token[:10] if self.session_token else 'None'}...")
            
            # COMPREHENSIVE SEARCH - test ALL sport IDs to find Premier League
            logger.info("Matchbook: COMPREHENSIVE SEARCH for Premier League - testing ALL sport IDs...")
            logger.info(f"🔓 AUTHENTICATION DEBUG - Session exists: {self.session is not None}, Token: {self.session_token[:10] if self.session_token else 'NONE'}")
            logger.info(f"🔑 CREDENTIALS DEBUG - Username: {'SET' if self.username else 'MISSING'}, Password: {'SET' if self.password else 'MISSING'}")
            soccer_sport_id = None
            
            # AGGRESSIVE PREMIER LEAGUE HUNT - Test sport ID 1 with maximum events
            test_url_1 = f"{self.base_url}/events?sport-ids=1&per-page=100"  # Increased to 100
            try:
                async with self.session.get(test_url_1) as test_response:
                    logger.info(f"🔍 Testing Sport ID 1 - Response Status: {test_response.status}")
                    if test_response.status == 200:
                        test_data = await test_response.json()
                        test_events = test_data.get('events', [])
                        if test_events:
                            logger.info(f"📊 Sport ID 1 has {len(test_events)} events - SEARCHING ALL FOR PREMIER LEAGUE:")
                            premier_league_found = []
                            for i, event in enumerate(test_events):
                                event_name = event.get('name', '')
                                name_lower = event_name.lower()
                                
                                # Check for Premier League teams specifically
                                if ('burnley' in name_lower and 'sunderland' in name_lower) or \
                                   ('manchester' in name_lower and 'tottenham' in name_lower) or \
                                   ('afc bournemouth' in name_lower) or \
                                   ('wolverhampton' in name_lower) or \
                                   ('brentford' in name_lower and 'aston villa' in name_lower):
                                    logger.info(f"    🎯 FOUND PREMIER LEAGUE MATCH: {event_name}")
                                    premier_league_found.append(event_name)
                                    soccer_sport_id = '1'
                                elif i < 20:  # Log first 20 for debugging
                                    logger.info(f"    Event {i+1}: '{event_name}'")
                            
                            if premier_league_found:
                                logger.info(f"🏆 PREMIER LEAGUE MATCHES FOUND IN SPORT ID 1: {len(premier_league_found)} matches!")
                                for match in premier_league_found:
                                    logger.info(f"   ⚽ {match}")
                        else:
                            logger.info("📭 Sport ID 1 has no events")
                    else:
                        logger.warning(f"❌ Sport ID 1 request failed: {test_response.status}")
            except Exception as e:
                logger.error(f"💥 Error testing sport ID 1: {e}")
            
            # EXHAUSTIVE PREMIER LEAGUE SEARCH - Test wider range with more events each
            if not soccer_sport_id:
                logger.info("🔎 EXHAUSTIVE PREMIER LEAGUE SEARCH - Testing ALL sport IDs with 50 events each...")
                # Test much wider range including 0 and higher numbers
                for test_id in range(0, 30):  # Extended to 30 sport IDs
                    test_id = str(test_id)
                    logger.info(f"🔍 Testing sport ID {test_id} for Premier League...")
                    test_url = f"{self.base_url}/events?sport-ids={test_id}&per-page=50"  # Increased from 3 to 50
                    
                    try:
                        async with self.session.get(test_url) as test_response:
                            if test_response.status == 200:
                                test_data = await test_response.json()
                                test_events = test_data.get('events', [])
                                
                                if test_events:
                                    first_event = test_events[0]
                                    event_name = first_event.get('name', '')
                                    logger.info(f"Matchbook: Sport ID {test_id} sample event: '{event_name}'")
                                    
                                    # Check if this looks like soccer
                                    name_lower = event_name.lower()
                                    
                                    # Enhanced soccer detection - Premier League and other teams
                                    premier_league_teams = ['arsenal', 'chelsea', 'liverpool', 'manchester', 'tottenham', 'newcastle', 
                                                           'brighton', 'aston villa', 'west ham', 'crystal palace', 'fulham', 'brentford', 
                                                           'nottingham forest', 'everton', 'wolves', 'leicester', 'bournemouth', 
                                                           'burnley', 'luton', 'sunderland', 'leeds', 'sheffield']
                                    
                                    soccer_teams = ['fc', 'united', 'city', 'real', 'barcelona', 'milan', 'juventus', 'bayern', 'ajax', 'sporting']
                                    
                                    # Individual sport patterns (avoid these - actual names not team names)
                                    individual_sports = ['lynx', 'fever', 'volynets', 'fett', 'rafferty', 'chamberlain', 'kubler', 'prizmic', 'mochizuki', 'galan']  # Tennis player names
                                    american_sports = ['cowboys', 'patriots', 'yankees', 'red sox', 'pirates', 'eagles', 'packers']
                                    tennis_keywords = ['kubler', 'prizmic', 'mochizuki', 'galan', 'vandewinkel', 'hon', 'salkova', 'marino']  # Tennis players
                                    
                                    # Check for soccer indicators
                                    has_premier_league = any(team in name_lower for team in premier_league_teams)
                                    has_team_indicator = any(team in name_lower for team in soccer_teams)
                                    has_vs_pattern = ' vs ' in name_lower or ' v ' in name_lower
                                    is_individual_sport = any(indiv in name_lower for indiv in individual_sports)
                                    is_american_sport = any(american in name_lower for american in american_sports)
                                    is_tennis = any(tennis in name_lower for tennis in tennis_keywords)  # Tennis detection
                                    
                                    # Look specifically for Premier League matches
                                    if 'burnley' in name_lower and 'sunderland' in name_lower:
                                        soccer_sport_id = test_id
                                        logger.info(f"Matchbook: 🎯 FOUND BURNLEY vs SUNDERLAND! Sport ID {test_id}")
                                        break
                                    elif has_premier_league or (has_team_indicator or has_vs_pattern) and not is_individual_sport and not is_american_sport and not is_tennis:
                                        soccer_sport_id = test_id
                                        logger.info(f"Matchbook: ✅ FOUND SOCCER! Sport ID {test_id} - Sample: '{event_name}'")
                                        break
                                    else:
                                        if is_tennis:
                                            logger.info(f"Matchbook: Sport ID {test_id} is TENNIS (not soccer): '{event_name}'")
                                        else:
                                            logger.info(f"Matchbook: Sport ID {test_id} appears to be individual/other sport: '{event_name}'")
                                else:
                                    logger.info(f"Matchbook: Sport ID {test_id} has no events")
                            else:
                                logger.info(f"Matchbook: Sport ID {test_id} returned {test_response.status}")
                    except Exception as e:
                        logger.info(f"Matchbook: Sport ID {test_id} failed: {e}")
            
            if not soccer_sport_id:
                logger.warning("Matchbook: No soccer sport ID found in common range, testing extended range...")
                # Try extended range of sport IDs
                for test_id in ['12', '13', '14', '15', '16', '17', '18', '19', '20']:
                    logger.info(f"Matchbook: Testing extended sport ID {test_id}")
                    test_url = f"{self.base_url}/events?sport-ids={test_id}&per-page=3"
                    
                    try:
                        async with self.session.get(test_url) as test_response:
                            if test_response.status == 200:
                                test_data = await test_response.json()
                                test_events = test_data.get('events', [])
                                
                                if test_events:
                                    first_event = test_events[0]
                                    event_name = first_event.get('name', '')
                                    logger.info(f"Matchbook: Extended sport ID {test_id} sample: '{event_name}'")
                                    
                                    # Check for soccer (including Arabic teams)
                                    name_lower = event_name.lower()
                                    soccer_teams = ['fc', 'united', 'city', 'real', 'barcelona', 'milan', 'arsenal', 'liverpool', 'chelsea', 'juventus', 'bayern']
                                    arabic_teams = ['al-', 'al ', ' al']  # Arabic team prefixes
                                    has_team = any(team in name_lower for team in soccer_teams)
                                    has_arabic_team = any(arabic in name_lower for arabic in arabic_teams)
                                    is_soccer = has_team or has_arabic_team
                                    
                                    if is_soccer:
                                        soccer_sport_id = test_id
                                        logger.info(f"Matchbook: ✅ FOUND SOCCER in extended range! Sport ID {test_id} - '{event_name}'")
                                        break
                                else:
                                    logger.info(f"Matchbook: Extended sport ID {test_id} has no events")
                    except Exception as e:
                        logger.info(f"Matchbook: Extended sport ID {test_id} failed: {e}")
                
                if not soccer_sport_id:
                    logger.error("Matchbook: CONCLUSION - No soccer events found on Matchbook")
                    return {'liability': 0.0, 'markets_count': 0, 'exchange': 'matchbook'}
            
            # Now get soccer events
            logger.info(f"Matchbook: Using soccer sport ID {soccer_sport_id}")
            events_url = f"{self.base_url}/events"
            params = {
                'sport-ids': str(soccer_sport_id),  # Correct soccer sport ID  
                'states': 'open,live,suspended,new,pending,closed,scheduled,upcoming',  # MAXIMUM EXPANSION: All possible states
                'exchange-type': 'back-lay',
                'odds-type': 'DECIMAL',
                'include-prices': 'true',
                'price-depth': '5',  # Increased depth to get more price levels
                'per-page': '200',   # MAXIMUM: Search more events for Premier League
                'offset': '0'        # Start from beginning
            }
            
            logger.info(f"🔍 SEARCHING FOR UPCOMING PREMIER LEAGUE - States: {params['states']}, Per-page: {params['per-page']}")
            
            async with self.session.get(events_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch Matchbook events: {response.status}")
                    return None
                
                events_data = await response.json()
                events = events_data.get('events', [])
                
                # Show sample of leagues/tournaments being monitored
                logger.info(f"Matchbook: Processing {len(events)} events for draw markets...")
                
                # FOCUS: Search specifically for matches from user's screenshot
                screenshot_matches = [
                    ('Manchester City', 'Tottenham'), ('Tottenham', 'Manchester City'),
                    ('AFC Bournemouth', 'Wolverhampton'), ('Bournemouth', 'Wolverhampton'),
                    ('Brentford', 'Aston Villa'), ('Aston Villa', 'Brentford'),
                    ('Burnley', 'Sunderland'), ('Sunderland', 'Burnley'),
                    ('Arsenal', 'Leeds United'), ('Leeds United', 'Arsenal'),
                    ('Crystal Palace', 'Nottingham Forest'), ('Nottingham Forest', 'Crystal Palace'),
                    ('Everton', 'Brighton'), ('Brighton', 'Everton'),
                    ('Fulham', 'Manchester United'), ('Manchester United', 'Fulham'),
                    ('Newcastle United', 'Liverpool'), ('Liverpool', 'Newcastle United')
                ]
                
                logger.info("🎯 SEARCHING FOR SPECIFIC PREMIER LEAGUE MATCHES FROM USER SCREENSHOT:")
                screenshot_matches_found = 0
                
                for event in events:
                    event_name = event.get('name', 'Unknown Event')
                    event_state = event.get('state', 'unknown')
                    start_time = event.get('start', 'No time')
                    
                    # Check if this matches any from the screenshot
                    for team1, team2 in screenshot_matches:
                        if team1 in event_name and team2 in event_name:
                            screenshot_matches_found += 1
                            logger.info(f"  🎯 SCREENSHOT MATCH FOUND: {event_name} [{event_state}] - {start_time}")
                
                logger.info(f"📊 Screenshot matches found: {screenshot_matches_found}")
                
                # Also do the general Premier League search
                sample_events = events[:20]  # Show sample for debugging
                if sample_events:
                    logger.info("Matchbook: Sample of all matches being monitored:")
                    premier_league_found = False
                    for i, event in enumerate(sample_events):
                        event_name = event.get('name', 'Unknown Event')
                        event_state = event.get('state', 'unknown')
                        start_time = event.get('start', 'No time')
                        logger.info(f"  {i+1}. {event_name} [{event_state}] - {start_time}")
                        
                        # COMPREHENSIVE Premier League team detection
                        pl_teams = ['Arsenal', 'Chelsea', 'Liverpool', 'Manchester United', 'Manchester City', 
                                   'Tottenham', 'Newcastle', 'Brighton', 'Aston Villa', 'West Ham', 
                                   'Crystal Palace', 'Fulham', 'Brentford', 'Nottingham Forest', 
                                   'Everton', 'Wolves', 'Leicester', 'Bournemouth', 'Sheffield United', 
                                   'Burnley', 'Luton', 'Leeds United', 'Sunderland', 'Wolverhampton']
                        
                        # More precise Premier League matching 
                        if (any(team in event_name for team in pl_teams) and 
                            'U21' not in event_name and 'Reserve' not in event_name and 'Under' not in event_name):
                            premier_league_found = True
                            logger.info(f"    ⚽ PREMIER LEAGUE MATCH DETECTED: {event_name}")
                    
                    if not premier_league_found:
                        logger.info("    ❌ NO PREMIER LEAGUE MATCHES FOUND in current sample")
                        
                    # Also check full list for any Premier League matches
                    total_pl_matches = 0
                    for event in events:
                        event_name = event.get('name', 'Unknown Event')
                        if any(team in event_name for team in pl_teams) and 'U21' not in event_name and 'Reserve' not in event_name:
                            total_pl_matches += 1
                    
                    logger.info(f"Matchbook: Premier League matches in full dataset: {total_pl_matches} out of {len(events)} total matches")
                
                total_unmatched = 0.0
                draw_markets_count = 0
                
                # FOCUS: Track individual DRAW LAY amounts over £2,000 (your specific requirement)
                big_draw_lays = []
                
                # Process each event to find draw markets (check individual odds)
                significant_odds = []
                
                for event in events:
                    event_name = event.get('name', 'Unknown Event')
                    markets = event.get('markets', [])
                    
                    # Only look at match result markets (faster filtering)  
                    for market in markets:
                        market_name = market.get('name', '').lower()
                        market_type = market.get('type', '').lower()
                        
                        # Check for main match result markets (broader matching)
                        if (any(word in market_name for word in ['match', 'winner', 'result', '1x2', 'betting']) or 
                            'match_odds' in market_type or market.get('market-type') == 'match-odds'):
                            
                            runners = market.get('runners', [])
                            
                            # Find the draw runner
                            for runner in runners:
                                runner_name = runner.get('name', '').lower()
                                if runner_name in ['draw', 'tie'] or 'draw' in runner_name:
                                    
                                    # Get lay prices (what we could sell/lay)
                                    prices = runner.get('prices', [])
                                    
                                    for price_obj in prices:
                                        if price_obj.get('side', '').lower() == 'lay':
                                            
                                            decimal_odds = float(price_obj.get('decimal-odds', 0))
                                            available_amount = float(price_obj.get('available-amount', 0))
                                            
                                            if decimal_odds > 1 and available_amount > 0:
                                                # Track total unmatched
                                                total_unmatched += available_amount
                                                
                                                # Check if this individual DRAW LAY has over £2,000
                                                if available_amount >= 2000:
                                                    draw_lay_alert = {
                                                        'event': event_name,
                                                        'odds': decimal_odds,
                                                        'amount': available_amount,
                                                        'type': 'DRAW LAY'
                                                    }
                                                    significant_odds.append(draw_lay_alert)
                                                    big_draw_lays.append(draw_lay_alert)
                                                    
                                                    # IMMEDIATE ALERT for DRAW LAY over £2,000
                                                    logger.info(f"🚨 DRAW LAY ALERT: {event_name} - £{available_amount:.2f} available to LAY draw at {decimal_odds}")
                                                    
                                                # SPECIAL: Log Burnley vs Sunderland specifically (from user's screenshot)
                                                if ('Burnley' in event_name and 'Sunderland' in event_name) or ('Sunderland' in event_name and 'Burnley' in event_name):
                                                    logger.info(f"🎯 BURNLEY vs SUNDERLAND FOUND: £{available_amount:.2f} at {decimal_odds} - MATCHES USER SCREENSHOT!")
                                                    
                                                # Log all DRAW LAY amounts for monitoring (including smaller ones)
                                                elif available_amount >= 100:  # Show any substantial amounts
                                                    logger.info(f"💰 Draw lay available: {event_name} - £{available_amount:.2f} at {decimal_odds}")
                                    
                                    draw_markets_count += 1
                                    break  # Found draw runner, move to next market
                    
                
                # Log significant individual odds
                if significant_odds:
                    logger.info(f"Matchbook: INDIVIDUAL ODDS OVER £2,000 UNMATCHED:")
                    # Sort by highest amount first
                    significant_odds.sort(key=lambda x: x['amount'], reverse=True)
                    for odds_info in significant_odds:
                        amount = odds_info['amount']
                        odds = odds_info['odds']
                        event = odds_info['event']
                        logger.info(f"  🚨 {event}: £{amount:,.0f} at {odds:.2f} odds")
                
                logger.info(f"Matchbook: Processed {draw_markets_count} draw markets, Total unmatched: £{total_unmatched:,.2f}")
                
                # Return the highest individual odds amount for threshold checking
                max_individual_odds = max([o['amount'] for o in significant_odds], default=0)
                
                return {
                    'liability': max_individual_odds,  # Now returns highest individual odds amount
                    'markets_count': draw_markets_count,
                    'exchange': 'matchbook',
                    'significant_odds': significant_odds,  # Include the qualifying odds
                    'timestamp': asyncio.get_event_loop().time()
                }
                
        except asyncio.TimeoutError:
            logger.error("Timeout fetching Matchbook data")
            return None
        except Exception as e:
            logger.error(f"Error fetching Matchbook draw liability: {e}")
            return None
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
