# Draw Liability Bot

## Overview

This is a Telegram bot application designed to monitor draw liability on two betting exchanges: Smarkets and Matchbook. The bot continuously polls these exchanges for liability data and sends alerts to a Telegram chat when liability crosses configurable thresholds. The application is built with Python using asyncio for concurrent operations and provides real-time monitoring capabilities for betting exchange data.

## Current Status - READY TO USE

The bot is fully built and working correctly. All files are in place:
- `draw_liability_bot_api.py` - Main bot controller
- `exchanges/smarkets_api.py` - Smarkets API client  
- `exchanges/matchbook_api.py` - Matchbook API client

To activate: Add environment variables in Secrets tab, then Run.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Application Design
The system follows a modular architecture with clear separation of concerns:

- **Main Bot Controller**: The `DrawLiabilityBot` class serves as the central orchestrator, managing configuration, exchange APIs, and Telegram integration
- **Exchange API Abstraction**: Separate API client classes (`SmarketsAPI` and `MatchbookAPI`) handle communication with each betting exchange
- **Event-Driven Monitoring**: Uses asyncio for concurrent polling of multiple exchanges without blocking operations
- **Configuration Management**: Environment variable-based configuration for credentials, thresholds, and polling intervals

### Messaging Architecture
- **Telegram Bot Integration**: Uses python-telegram-bot library for sending alerts and handling commands
- **Asynchronous Communication**: All API calls and message sending operations are non-blocking
- **Threshold-Based Alerting**: Configurable liability thresholds trigger automatic notifications

### Data Flow Pattern
1. Bot polls both exchange APIs concurrently at regular intervals
2. Each exchange API authenticates and maintains session tokens
3. Liability data is fetched and compared against configured thresholds
4. Alerts are sent to designated Telegram chat when thresholds are exceeded

### Security Considerations
- Credentials stored as environment variables rather than hardcoded values
- Session-based authentication with automatic token management
- API rate limiting through configurable polling intervals

## External Dependencies

### Third-Party APIs
- **Smarkets API**: REST API at `https://api.smarkets.com` for fetching betting exchange data
- **Matchbook API**: REST API at `https://api.matchbook.com` for accessing alternative exchange data
- **Telegram Bot API**: For sending notifications and receiving commands

### Python Libraries
- **aiohttp**: Asynchronous HTTP client for API communications
- **python-telegram-bot**: Telegram bot framework for messaging integration
- **asyncio**: Built-in Python library for concurrent programming

### Infrastructure Requirements
- Environment variables for secure credential management
- Persistent runtime environment for continuous monitoring
- Network access to external APIs (Smarkets, Matchbook, Telegram)

### Configuration Dependencies
- `TELEGRAM_BOT_TOKEN`: Bot authentication token from Telegram
- `TELEGRAM_CHAT_ID`: Target chat for notifications
- `LIABILITY_THRESHOLD`: Configurable alert threshold (default: 6000)
- `POLLING_INTERVAL`: Monitoring frequency in seconds (default: 120)
- Exchange credentials for Smarkets and Matchbook APIs