import discord ,yaml
import aiohttp ,tls_client ,datetime
import time,requests
from discord.ext import commands, tasks
from typing import Literal , Optional
from datetime import datetime,timedelta,timezone
from panel import *

bot = commands.Bot(command_prefix=',', intents=discord.Intents.all(), help_command=None)
bot.activity = discord.Activity(type=discord.ActivityType.watching, name='Managing Applications')
bot.status = discord.Status.dnd
config = open('config.yaml') 
config = yaml.safe_load(config)
base_url = config['base_url']
authtoken = config['authtoken']
base = base_url
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {authtoken}'}

session = None  
embed_messages = {}
status_channel = None
last_updated = int(time.time())  # Store the last update timestamp
ses = tls_client.Session()
ses.headers.update(headers)


@bot.event
async def on_ready():
    global session
    if session is None:
        session = aiohttp.ClientSession(headers=headers)  # Initialize session inside an async function
    print(f'{bot.user} Bot Online')
    synced = await bot.tree.sync()
    print(f'Synced {len(synced)} Commands.')


@tasks.loop(minutes=1)
async def check_auth_status():

    global status_channel, session, last_updated

    if status_channel is None or session is None:
        return  # No channel or session, so don't proceed

    try:
        async with session.get(base) as response:
            if response.status != 200:
                raise Exception("Server Error")  # If response is not 200, treat it as a failure

            status = await response.text()

        async with session.get(base + '/check') as response2:
            if response2.status != 200:
                raise Exception("Server Error")  # Ensure check API responds correctly

            data = await response2.json()
            total_licenses = data.get('total_licenses', 'N/A')
            total_apps = data.get('total_apps', 'N/A')

            # Update last_updated time with current UNIX timestamp
            last_updated = int(time.time())

            embed = discord.Embed(
                title="Auth Stats",
                description=f"**Status: Active\nTotal Licenses: {total_licenses}\nTotal Apps: {total_apps}**",
                color=0xDFA7A2
            )
            embed.add_field(name="Last Updated", value=f"<t:{last_updated}:R>", inline=False)

    except Exception as e:
        # If server doesn't respond, create an Inactive embed
        embed = discord.Embed(title="Auth Stats", description="**Inactive, 500**", color=0xDFA7A2)

    # Set default footer for all embeds
    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    # Update the existing embed if it exists, otherwise send a new one
    if status_channel.id in embed_messages:
        await embed_messages[status_channel.id].edit(embed=embed)
    else:
        embed_messages[status_channel.id] = await status_channel.send(embed=embed)


@bot.hybrid_command(name='status', description='Check Auth Stats')
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def status(ctx: discord.AppCommandContext):
    global status_channel
    await ctx.interaction.response.defer(thinking=True, ephemeral=True) 

    status_channel = ctx.channel  # Store the last used channel

    if not check_auth_status.is_running():
        check_auth_status.start()

    await ctx.interaction.followup.send("Started Monitoring", ephemeral=True)


@bot.hybrid_command(name='create_app', description='Create New App', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()

async def create_app(ctx: discord.AppCommandContext, app_name: str, version: float, download_link: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True) 

    data = {
        "app_name": app_name,
        "version": version,
        "link": download_link
    }

    try:
        r = ses.post(f'{base}/create-app', json=data)  # ✅ Use json=data

        if r.status_code == 201:
            response_data = r.json()  # Get response JSON
            app_id = response_data.get("app_id", "Unknown")
            app_secret = response_data.get("app_secret", "Unknown")

            embed = discord.Embed(
                title="✅ App Created Successfully",
                description=f"```App Name: {app_name}\nApp ID: {app_id}\nApp Secret: {app_secret}```",
                color=0xDFA7A2
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Create App",
                description=f"Error: {r.text}",
                color=0xFF0000
            )

    except Exception as e:
        embed = discord.Embed(title="❌ Request Failed", description=str(e), color=0xFF0000)

    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)

