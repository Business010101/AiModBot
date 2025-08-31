# Discord AI Admin Bot

## Overview

This is a Discord administration bot that leverages AI to parse natural language commands into server management actions. The bot allows server administrators to perform Discord server management tasks using conversational language instead of traditional slash commands. It integrates OpenAI's language models to understand user intent and translate it into actionable Discord API calls.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Discord.py Library**: Uses the discord.py library (version 2.3.2+) as the core framework for Discord bot functionality
- **Command Architecture**: Implements a hybrid approach with both traditional command prefix (`!`) and slash commands via `app_commands`
- **Intent Configuration**: Configured with minimal required intents (guilds, members) with optional message content access

### AI Integration
- **Hugging Face API**: Integrates with Hugging Face's language models for natural language processing (Updated August 27, 2025)
- **Model Selection**: Currently configured to use Mistral 7B Instruct as the primary language model
- **Free Inference**: Uses Hugging Face's free inference API for cost-effective AI processing
- **Asynchronous Processing**: Implements timeout-based AI calls (20-second default) to handle API latency

### 24/7 Uptime Support (Added August 27, 2025)
- **Flask Web Server**: Built-in web server running on port 5000 for UptimeRobot monitoring
- **Threaded Architecture**: Web server runs in separate daemon thread alongside Discord bot
- **Status Endpoint**: Provides real-time bot statistics (user info, guild count, latency)
- **UptimeRobot Integration**: Ready for external monitoring service to maintain 24/7 uptime

### Security & Permissions
- **Permission-Based Access Control**: Restricts admin commands to users with "Manage Guild" (Manage Server) permissions
- **Decorator-Based Security**: Uses `@app_commands.checks.has_permissions(manage_guild=True)` for command authorization

### Data Management
- **In-Memory Storage**: Uses a simple in-memory dictionary (`PENDING_ACTIONS`) to track pending administrative actions
- **Action Confirmation System**: Implements a pending actions system that maps message IDs to user actions for confirmation workflows
- **Stateless Design**: No persistent database storage, relying on Discord's state and temporary in-memory caching

### Command Processing Pipeline
- **Natural Language Input**: Accepts conversational commands from administrators
- **AI Parsing**: Translates natural language into structured JSON action arrays with expanded permission support
- **Action Confirmation**: Implements a confirmation step before executing administrative actions
- **Discord API Execution**: Executes parsed actions through Discord's REST API

### Enhanced Permission System (Added August 27, 2025)
- **Granular Channel Permissions**: New `/channel_permissions` command for detailed permission management
- **AI Permission Understanding**: Enhanced AI can parse channel permission requests in natural language
- **Multi-Permission Support**: Handles send_messages, view_channel, manage_messages, connect, speak permissions
- **Role and User Targeting**: Supports permission changes for both roles and individual users

## External Dependencies

### Required Services
- **Discord API**: Core platform integration for bot functionality and server management
- **Hugging Face API**: Language model service for natural language processing and command interpretation (Updated August 27, 2025)

### Environment Configuration
- **DISCORD_TOKEN**: Bot authentication token from Discord Developer Portal
- **HUGGINGFACE_TOKEN**: API token for Hugging Face service access

### Python Dependencies
- **discord.py** (>=2.3.2): Discord API wrapper and bot framework
- **requests**: HTTP library for Hugging Face API calls (Updated August 27, 2025)
- **flask**: Web server framework for 24/7 uptime monitoring
- **python-dotenv**: Environment variable management for secure configuration

### Discord Permissions Required
- **Bot Permissions**: Requires appropriate guild management permissions to perform administrative actions
- **User Permissions**: Validates user has "Manage Guild" permission before processing commands
- **Optional Intents**: Message content intent is optional but can be enabled for enhanced functionality