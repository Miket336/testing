import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import re

logger = logging.getLogger(__name__)

class SmarketsWebScraper:
    def __init__(self, bot=None, threshold=2000):
        self.bot = bot
        self.threshold = threshold
        self.driver = None
        
    async def initialize_driver(self):
        """Initialize the Chrome driver with headless options."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Mobile emulation for cleaner, simpler DOM structure
            mobile_emulation = {
                "deviceMetrics": {
                    "width": 375,
                    "height": 812,
                    "pixelRatio": 3.0
                },
                "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
            }
            chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
            
            # Mobile user agent for better betting interface
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1')
            
            # Set the correct chromium binary path for Nix
            chrome_options.binary_location = '/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium-browser'
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Smarkets Scraper: Chrome driver initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Smarkets Scraper: Failed to initialize driver: {e}")
            return False
    
    async def get_draw_liability_web(self):
        """Scrape draw liability from Smarkets website directly."""
        if not self.driver:
            if not await self.initialize_driver():
                return None
        
        try:
            total_liability = 0
            matches_found = 0
            
            # Go to Smarkets mobile football page
            logger.info("Smarkets Scraper: Loading football markets (mobile)...")
            self.driver.get("https://m.smarkets.com/sport/football")
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Find all match elements
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Look for match/event containers with more specific selectors
            match_selectors = [
                '[data-testid*="event"]', '[class*="event"]', '[class*="match"]',
                '.market-row', '.event-row', '.fixture', '[data-cy*="event"]'
            ]
            
            match_elements = []
            for selector in match_selectors:
                elements = soup.select(selector)
                match_elements.extend(elements)
            
            # Remove duplicates and filter
            unique_matches = []
            seen_texts = set()
            for elem in match_elements:
                text = elem.get_text(strip=True)[:100]  # First 100 chars to identify uniqueness
                if text and text not in seen_texts and ('vs' in text.lower() or 'v ' in text):
                    unique_matches.append(elem)
                    seen_texts.add(text)
            
            logger.info(f"Smarkets Scraper: Found {len(unique_matches)} unique match containers")
            
            for match_element in unique_matches[:10]:  # Limit to first 10 matches
                try:
                    # Extract match name
                    match_name = self.extract_match_name(match_element)
                    if not match_name:
                        continue
                    
                    logger.info(f"Smarkets Scraper: Processing match: {match_name}")
                    
                    # Navigate to the actual match betting page where LAY values are shown
                    if await self.navigate_to_match_betting_page(match_name):
                        # Extract blue LAY data from the betting interface
                        draw_data = self.extract_blue_lay_data_from_betting_page()
                        
                        if draw_data:
                            matches_found += 1
                            for odds, unmatched, liability in draw_data:
                                total_liability += unmatched  # Use unmatched amount as liability
                                
                                logger.info(f"Smarkets Scraper: {match_name} - £{unmatched:.2f} unmatched at {odds:.2f} odds")
                                
                                # Send alert if above threshold
                                if self.bot and unmatched > self.threshold:
                                    alert_message = (
                                        f"🚨 HIGH LAY OPPORTUNITY!\n\n"
                                        f"Exchange: Smarkets (Web)\n"
                                        f"Event: {match_name}\n"
                                        f"Market: Draw LAY\n"
                                        f"Blue LAY Available: £{unmatched:,.2f}\n"
                                        f"Odds: {odds:.2f}\n"
                                        f"Threshold: £{self.threshold:,.2f}\n"
                                        f"Excess: £{unmatched - self.threshold:,.2f}"
                                    )
                                    asyncio.create_task(self.bot.send_telegram_message(alert_message))
                        
                        # Go back to main page for next match
                        self.driver.get("https://smarkets.com/sport/football")
                        await asyncio.sleep(2)
                    
                
                except Exception as e:
                    logger.warning(f"Smarkets Scraper: Error processing match element: {e}")
                    continue
            
            logger.info(f"Smarkets Scraper: Processed {matches_found} matches, Total liability: £{total_liability:,.2f}")
            
            return {
                'liability': total_liability,
                'markets_count': matches_found,
                'exchange': 'smarkets_web',
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Smarkets Scraper: Error scraping website: {e}")
            return None
    
    def extract_match_name(self, match_element):
        """Extract clean match name from match element."""
        try:
            # Get the text content and look for match patterns
            full_text = match_element.get_text(strip=True)
            
            # Split by common separators and look for team vs team pattern
            lines = full_text.split('\n')
            for line in lines:
                line = line.strip()
                if (' vs ' in line.lower() or ' v ' in line) and len(line) < 100:
                    # Clean up the line - remove all extra text
                    line = re.sub(r'in \d+ (minute|hour)s?', '', line, flags=re.I)  # Remove time info
                    line = re.sub(r'Traded:\$[\d,]+', '', line)  # Remove trading volume
                    line = re.sub(r'\d+:\d+', '', line)  # Remove times
                    line = re.sub(r'\d+/\d+/\d+', '', line)  # Remove dates
                    line = re.sub(r'[\$£][\d,]+', '', line)  # Remove money amounts
                    line = re.sub(r'\s+', ' ', line).strip()  # Clean extra spaces
                    
                    if line and len(line) > 5 and ' vs ' in line.lower():
                        return line
            
            return None
            
        except Exception as e:
            logger.debug(f"Smarkets Scraper: Error extracting match name: {e}")
            return None
    
    def extract_blue_lay_data_from_betting_page(self):
        """Extract blue LAY values from the actual betting interface page."""
        try:
            draw_data = []
            
            # Get current page source
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Look for draw market section first
            draw_selectors = [
                '[data-testid*="draw"]',
                '[class*="draw"]', 
                '*:contains("Draw")',
                '*:contains("X")',
                '.market-outcome:contains("Draw")'
            ]
            
            draw_elements = []
            for selector in draw_selectors:
                if ':contains(' in selector:
                    # Use text search for these
                    elements = soup.find_all(text=re.compile(r'Draw|X', re.I))
                    for text in elements:
                        if text.parent:
                            draw_elements.append(text.parent)
                else:
                    elements = soup.select(selector)
                    draw_elements.extend(elements)
            
            logger.info(f"Smarkets Scraper: Found {len(draw_elements)} potential draw elements")
            
            # Look for unique LAY/blue button combinations (avoid duplicates)
            seen_combinations = set()
            
            for draw_element in draw_elements[:3]:  # Check first 3 draw elements only
                try:
                    # Find the draw market container more precisely
                    market_container = draw_element
                    for _ in range(4):  # Go up to find market row/container
                        if market_container.parent and any(cls in str(market_container.parent.get('class', [])) for cls in ['market', 'outcome', 'selection']):
                            market_container = market_container.parent
                        elif market_container.parent:
                            market_container = market_container.parent
                        else:
                            break
                    
                    # Look for betting buttons in this market container
                    button_selectors = [
                        'button', '[role="button"]', '.btn', '[class*="button"]',
                        '[class*="bet"]', '[data-testid*="bet"]'
                    ]
                    
                    for selector in button_selectors:
                        buttons = market_container.select(selector)
                        
                        for button in buttons:
                            button_text = button.get_text(strip=True)
                            
                            # Look for odds and amounts in button or very close elements
                            odds_match = re.search(r'([2-9]\.\d{1,2})', button_text)
                            amount_match = re.search(r'£([\d,]+)', button_text)
                            
                            if odds_match:
                                odds = float(odds_match.group(1))
                                
                                # If amount not in button, check immediate siblings
                                if not amount_match:
                                    nearby_elements = [button.next_sibling, button.previous_sibling]
                                    if button.parent:
                                        nearby_elements.extend(button.parent.find_all(text=True))
                                    
                                    for elem in nearby_elements[:5]:
                                        if elem and hasattr(elem, 'strip'):
                                            elem_text = elem.strip()
                                            amount_match = re.search(r'£([\d,]+)', elem_text)
                                            if amount_match:
                                                break
                                
                                if amount_match:
                                    unmatched = float(amount_match.group(1).replace(',', ''))
                                    
                                    # Create unique key to avoid duplicates
                                    combo_key = f"{odds:.2f}-{unmatched:.0f}"
                                    
                                    if (2.0 <= odds <= 10.0 and 5 <= unmatched <= 100000 and 
                                        combo_key not in seen_combinations):
                                        
                                        seen_combinations.add(combo_key)
                                        draw_data.append((odds, unmatched, unmatched))
                                        logger.info(f"Smarkets Scraper: Found unique blue LAY - £{unmatched:.0f} at {odds:.2f} odds")
                                        
                                        # Only keep first few unique entries
                                        if len(draw_data) >= 3:
                                            break
                        
                        if len(draw_data) >= 3:
                            break
                    
                    if len(draw_data) >= 3:
                        break
                        
                except Exception as button_error:
                    logger.debug(f"Smarkets Scraper: Error processing draw element: {button_error}")
                    continue
            
            return draw_data if draw_data else None
            
        except Exception as e:
            logger.error(f"Smarkets Scraper: Error extracting blue LAY data: {e}")
            return None
    
    def find_odds_near_element(self, element):
        """Find odds value near a draw element."""
        try:
            # Look for decimal odds pattern (e.g., 3.45, 2.80)
            odds_pattern = r'\b([1-9]\.\d{1,2})\b'
            
            # Check element text and nearby elements
            search_elements = [element] + element.find_all_next(limit=5) + element.find_all_previous(limit=5)
            
            for elem in search_elements:
                text = elem.get_text(strip=True)
                match = re.search(odds_pattern, text)
                if match:
                    odds = float(match.group(1))
                    if 1.5 <= odds <= 10:  # Reasonable range for draw odds
                        return odds
            
            return None
            
        except Exception as e:
            logger.debug(f"Smarkets Scraper: Error finding odds: {e}")
            return None
    
    def find_unmatched_near_element(self, element):
        """Find unmatched amount near a draw element."""
        try:
            # Look for currency amounts (£100, £1,500.50)
            amount_pattern = r'£([\d,]+\.?\d*)'
            
            # Check element text and nearby elements
            search_elements = [element] + element.find_all_next(limit=10) + element.find_all_previous(limit=10)
            
            for elem in search_elements:
                text = elem.get_text(strip=True)
                match = re.search(amount_pattern, text)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    if 1 <= amount <= 1000000:  # Reasonable range
                        return amount
            
            return None
            
        except Exception as e:
            logger.debug(f"Smarkets Scraper: Error finding unmatched amount: {e}")
            return None
    
    async def navigate_to_match_betting_page(self, match_name):
        """Navigate to the betting page for a specific match."""
        try:
            # Clean match name for URL
            clean_name = match_name.replace(' vs ', '-').replace(' ', '-').lower()
            
            # Try multiple URL patterns for mobile Smarkets
            url_patterns = [
                f"https://m.smarkets.com/event/{clean_name}/winner",
                f"https://m.smarkets.com/event/{clean_name}", 
                f"https://m.smarkets.com/sport/football/{clean_name}",
                f"https://smarkets.com/event/{clean_name}/winner",
                f"https://smarkets.com/event/{clean_name}"
            ]
            
            for url in url_patterns:
                try:
                    logger.info(f"Smarkets Scraper: Trying URL: {url}")
                    self.driver.get(url)
                    await asyncio.sleep(3)
                    
                    # Check if we found a betting page with draw markets
                    page_source = self.driver.page_source
                    if ('draw' in page_source.lower() and 
                        any(pattern in page_source for pattern in ['lay', 'blue', 'betting-button', 'bet-button'])):
                        logger.info(f"Smarkets Scraper: Found betting page for {match_name}")
                        return True
                        
                except Exception as url_error:
                    logger.debug(f"Smarkets Scraper: URL {url} failed: {url_error}")
                    continue
            
            # Last resort: search for the match
            try:
                search_url = f"https://smarkets.com/search?q={match_name.replace(' ', '%20')}"
                self.driver.get(search_url)
                await asyncio.sleep(3)
                
                # Look for the first match result and click it
                search_results = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="search-result"], .search-result, a[href*="event"]')
                if search_results:
                    search_results[0].click()
                    await asyncio.sleep(3)
                    return True
                    
            except Exception as search_error:
                logger.debug(f"Smarkets Scraper: Search failed: {search_error}")
            
            return False
            
        except Exception as e:
            logger.debug(f"Smarkets Scraper: Navigation error for {match_name}: {e}")
            return False
    
    async def close(self):
        """Close the web driver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Smarkets Scraper: Driver closed successfully")
            except Exception as e:
                logger.error(f"Smarkets Scraper: Error closing driver: {e}")