@bot.hybrid_command(name='generate_license', description='Generate License', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()

async def generate_license(ctx: discord.AppCommandContext, app_name: str, duration: Literal['Lifetime', 'Month', 'Week'], quantity: int):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True) 

    data = {
        "app_name": app_name,
        "duration": duration,
        "quantity": quantity
    }

    r = ses.post(f'{base}/gen-license', json=data)

    if r.status_code == 201:
        embed = discord.Embed(
            title="✅ License Generated Successfully",
            description=f"```App Name: {app_name}\nDuration: {duration}\nQuantity: {quantity}```",
            color=0xDFA7A2
        )
    else:
        embed = discord.Embed(
            title="❌ Failed to Generate License",
            description=f"Error: {r.text}",
            color=0xFF0000
        )

    # Footer (applies to both success and failure)
    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    # Send only ONE message
    await ctx.interaction.followup.send(embed=embed, ephemeral=True)

import asyncio  # Required for async sleep

@bot.hybrid_command(name='get_license', description='Get License Details', with_app_command=True)
@commands.guild_only()

async def get_license(ctx: discord.AppCommandContext, license_key: str):

    try:
        # Check if response is already done before deferring
        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer(thinking=True, ephemeral=True)

        data = {"license_key": license_key}

        
        r = ses.post(f'{base}/get-license', json=data) 
        status = r.status_code
        response =  r.json()

        # Handling responses based on status codes
        if status == 200:
            expiry_str = response.get('expiry_date', '')
            try:
                expiry_unix = int(expiry_str)
            except ValueError:
                expiry_unix = None

            embed = discord.Embed(
                title="✅ License Found",
                description=(
                    f"**🔑 License Key:** `{response.get('license_key', 'N/A')}`\n"
                    f"**📌 App Name:** `{response.get('app_name', 'N/A')}`\n"
                    f"**👤 User:** `{response.get('user', 'Unknown')}`\n"
                    f"**⏳ Expiry:** {f'<t:{expiry_unix}:R>' if expiry_unix else 'Never'}\n"
                    f"**🟢 Status:** `Valid`"
                ),
                color=0x32CD32  # Green color
            )

        elif status == 403:
            embed = discord.Embed(
                title="❌ License Expired",
                description="The provided license key has expired.",
                color=0xFF0000
            )

        elif status == 404:
            embed = discord.Embed(
                title="❌ License Not Found",
                description="No license found with the given key.",
                color=0xFFA500
            )

        elif status == 401:
            embed = discord.Embed(
                title="❌ Unauthorized",
                description="Invalid API authentication. Please check your API token.",
                color=0xFF0000
            )

        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description=f"An unexpected error occurred (Status Code: {status}).",
                color=0xFFFF00
            )

        # Add footer to embed
        embed.set_footer(
            text="Asta Authentication",
            icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
        )

        # Send embed using followup
        await ctx.interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        await ctx.interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.hybrid_command(name='updateapp', description='Update the app', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def updateapp(ctx, app_name: str, version: float, download_link: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)   # Defer response for smoother interaction

    data = {
        "app_name": app_name,
        "version": version,
        "link": download_link
    }

    r = ses.post(f'{base}/update-version', json=data)

    # If the update was successful
    if r.status_code == 200:
        embed = discord.Embed(
            title="✅ Update Successful",
            description=(
                f"**📌 App Name:** `{app_name}`\n"
                f"**🚀 New Version:** `{version}`\n"
                f"**🔗 Download Link:** [Click Here]({download_link})"
            ),
            color=0x00FF00  # Green
        )

    # If the app was not found
    elif r.status_code == 404:
        embed = discord.Embed(
            title="❌ Update Failed",
            description=f"App `{app_name}` not found.",
            color=0xFF0000  # Red
        )

    # Unauthorized access
    elif r.status_code == 401:
        embed = discord.Embed(
            title="❌ Unauthorized",
            description="Invalid API authentication. Please check your API token.",
            color=0xFF0000
        )

    # Any other server error
    else:
        embed = discord.Embed(
            title="⚠️ Error",
            description="An unexpected error occurred while updating the app.",
            color=0xFFFF00  # Yellow
        )

    # Add footer to embed
    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    # Send embed
    await ctx.interaction.followup.send(embed=embed, ephemeral=True)  # Ephemeral makes it visible only to the user

from datetime import datetime, timedelta

@bot.hybrid_command(name='assign_license', description='Assign License For App')
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def assign_license(ctx, app_name: str, duration: Literal['Lifetime', 'Month', 'Week']):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)   # Defer response for smoother interaction

    data = {
        "app_name": app_name,
        "duration": duration
    }

    r = ses.post(f'{base}/assign-license', json=data)  # Send JSON request

    if r.status_code == 200:
        response = r.json()
        licensek = response.get('license')
        expiry = response.get('expiry')

        # Convert expiry duration to a timestamp
        

        embed = discord.Embed(
            title="✅ License Assigned",
            description=(
                f"**🔑 License Key:** `{licensek}`\n"
                f"**📌 App Name:** `{app_name}`\n"
                f"**⏳ Expiry:** {expiry}\n"
                f"**🕒 Duration:** `{duration}`"
            ),
            color=0x32CD32  # Green color
        )

    elif r.status_code == 400:
        embed = discord.Embed(
            title="❌ Error",
            description="Missing required parameters (app_name or duration).",
            color=0xFFA500  # Orange color
        )

    elif r.status_code == 401:
        embed = discord.Embed(
            title="❌ Unauthorized",
            description="Invalid API authentication. Please check your API token.",
            color=0xFF0000  # Red color
        )

    elif r.status_code == 404:
        embed = discord.Embed(
            title="❌ Not Found",
            description="App does not exist or no unused licenses available.",
            color=0xFFA500
        )

    elif r.status_code == 426:
        embed = discord.Embed(
            title="❌ No Licenses Available",
            description="No licenses available for the specified duration.",
            color=0xFFFF00  # Yellow color
        )

    else:
        embed = discord.Embed(
            title="⚠️ Unexpected Error",
            description="An error occurred while assigning the license.",
            color=0xFFFF00
        )

    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)  # Send embed privately


