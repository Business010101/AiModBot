# Discord AI Admin Bot

A powerful Discord administration bot that uses AI to understand natural language commands and execute Discord server management actions. **Now includes 24/7 uptime support and advanced channel permissions management.**

## Features

### AI-Powered Natural Language Commands
- **`/server_ai`**: Give instructions in plain English like "create a role called Moderators with blue color" or "lock the general channel"
- Supports complex multi-action commands: "create a Gaming category, then create voice channels called Game Room 1 and Game Room 2 in that category"
- **NEW**: Channel permissions: "give the Moderators role permission to manage messages in general channel"
- Automatic confirmation system for destructive actions (deletes)

### Direct Slash Commands
- **`/create_role`**: Create roles with optional hex colors
- **`/create_channel`**: Create text or voice channels with optional categories  
- **`/create_category`**: Create channel categories
- **`/delete_channel`**: Delete channels by mention
- **`/assign_role`** / **`/remove_role`**: Manage user roles
- **`/lock_channel`** / **`/unlock_channel`**: Control channel permissions
- **🆕 `/channel_permissions`**: Set granular permissions for roles/users in specific channels

### 24/7 Uptime Support
- **Built-in web server** running on port 5000 for UptimeRobot monitoring
- **Automatic restart capabilities** with persistent connections
- **Status monitoring** with real-time bot statistics

## Setup Instructions

### 1. Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token
4. In the OAuth2 section, select bot permissions:
   - Manage Roles
   - Manage Channels  
   - Read Messages/View Channels
   - Send Messages
   - Use Slash Commands

### 2. Hugging Face API Setup
1. Go to [Hugging Face Settings](https://huggingface.co/settings/tokens)
2. Create a new access token with "Read" permissions
3. Copy the token

### 3. Environment Configuration
Set these environment variables in your Replit secrets:
- `DISCORD_TOKEN`: Your Discord bot token
- `HUGGINGFACE_TOKEN`: Your Hugging Face API token

### 4. Bot Permissions
The bot requires users to have "Manage Server" (Manage Guild) permission to use admin commands.

## Usage Examples

### Natural Language Commands with `/server_ai`

**Creating roles and channels:**
```
/server_ai instruction: Create a role called "VIP Members" with gold color, then create a text channel called "vip-lounge" that only VIP Members can access
```

**Server organization:**
```
/server_ai instruction: Create a category called "Gaming" and add voice channels "Lobby", "Team 1", and "Team 2" to it
```

**Moderation actions:**
```
/server_ai instruction: Lock the general channel and create a temporary announcement saying we're doing maintenance
```

### Direct Commands

**Create a moderator role:**
```
/create_role name: Moderator color: #0099ff
```

**Set up gaming channels:**
```
/create_category name: Gaming
/create_channel name: voice-chat channel_type: voice category: Gaming  
```

**Quick moderation:**
```
/lock_channel channel: #general
/assign_role user: @SomeUser role: @Moderator
```

**Channel permissions management:**
```
/channel_permissions channel: #staff-only role: @Member send_messages: False view_channel: False
/channel_permissions channel: #announcements role: @Everyone send_messages: False view_channel: True
```

## AI Understanding Capabilities

The bot can parse and execute these action types:
- **create_channel**: Create text/voice channels with categories and permissions
- **delete_channel**: Remove channels by name or ID
- **create_role**: Create roles with colors and permissions
- **delete_role**: Remove roles by name or ID  
- **assign_role** / **remove_role**: Manage user role assignments
- **lock_channel** / **unlock_channel**: Control channel messaging permissions
- **create_category**: Create channel categories
- **🆕 set_channel_permissions**: Set granular permissions for roles/users in channels

### Channel Permissions Options
The bot supports these permission types:
- **send_messages**: Allow/deny sending messages (text channels)
- **view_channel**: Allow/deny viewing the channel
- **manage_messages**: Allow/deny managing messages (delete, pin, etc.)
- **connect**: Allow/deny connecting to voice channels
- **speak**: Allow/deny speaking in voice channels

## Safety Features

- **Permission-based access**: Only users with "Manage Server" permission can use admin commands
- **Confirmation system**: Destructive actions (deletes) require confirmation unless auto-confirmed
- **Error handling**: Clear error messages for invalid inputs or missing permissions
- **Audit trail**: All actions are logged with success/failure status

## Technical Details

- Built with discord.py 2.3.2+
- Uses Hugging Face Mistral 7B Instruct for natural language processing  
- Implements Discord slash commands and button interactions
- Supports both individual and batch command execution
- Includes comprehensive error handling and type safety
- Free AI inference through Hugging Face API

## 24/7 Uptime Setup with UptimeRobot

Your bot includes a built-in web server for 24/7 monitoring:

### 1. Get Your Bot's URL
- The web server runs on port 5000
- Your bot's monitoring URL: `https://[your-replit-url]/` 
- The status page shows: bot info, connected guilds, and latency

### 2. Set Up UptimeRobot (Free)
1. Go to [UptimeRobot.com](https://uptimerobot.com) and create a free account
2. Click "Add New Monitor"
3. Choose "HTTP(s)" monitor type
4. Enter your bot's URL from step 1
5. Set monitoring interval (5 minutes recommended for free tier)
6. Save the monitor

### 3. Benefits of UptimeRobot
- **Automatic restarts**: Pings keep your bot alive on Replit
- **Uptime tracking**: Monitor your bot's availability
- **Notifications**: Get alerts if your bot goes down
- **Free tier**: Up to 50 monitors with 5-minute intervals

### Manual Keep-Alive Alternative
If you prefer not to use UptimeRobot, you can manually visit your bot's URL periodically to keep it alive.

## Bot Status

✅ **Running**: The bot is currently online with 24/7 uptime support
🌍 **Web Server**: Active on port 5000 for monitoring
🔄 **Auto-Restart**: Ready for UptimeRobot integration

Use `/server_ai` with natural language, `/channel_permissions` for detailed control, or any direct slash commands to manage your Discord server efficiently!