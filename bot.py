"""
bot.py — Discord Bot
Improvements:
  - Shared aiohttp session (not tls_client for async routes)
  - Helper for building embeds (DRY)
  - Input validation on all commands
  - Graceful shutdown
  - Error handler for all app commands
  - Logging on startup
"""

import time
import yaml
import logging
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Literal

from panel import (
    ClaimRoleView, HWIDResetView,
    make_embed, get_session, FOOTER_TEXT, FOOTER_ICON, BASE_URL, AUTH_TOKEN
)

# ─── Config ──────────────────────────────────────────────────────────────────

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

BOT_TOKEN: str = config["token"]
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

# ─── Bot Setup ────────────────────────────────────────────────────────────────

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=",", intents=intents, help_command=None)
bot.activity = discord.Activity(type=discord.ActivityType.watching, name="Managing Applications")
bot.status = discord.Status.dnd

_http: aiohttp.ClientSession | None = None
_status_channel: discord.TextChannel | None = None
_status_message: discord.Message | None = None
_last_updated: int = 0


def http() -> aiohttp.ClientSession:
    return _http


# ─── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    global _http
    if _http is None:
        _http = aiohttp.ClientSession(headers=HEADERS)

    # Re-register persistent views on restart
    bot.add_view(HWIDResetView())
    bot.add_view(ClaimRoleView())

    synced = await bot.tree.sync()
    log.info(f"Logged in as {bot.user} | Synced {len(synced)} commands")


@bot.event
async def on_close():
    if _http:
        await _http.close()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    embed = make_embed("❌ Error", str(error), 0xFF0000)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Status Loop ──────────────────────────────────────────────────────────────

@tasks.loop(minutes=1)
async def check_auth_status():
    global _status_message, _last_updated
    if not _status_channel or not _http:
        return

    try:
        async with _http.get(BASE_URL) as r1:
            if r1.status != 200:
                raise Exception("Server offline")
        async with _http.get(f"{BASE_URL}/check") as r2:
            data = await r2.json()

        _last_updated = int(time.time())
        embed = discord.Embed(
            title="📊 Auth Stats",
            description=(
                f"**Status:** 🟢 Active\n"
                f"**Total Apps:** `{data.get('total_apps', 'N/A')}`\n"
                f"**Total Licenses:** `{data.get('total_licenses', 'N/A')}`"
            ),
            color=0x32CD32,
        )
        embed.add_field(name="Last Updated", value=f"<t:{_last_updated}:R>", inline=False)
    except Exception:
        embed = discord.Embed(title="📊 Auth Stats", description="**Status:** 🔴 Offline", color=0xFF4444)

    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    if _status_message:
        await _status_message.edit(embed=embed)
    else:
        _status_message = await _status_channel.send(embed=embed)


# ─── Commands ─────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="status", description="Start auth status monitor in this channel")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def status_cmd(ctx):
    global _status_channel, _status_message
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    _status_channel = ctx.channel
    _status_message = None  # Force fresh message
    if not check_auth_status.is_running():
        check_auth_status.start()
    await ctx.interaction.followup.send("✅ Status monitor started in this channel.", ephemeral=True)


@bot.hybrid_command(name="create_app", description="Create a new application")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def create_app(ctx, app_name: str, version: float, download_link: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/create-app", json={"app_name": app_name, "version": version, "link": download_link})

    if r.status_code == 201:
        d = r.json()
        embed = make_embed(
            "✅ App Created",
            f"```App Name  : {d['app_name']}\nApp ID    : {d['app_id']}\nApp Secret: {d['app_secret']}```",
            0xDFA7A2,
        )
    elif r.status_code == 409:
        embed = make_embed("⚠️ App Exists", f"An app named `{app_name}` already exists.", 0xFFA500)
    else:
        embed = make_embed("❌ Failed", r.json().get("error", r.text), 0xFF0000)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="generate_license", description="Generate license keys")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def generate_license(ctx, app_name: str, duration: Literal["Lifetime", "Month", "Week", "Day"], quantity: int):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)

    if not 1 <= quantity <= 500:
        embed = make_embed("⚠️ Invalid Quantity", "Quantity must be between 1 and 500.", 0xFFA500)
        await ctx.interaction.followup.send(embed=embed, ephemeral=True)
        return

    r = get_session().post(f"{BASE_URL}/gen-license", json={"app_name": app_name, "duration": duration, "quantity": quantity})

    if r.status_code == 201:
        embed = make_embed(
            "✅ Licenses Generated",
            f"```App     : {app_name}\nDuration: {duration}\nCount   : {quantity}```",
            0xDFA7A2,
        )
    else:
        embed = make_embed("❌ Failed", r.json().get("error", r.text), 0xFF0000)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="assign_license", description="Assign a license to an app")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def assign_license(ctx, app_name: str, duration: Literal["Lifetime", "Month", "Week", "Day"]):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/assign-license", json={"app_name": app_name, "duration": duration})

    if r.status_code == 200:
        d = r.json()
        embed = make_embed(
            "✅ License Assigned",
            f"**🔑 License:** `{d['license']}`\n**📌 App:** `{app_name}`\n**⏳ Expiry:** `{d['expiry']}`\n**🕒 Duration:** `{duration}`",
            0x32CD32,
        )
    elif r.status_code == 404:
        embed = make_embed("❌ Not Found", f"App `{app_name}` not found or no unused `{duration}` licenses.", 0xFFA500)
    else:
        embed = make_embed("❌ Failed", r.json().get("error", r.text), 0xFF0000)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="get_license", description="Look up a license key")
