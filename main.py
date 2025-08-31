"""
Discord AI Admin Bot
A Discord administration bot that uses AI to parse natural language commands into server management actions.

Requirements: discord.py>=2.3.2, requests, python-dotenv
Set environment variables: DISCORD_TOKEN, HUGGINGFACE_TOKEN
Enable intents: guilds, members, message_content (message_content optional here)
Note: Only users with Manage Guild (Manage Server) permission may use admin/AI commands.
"""

import os
import asyncio
import json
import uuid
from typing import List, Dict, Any, Optional
from threading import Thread
import time

import discord
from discord import app_commands
from discord.ext import commands

import requests
from dotenv import load_dotenv
from flask import Flask

load_dotenv()
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
HUGGINGFACE_TOKEN = os.environ.get("HUGGINGFACE_TOKEN")
if not DISCORD_TOKEN or not HUGGINGFACE_TOKEN:
    raise RuntimeError("Set DISCORD_TOKEN and HUGGINGFACE_TOKEN environment variables.")

# Hugging Face API configuration
HF_API_URL = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
HF_HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_TOKEN}"}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = False  # not required for admin actions but optional
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Helpers & Config ----------
ADMIN_CHECK = app_commands.checks.has_permissions(manage_guild=True)

# In-memory pending actions store: message_id -> {user_id, guild_id, actions}
PENDING_ACTIONS: Dict[int, Dict[str, Any]] = {}

# ---------- UptimeRobot Web Server (for 24/7 uptime) ----------
app = Flask(__name__)

@app.route('/')
def home():
    return f'''
    <h1>Discord AI Admin Bot - Status: Online</h1>
    <p>Bot User: {bot.user}</p>
    <p>Connected Guilds: {len(bot.guilds) if bot.guilds else 0}</p>
    <p>Latency: {round(bot.latency * 1000, 2)}ms</p>
    <p>This endpoint keeps the bot alive for UptimeRobot monitoring.</p>
    '''

def run_flask():
    """Run Flask server in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def keep_alive():
    """Start the web server to keep the bot alive"""
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    print("🌐 UptimeRobot web server started on port 5000")

async def call_huggingface_parse(prompt: str, timeout: int = 20) -> str:
    """
    Calls Hugging Face Inference API synchronously inside thread pool and returns model text.
    Uses a more specific model that can handle structured JSON responses.
    """
    loop = asyncio.get_running_loop()
    
    # Use a better model for JSON parsing - Mistral 7B Instruct
    hf_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
    
    def _call():
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 800,
                "temperature": 0.1,
                "do_sample": True,
                "return_full_text": False
            }
        }
        
        response = requests.post(hf_url, headers=HF_HEADERS, json=payload, timeout=timeout)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "")
            return str(result)
        else:
            return f"(HF API error {response.status_code}) {response.text}"
    
    try:
        resp = await asyncio.wait_for(loop.run_in_executor(None, _call), timeout=timeout)
        return resp.strip() if resp else ""
    except Exception as e:
        return f"(Hugging Face error) {e}"

def build_parse_prompt(user_instruction: str) -> str:
    """
    Prompt for Hugging Face model to parse instructions into Discord actions.
    Optimized for Mistral/Llama-style models that work better with more structured prompts.
    """
    return f"""<s>[INST] You are a Discord bot command parser. Convert natural language into JSON actions.

ALLOWED ACTIONS:
- create_channel: {{"type":"create_channel", "channel_type":"text"|"voice", "name":"string", "category":"string"}}
- delete_channel: {{"type":"delete_channel", "name_or_id":"string"}}
- create_role: {{"type":"create_role", "name":"string", "color":"#hexcolor"}}
- delete_role: {{"type":"delete_role", "name_or_id":"string"}}
- assign_role: {{"type":"assign_role", "user":"string", "role":"string"}}
- remove_role: {{"type":"remove_role", "user":"string", "role":"string"}}
- lock_channel: {{"type":"lock_channel", "name_or_id":"string"}}
- unlock_channel: {{"type":"unlock_channel", "name_or_id":"string"}}
- create_category: {{"type":"create_category", "name":"string"}}
- set_channel_permissions: {{"type":"set_channel_permissions", "channel":"string", "role_or_user":"string", "permissions":{{"send_messages":boolean}}}}

INSTRUCTION: {user_instruction}