@bot.hybrid_command(name='reset_hwid', description='Reset HWID', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def reset_hwid(ctx, license: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)   # Defer response for a smooth experience
    
    data = {
        "license_key": license,
        "user": str(ctx.author.id)  # Automatically assign user as the command executor
    }
    
    r = ses.post(f"{base}/reset-hwid", json=data)

    if r.status_code == 200:
        embed = discord.Embed(
            title="✅ HWID Reset Successful",
            description=f"🔑 **License Key:** `{license}`\n👤 **User ID:** `{ctx.author.id}`",
            color=0x32CD32  # Green color
        )
    elif r.status_code == 401:
        embed = discord.Embed(
            title="❌ Unauthorized",
            description="Invalid API authentication. Please check your API token.",
            color=0xFF0000
        )
    elif r.status_code == 404:
        embed = discord.Embed(
            title="❌ License Not Found",
            description="No active license found for this key.",
            color=0xFFA500  # Orange color
        )
    elif r.status_code == 400:
        embed = discord.Embed(
            title="❌ Bad Request",
            description="Missing required parameters. Ensure you provide a valid license key.",
            color=0xFFFF00  # Yellow color
        )
    else:
        embed = discord.Embed(
            title="⚠️ Error",
            description="An unexpected error occurred while resetting HWID.",
            color=0xFFFF00
        )

    embed.set_footer(text="Asta Authentication", icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png")
    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name='update_user', description='Update License User', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def update_user(ctx, license: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True) 
    data = {
        "license_key": license,
        "user": str(ctx.author.id)  # Automatically use command executor's ID
    }

    r = ses.patch(f"{base}/update-user", json=data, headers=headers) 

    if r.status_code == 200:
        embed = discord.Embed(
            title="✅ User Updated Successfully",
            description=f"🔑 **License Key:** `{license}`\n👤 **New User ID:** `{ctx.author.id}`",
            color=0x32CD32  # Green color
        )
    elif r.status_code == 401:
        embed = discord.Embed(
            title="❌ Unauthorized",
            description="Invalid API authentication. Please check your API token.",
            color=0xFF0000
        )
    elif r.status_code == 404:
        embed = discord.Embed(
            title="❌ License Not Found",
            description="No active license found for this key.",
            color=0xFFA500  # Orange color
        )
    elif r.status_code == 400:
        embed = discord.Embed(
            title="❌ Bad Request",
            description="Missing required parameters. Ensure you provide a valid license key.",
            color=0xFFFF00  # Yellow color
        )
    else:
        embed = discord.Embed(
            title="⚠️ Error",
            description="An unexpected error occurred while updating the user.",
            color=0xFFFF00
        )

    embed.set_footer(text="Asta Authentication", icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png")
    await ctx.interaction.followup.send(embed=embed, ephemeral=True)


@bot.hybrid_command(name='ban_license', description='Ban License', with_app_command=True)
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def ban_license(ctx, license: str):
    await ctx.interaction.response.defer(thinking=True, ephemeral=True)  

    data = {
        "license_key": license
    }

    r = ses.post(f'{base}/ban-license', json=data)

    if r.status_code == 200:
        embed = discord.Embed(
            title="✅ License Banned",
            description=f"**🔑 License Key:** `{license}`\n**Status:** `Banned Successfully`",
            color=0xFF0000  # Red color for banned licenses
        )

    elif r.status_code == 404:
        embed = discord.Embed(
            title="❌ License Not Found",
            description="No active license found with the given key.",
            color=0xFFA500  # Orange color for not found
        )

    elif r.status_code == 400:
        embed = discord.Embed(
            title="⚠️ Invalid Request",
            description="Missing or invalid license key.",
            color=0xFFFF00  # Yellow color for warning
        )

    elif r.status_code == 401:
        embed = discord.Embed(
            title="❌ Unauthorized",
            description="Invalid API authentication. Please check your API token.",
            color=0xFF0000
        )

    else:
        embed = discord.Embed(
            title="⚠️ Error",
            description="An unexpected error occurred while banning the license.",
            color=0xFFFF00  # Yellow color for errors
        )

    # Add footer to embed
    embed.set_footer(
        text="Asta Authentication",
        icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
    )

    await ctx.interaction.followup.send(embed=embed, ephemeral=True)  # Ephemeral = only visible to the user




@bot.hybrid_command(name="deploy_hwid_panel", description="Deploy HWID Reset Panel")
@commands.has_permissions(administrator=True)
async def deploy_hwid_panel(ctx):
    embed = discord.Embed(
        title="🔄 HWID Reset Panel",
        description="Self Reset HWID",
        color=0x2B65EC  # Blue color
    )
    embed.set_footer(text="Asta Authentication", icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png")

    await ctx.send(embed=embed, view=HWIDResetView())



def extract_app_name(license_key: str):
    """Extract app name from the license key format (e.g., MyApp-M-ABCDEFGH)"""
    parts = license_key.split("-")
    return parts[0] if len(parts) > 1 else "Unknown App"

class ClaimRoleModal(ui.Modal, title="🎟️ Claim Your Roles"):
    def __init__(self):
        super().__init__()
        self.license = ui.TextInput(label="License Key", placeholder="Enter Your License", required=True)
        self.add_item(self.license)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True,ephemeral=True)

        license_key = self.license.value
        user_id = str(interaction.user.id)

        # Call the update-user API
        data = {"license_key": license_key, "user": user_id}

        response = ses.patch(f"{base}/update-user", json=data)
        result = response.json()

        if response.status_code == 200:
            app_name = extract_app_name(license_key=license_key)

            # Assign roles
            await self.assign_roles(interaction, app_name)

            embed = discord.Embed(
                title="✅ Roles Updated",
                description=f"**🎟️ License Key:** `{license_key}`\n**📌 App:** `{app_name}`\n**👤 User:** <@{user_id}>",
                color=0x32CD32
            )
        else:
            embed = discord.Embed(title="❌ Error", description=result.get("error", "Something went wrong!"), color=0xFF0000)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def assign_roles(self, interaction, app_name):
        """Creates and assigns the required roles if they don't exist"""
        guild = interaction.guild
        customer_role = discord.utils.get(guild.roles, name="Customer")
        app_role = discord.utils.get(guild.roles, name=app_name)

        if not customer_role:
            customer_role = await guild.create_role(name="Customer", color=discord.Color.blue())
        if not app_role:
            app_role = await guild.create_role(name=app_name, color=discord.Color.green())

        await interaction.user.add_roles(customer_role, app_role)


class ClaimRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Claim Roles", style=ButtonStyle.green, custom_id="claim_roles_button")
    async def claim_roles(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ClaimRoleModal())


@bot.hybrid_command(name="deploy_role_panel", description="Deploy Role Claim Panel")
@commands.has_permissions(administrator=True)
async def deploy_role_panel(ctx):
    embed = discord.Embed(
        title="🎟️ Claim Your Roles",
        description="Click the button below to claim your **Customer** & **App Role** using your license key.",
        color=0x2B65EC
    )
    await ctx.send(embed=embed, view=ClaimRoleView())


@bot.event
async def on_close():
    global session
    if session:
        await session.close()  # Properly close session when bot stops









t = config['token']

bot.run(t)  # Replace with your bot token