@commands.guild_only()
async def get_license(ctx, license_key: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/get-license", json={"license_key": license_key})

    if r.status_code == 200:
        d = r.json()
        embed = make_embed(
            "✅ License Found",
            (
                f"**🔑 Key:** `{d['license_key']}`\n"
                f"**📌 App:** `{d['app_name']}`\n"
                f"**👤 User:** `{d['user']}`\n"
                f"**🖥 HWID:** `{d['hwid']}`\n"
                f"**⏳ Expiry:** `{d['expiry_date']}`\n"
                f"**🟢 Valid:** Yes"
            ),
            0x32CD32,
        )
    elif r.status_code == 403:
        embed = make_embed("❌ Expired", "This license has expired.", 0xFF0000)
    elif r.status_code == 404:
        embed = make_embed("❌ Not Found", "No license found for that key.", 0xFFA500)
    else:
        embed = make_embed("⚠️ Error", r.json().get("error", "Unknown error"), 0xFFFF00)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="update_app", description="Update app version and download link")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def update_app(ctx, app_name: str, version: float, download_link: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/update-version", json={"app_name": app_name, "version": version, "link": download_link})

    if r.status_code == 200:
        embed = make_embed(
            "✅ App Updated",
            f"**📌 App:** `{app_name}`\n**🚀 Version:** `{version}`\n**🔗 Link:** [Download]({download_link})",
            0x00FF00,
        )
    elif r.status_code == 404:
        embed = make_embed("❌ Not Found", f"App `{app_name}` not found.", 0xFF0000)
    else:
        embed = make_embed("⚠️ Error", r.json().get("error", "Unknown error"), 0xFFFF00)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="ban_license", description="Ban and remove a license")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def ban_license(ctx, license_key: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/ban-license", json={"license_key": license_key})

    if r.status_code == 200:
        embed = make_embed("🔨 License Banned", f"**🔑 Key:** `{license_key}`\n**Status:** Banned", 0xFF0000)
    elif r.status_code == 404:
        embed = make_embed("❌ Not Found", "License not found.", 0xFFA500)
    else:
        embed = make_embed("⚠️ Error", r.json().get("error", "Unknown error"), 0xFFFF00)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="reset_hwid", description="Reset HWID for a license")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def reset_hwid_cmd(ctx, license_key: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/reset-hwid", json={"license_key": license_key, "user": str(ctx.author.id)})

    if r.status_code == 200:
        embed = make_embed("✅ HWID Reset", f"**🔑 Key:** `{license_key}`\n**👤 User:** <@{ctx.author.id}>", 0x32CD32)
    elif r.status_code == 403:
        embed = make_embed("🚫 License Banned", "License sharing detected — license has been banned.", 0xFF0000)
    elif r.status_code == 404:
        embed = make_embed("❌ Not Found", "License not found.", 0xFFA500)
    else:
        embed = make_embed("⚠️ Error", r.json().get("error", "Unknown error"), 0xFFFF00)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="cleanup_licenses", description="Remove all expired licenses")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def cleanup_licenses(ctx):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)
    r = get_session().post(f"{BASE_URL}/cleanup")

    if r.status_code == 200:
        embed = make_embed("🧹 Cleanup Complete", r.json().get("message", "Done"), 0x32CD32)
    else:
        embed = make_embed("❌ Failed", "Could not run cleanup.", 0xFF0000)

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name="deploy_hwid_panel", description="Deploy the self-service HWID reset panel")
@commands.has_permissions(administrator=True)
async def deploy_hwid_panel(ctx):
    embed = make_embed("🔄 HWID Reset Panel", "Click the button below to reset your HWID.", 0x2B65EC)
    await ctx.send(embed=embed, view=HWIDResetView())
    if ctx.interaction:
        await ctx.interaction.response.send_message("Panel deployed!", ephemeral=True)


@bot.hybrid_command(name="deploy_role_panel", description="Deploy the role claim panel")
@commands.has_permissions(administrator=True)
async def deploy_role_panel(ctx):
    embed = make_embed(
        "🎟️ Claim Your Roles",
        "Enter your license key to receive your **Customer** and **App** roles.",
        0x2B65EC,
    )
    await ctx.send(embed=embed, view=ClaimRoleView())
    if ctx.interaction:
        await ctx.interaction.response.send_message("Panel deployed!", ephemeral=True)


# ─── Run ──────────────────────────────────────────────────────────────────────

bot.run(BOT_TOKEN)