Response format: {{"actions": [action1, action2, ...]}}
Only respond with valid JSON. No explanations. [/INST]</s>"""

# ---------- Execution helpers ----------
async def find_channel_by_name_or_id(guild: discord.Guild, name_or_id: str) -> Optional[discord.abc.GuildChannel]:
    # try by ID
    try:
        cid = int(name_or_id)
        ch = guild.get_channel(cid)
        if ch:
            return ch
    except:
        pass
    # try by name
    ch = discord.utils.get(guild.channels, name=name_or_id)
    return ch

async def find_role_by_name_or_id(guild: discord.Guild, name_or_id: str) -> Optional[discord.Role]:
    try:
        rid = int(name_or_id)
        role = guild.get_role(rid)
        if role:
            return role
    except:
        pass
    role = discord.utils.get(guild.roles, name=name_or_id)
    return role

async def find_member_by_mention_or_id(guild: discord.Guild, value: str) -> Optional[discord.Member]:
    # try id
    try:
        mid = int(value)
        mem = guild.get_member(mid)
        if mem:
            return mem
    except:
        pass
    # try mention format
    if value.startswith("<@") and value.endswith(">"):
        vid = ''.join(ch for ch in value if ch.isdigit())
        try:
            mem = guild.get_member(int(vid))
            if mem:
                return mem
        except:
            pass
    # try by name (first match)
    for m in guild.members:
        if m.name == value or f"{m.name}#{m.discriminator}" == value:
            return m
    return None

async def execute_action(guild: discord.Guild, action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a single action. Returns result dict {ok:bool, message:str}
    """
    typ = action.get("type")
    try:
        if typ == "create_channel":
            ch_type = action.get("channel_type","text")
            name = action.get("name") or "new-channel"
            category_name = action.get("category")
            category_obj = None
            if category_name:
                category_obj = discord.utils.get(guild.categories, name=category_name)
                if not category_obj:
                    category_obj = await guild.create_category(category_name)
            if ch_type == "voice":
                ch = await guild.create_voice_channel(name, category=category_obj)
            else:
                overwrites = None
                # optional overwrites: {"role_name": {"send_messages": False}}
                if action.get("overwrites"):
                    overwrites = {}
                    for role_name, perms in action["overwrites"].items():
                        r = await find_role_by_name_or_id(guild, role_name)
                        if r:
                            overwrite = discord.PermissionOverwrite()
                            for k,v in perms.items():
                                if hasattr(overwrite, k):
                                    setattr(overwrite, k, v)
                            overwrites[r] = overwrite
                ch = await guild.create_text_channel(name, category=category_obj, overwrites=overwrites or {})
            return {"ok":True, "message": f"Created channel {ch.name} ({ch.id})"}
        elif typ == "delete_channel":
            target = action.get("name_or_id")
            ch = await find_channel_by_name_or_id(guild, str(target))
            if not ch:
                return {"ok":False, "message": f"Channel not found: {target}"}
            await ch.delete()
            return {"ok":True, "message": f"Deleted channel {target}"}
        elif typ == "create_role":
            name = action.get("name","NewRole")
            color = action.get("color")
            perms = action.get("permissions", [])
            discord_color = discord.Color.default()
            if color:
                try:
                    discord_color = discord.Color(int(color.strip("#"),16))
                except:
                    pass
            permissions = discord.Permissions.none()
            # Basic perm mapping: allow only common ones if provided
            perm_map = {
                "manage_messages":"manage_messages",
                "kick_members":"kick_members",
                "ban_members":"ban_members",
                "administrator":"administrator",
                "manage_channels":"manage_channels",
                "manage_guild":"manage_guild"
            }
            for p in perms:
                key = perm_map.get(p)
                if key and hasattr(permissions, key):
                    setattr(permissions, key, True)
            role = await guild.create_role(name=name, color=discord_color, permissions=permissions)
            return {"ok":True, "message": f"Created role {role.name} ({role.id})"}
        elif typ == "delete_role":
            target = action.get("name_or_id")
            role = await find_role_by_name_or_id(guild, str(target))
            if not role:
                return {"ok":False, "message": f"Role not found: {target}"}
            await role.delete()
            return {"ok":True, "message": f"Deleted role {target}"}
        elif typ == "assign_role":
            user_ref = action.get("user")
            role_ref = action.get("role")
            member = await find_member_by_mention_or_id(guild, str(user_ref))
            role = await find_role_by_name_or_id(guild, str(role_ref))
            if not member:
                return {"ok":False, "message": f"Member not found: {user_ref}"}
            if not role:
                return {"ok":False, "message": f"Role not found: {role_ref}"}
            await member.add_roles(role)
            return {"ok":True, "message": f"Assigned role {role.name} to {member.display_name}"}
        elif typ == "remove_role":
            user_ref = action.get("user")
            role_ref = action.get("role")
            member = await find_member_by_mention_or_id(guild, str(user_ref))
            role = await find_role_by_name_or_id(guild, str(role_ref))
            if not member:
                return {"ok":False, "message": f"Member not found: {user_ref}"}
            if not role:
                return {"ok":False, "message": f"Role not found: {role_ref}"}
            await member.remove_roles(role)
            return {"ok":True, "message": f"Removed role {role.name} from {member.display_name}"}
        elif typ == "lock_channel":
            target = action.get("name_or_id")
            ch = await find_channel_by_name_or_id(guild, str(target))
            if not ch:
                return {"ok":False, "message": f"Channel not found: {target}"}
            if not isinstance(ch, discord.TextChannel):
                return {"ok":False, "message": f"Cannot lock non-text channel: {target}"}
            overwrite = ch.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            await ch.set_permissions(guild.default_role, overwrite=overwrite)
            return {"ok":True, "message": f"Locked channel {ch.name}"}
        elif typ == "unlock_channel":
            target = action.get("name_or_id")
            ch = await find_channel_by_name_or_id(guild, str(target))
            if not ch:
                return {"ok":False, "message": f"Channel not found: {target}"}
            if not isinstance(ch, discord.TextChannel):
                return {"ok":False, "message": f"Cannot unlock non-text channel: {target}"}
            overwrite = ch.overwrites_for(guild.default_role)
            overwrite.send_messages = True
            await ch.set_permissions(guild.default_role, overwrite=overwrite)
            return {"ok":True, "message": f"Unlocked channel {ch.name}"}
        elif typ == "create_category":
            name = action.get("name","Category")
            cat = await guild.create_category(name)
            return {"ok":True, "message": f"Created category {cat.name}"}
        elif typ == "set_channel_permissions":
            target = action.get("channel")
            ch = await find_channel_by_name_or_id(guild, str(target))
            if not ch:
                return {"ok":False, "message": f"Channel not found: {target}"}
            if not isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                return {"ok":False, "message": f"Cannot set permissions on this channel type: {target}"}
            
            role_or_user = action.get("role_or_user")
            permissions = action.get("permissions", {})
            
            # Find role or user
            role = await find_role_by_name_or_id(guild, str(role_or_user))
            member = None if role else await find_member_by_mention_or_id(guild, str(role_or_user))
            
            if not role and not member:
                return {"ok":False, "message": f"Role or user not found: {role_or_user}"}
            
            target_obj = role or member
            if target_obj:
                overwrite = ch.overwrites_for(target_obj)
                
                # Set permissions based on provided dict
                for perm_name, value in permissions.items():
                    if hasattr(overwrite, perm_name):
                        setattr(overwrite, perm_name, value)
                
                await ch.set_permissions(target_obj, overwrite=overwrite)
                target_type = "role" if role else "user"
                return {"ok":True, "message": f"Set permissions for {target_type} {target_obj.name} in channel {ch.name}"}
            else:
                return {"ok":False, "message": "Target role or user not found"}
        else:
            return {"ok":False, "message": f"Unknown action type: {typ}"}
    except Exception as e:
        return {"ok":False, "message": f"Exception: {e}"}

# ---------- Interactive confirmation view ----------
class ConfirmView(discord.ui.View):
    def __init__(self, actions: List[Dict[str,Any]], author_id: int, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.actions = actions
        self.author_id = author_id
        self.result: Optional[List[Dict[str,Any]]] = None  # will hold results after execution

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if user is the original author or has administrator permissions
        if interaction.user.id != self.author_id:
            if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
                return True
            await interaction.response.send_message("You are not allowed to confirm this action.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=False)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Guild not found")
            return
        results = []
        for act in self.actions:
            res = await execute_action(guild, act)
            results.append(res)
        self.result = results
        # send results summary and disable buttons
        summary = "\n".join([f"- {r.get('message')}" for r in results])
        await interaction.followup.send(f"✅ Actions executed:\n{summary}")
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = True
        await interaction.edit_original_response(content="Confirmed — actions executed.", view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            if hasattr(child, 'disabled'):
                child.disabled = True
        await interaction.response.edit_message(content="Cancelled — no actions were taken.", view=self)

# ---------- Bot events ----------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    if bot.user:
        print(f"✅ Logged in as {bot.user} (id: {bot.user.id})")
    else:
        print("✅ Bot logged in (user info not available)")
    print(f"🌍 Connected to {len(bot.guilds)} guild(s)")
    print(f"🔄 Bot is ready and operational")

# ---------- Slash commands (direct safe commands) ----------

@bot.tree.command(name="create_role", description="Create a role with optional hex color")
@ADMIN_CHECK
async def slash_create_role(interaction: discord.Interaction, name: str, color: Optional[str] = None):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    discord_color = discord.Color.default()
    if color:
        try:
            discord_color = discord.Color(int(color.strip("#"),16))
        except:
            await interaction.response.send_message("Invalid color hex. Example: #ff0000", ephemeral=True)
            return
    role = await guild.create_role(name=name, color=discord_color)
    await interaction.response.send_message(f"✅ Created role {role.mention}")

@bot.tree.command(name="create_channel", description="Create a text or voice channel (optional category)")
@ADMIN_CHECK
async def slash_create_channel(interaction: discord.Interaction, name: str, channel_type: str = "text", category: Optional[str] = None):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    category_obj = None
    if category:
        category_obj = discord.utils.get(guild.categories, name=category)
        if not category_obj:
            category_obj = await guild.create_category(category)
    if channel_type.lower() == "voice":
        ch = await guild.create_voice_channel(name, category=category_obj)
    else:
        ch = await guild.create_text_channel(name, category=category_obj)
    await interaction.response.send_message(f"✅ Created {channel_type} channel: {ch.mention}")

@bot.tree.command(name="delete_channel", description="Delete a channel by mention or ID")
@ADMIN_CHECK
async def slash_delete_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    channel_name = channel.name
    await channel.delete()
    await interaction.response.send_message(f"🗑️ Deleted channel `{channel_name}`")

@bot.tree.command(name="assign_role", description="Assign a role to a member")
@ADMIN_CHECK
async def slash_assign_role(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    await user.add_roles(role)
    await interaction.response.send_message(f"✅ Assigned {role.mention} to {user.mention}")

@bot.tree.command(name="remove_role", description="Remove a role from a member")
@ADMIN_CHECK
async def slash_remove_role(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    await user.remove_roles(role)
    await interaction.response.send_message(f"✅ Removed {role.mention} from {user.mention}")

@bot.tree.command(name="lock_channel", description="Lock a text channel for @everyone")
@ADMIN_CHECK
async def slash_lock_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    overwrite = channel.overwrites_for(guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(f"🔒 Locked {channel.mention}")

@bot.tree.command(name="unlock_channel", description="Unlock a text channel for @everyone")
@ADMIN_CHECK
async def slash_unlock_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    overwrite = channel.overwrites_for(guild.default_role)
    overwrite.send_messages = True
    await channel.set_permissions(guild.default_role, overwrite=overwrite)
    await interaction.response.send_message(f"🔓 Unlocked {channel.mention}")

@bot.tree.command(name="create_category", description="Create a new category")
@ADMIN_CHECK
async def slash_create_category(interaction: discord.Interaction, name: str):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    category = await guild.create_category(name)
    await interaction.response.send_message(f"✅ Created category: {category.name}")

@bot.tree.command(name="channel_permissions", description="Set specific permissions for a role or user in a channel")
@ADMIN_CHECK
@app_commands.describe(
    channel="The channel to modify permissions for",
    role="The role to set permissions for (use either role OR user, not both)",
    user="The user to set permissions for (use either role OR user, not both)",
    send_messages="Allow/deny sending messages (text channels)",
    view_channel="Allow/deny viewing the channel",
    manage_messages="Allow/deny managing messages (delete, pin, etc.)",
    connect="Allow/deny connecting to voice channel",
    speak="Allow/deny speaking in voice channel"
)
async def slash_channel_permissions(
    interaction: discord.Interaction,
    channel: discord.abc.GuildChannel,
    role: Optional[discord.Role] = None,
    user: Optional[discord.Member] = None,
    send_messages: Optional[bool] = None,
    view_channel: Optional[bool] = None,
    manage_messages: Optional[bool] = None,
    connect: Optional[bool] = None,
    speak: Optional[bool] = None
):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    
    if not role and not user:
        await interaction.response.send_message("❌ You must specify either a role or a user.", ephemeral=True)
        return
    
    if role and user:
        await interaction.response.send_message("❌ Please specify either a role OR a user, not both.", ephemeral=True)
        return
    
    target = role or user
    target_type = "role" if role else "user"
    
    if not target:
        await interaction.response.send_message("❌ Target not found.", ephemeral=True)
        return
    
    # Get current permissions
    overwrite = channel.overwrites_for(target)
    
    # Update permissions based on provided values
    changes = []
    if send_messages is not None:
        overwrite.send_messages = send_messages
        changes.append(f"send_messages: {send_messages}")
    if view_channel is not None:
        overwrite.view_channel = view_channel
        changes.append(f"view_channel: {view_channel}")
    if manage_messages is not None:
        overwrite.manage_messages = manage_messages
        changes.append(f"manage_messages: {manage_messages}")
    if connect is not None:
        overwrite.connect = connect
        changes.append(f"connect: {connect}")
    if speak is not None:
        overwrite.speak = speak
        changes.append(f"speak: {speak}")
    
    if not changes:
        await interaction.response.send_message("❌ No permission changes specified.", ephemeral=True)
        return
    
    # Apply the permissions
    if target:
        await channel.set_permissions(target, overwrite=overwrite)
        
        changes_text = "\n".join([f"• {change}" for change in changes])
        await interaction.response.send_message(
            f"✅ Updated permissions for {target_type} **{target.name}** in {channel.mention}:\n{changes_text}"
        )
    else:
        await interaction.response.send_message("❌ Target not found.", ephemeral=True)

# ---------- AI natural language admin ----------

@bot.tree.command(name="server_ai", description="Give the bot a natural-language server instruction (Admins only).")
@ADMIN_CHECK
@app_commands.describe(instruction="What you want the bot to do, in plain language",
                       auto_confirm="If true, skip confirmation for safe actions (not recommended for deletes)")
async def server_ai(interaction: discord.Interaction, instruction: str, auto_confirm: bool = False):
    await interaction.response.defer(thinking=True)
    guild = interaction.guild
    if not guild:
        await interaction.followup.send("❌ This command can only be used in a server.")
        return

    # Build prompt & call Hugging Face to parse into JSON actions
    prompt = build_parse_prompt(instruction)
    model_text = await call_huggingface_parse(prompt)
    
    # Try to parse JSON from model_text
    try:
        parsed = json.loads(model_text)
    except Exception:
        # sometimes model adds backticks or other noise; try to extract first JSON object
        import re
        m = re.search(r'(\{.*\})', model_text, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except Exception as e:
                await interaction.followup.send(f"Failed to parse Hugging Face response as JSON: {e}\n\nRaw response:\n```\n{model_text}\n```")
                return
        else:
            await interaction.followup.send(f"Failed to parse Hugging Face response as JSON.\n\nRaw response:\n```\n{model_text}\n```")
            return

    actions = parsed.get("actions", [])
    if not isinstance(actions, list) or len(actions) == 0:
        await interaction.followup.send("AI returned no actions to perform.")
        return

    # Determine if any action is destructive (delete_*)
    destructive = any(a.get("type","").startswith("delete_") for a in actions)
    
    if destructive and not auto_confirm:
        # ask for confirmation with a view
        readable = json.dumps(actions, indent=2)
        embed = discord.Embed(title="Confirm AI Actions",
                              description=f"The AI parsed the following actions from your instruction. Confirm to execute.\n\n```json\n{readable}\n```",
                              color=discord.Color.orange())
        view = ConfirmView(actions=actions, author_id=interaction.user.id)
        msg = await interaction.followup.send(embed=embed, view=view)
        # store pending (optional)
        if guild:
            PENDING_ACTIONS[msg.id] = {"user_id": interaction.user.id, "guild_id": guild.id, "actions": actions}
        return
    else:
        # Directly execute (auto_confirm True or non-destructive)
        results = []
        for act in actions:
            res = await execute_action(guild, act)
            results.append(res)
        
        # Format results nicely
        success_count = sum(1 for r in results if r.get("ok"))
        failure_count = len(results) - success_count
        
        summary_lines = []
        for i, result in enumerate(results):
            status_emoji = "✅" if result.get("ok") else "❌"
            summary_lines.append(f"{status_emoji} {result.get('message', 'Unknown result')}")
        
        summary = "\n".join(summary_lines)
        header = f"Executed {len(actions)} action(s): {success_count} succeeded, {failure_count} failed"
        
        await interaction.followup.send(f"**{header}**\n{summary}")

# ---------- Run ----------
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        exit(1)
    if not HUGGINGFACE_TOKEN:
        print("Error: HUGGINGFACE_TOKEN environment variable not set")
        exit(1)
    
    print("Starting Discord AI Admin Bot with Hugging Face...")
    
    # Start the web server for UptimeRobot monitoring
    keep_alive()
    
    # Start the Discord bot
    bot.run(DISCORD_TOKEN)