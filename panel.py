"""
panel.py — Discord UI Components
Improvements:
  - Shared session via dependency injection (no duplicate session)
  - Consistent embed builder helper
  - Cleaner HWID modal with better UX copy
"""

import discord
from discord import ui, ButtonStyle
import tls_client
import yaml

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

BASE_URL: str = config["base_url"]
AUTH_TOKEN: str = config["authtoken"]
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"}
FOOTER_TEXT = "Auth System"
FOOTER_ICON = "https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"

_session = tls_client.Session()
_session.headers.update(HEADERS)


def make_embed(title: str, description: str, color: int) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    return embed


def get_session() -> tls_client.Session:
    return _session


class HWIDModal(ui.Modal, title="🔄 HWID Reset"):
    license_key = ui.TextInput(
        label="License Key",
        placeholder="e.g. MyApp-M-Abc12345",
        required=True,
        min_length=5,
        max_length=64,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        key = self.license_key.value.strip()
        user_id = str(interaction.user.id)

        r = get_session().post(f"{BASE_URL}/reset-hwid", json={"license_key": key, "user": user_id})

        status_map = {
            200: make_embed(
                "✅ HWID Reset Successful",
                f"**🔑 License:** `{key}`\n**👤 User:** <@{user_id}>\n**Status:** Reset complete",
                0x32CD32,
            ),
            403: make_embed("🚫 License Banned", "License sharing was detected. Your license has been banned.", 0xFF0000),
            404: make_embed("❌ Not Found", "No active license found for that key.", 0xFFA500),
            400: make_embed("⚠️ Bad Request", "Invalid or missing license key.", 0xFFFF00),
            401: make_embed("❌ Unauthorized", "API authentication failed.", 0xFF0000),
        }
        embed = status_map.get(r.status_code, make_embed("⚠️ Error", "An unexpected error occurred.", 0xFFFF00))
        await interaction.followup.send(embed=embed, ephemeral=True)


class HWIDResetView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 Reset HWID", style=ButtonStyle.green, custom_id="reset_hwid_button")
    async def reset_hwid(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(HWIDModal())


class ClaimRoleModal(ui.Modal, title="🎟️ Claim Your Roles"):
    license_key = ui.TextInput(
        label="License Key",
        placeholder="Enter your license key",
        required=True,
        min_length=5,
        max_length=64,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        key = self.license_key.value.strip()
        user_id = str(interaction.user.id)

        r = get_session().patch(f"{BASE_URL}/update-user", json={"license_key": key, "user": user_id})

        if r.status_code == 200:
            app_name = key.split("-")[0] if "-" in key else "Unknown"
            await _assign_roles(interaction, app_name)
            embed = make_embed(
                "✅ Roles Claimed",
                f"**🔑 License:** `{key}`\n**📌 App:** `{app_name}`\n**👤 User:** <@{user_id}>",
                0x32CD32,
            )
        else:
            result = r.json()
            embed = make_embed("❌ Error", result.get("error", "Something went wrong."), 0xFF0000)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def _assign_roles(interaction: discord.Interaction, app_name: str):
    guild = interaction.guild
    for role_name in ("Customer", app_name):
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(
                name=role_name,
                color=discord.Color.blue() if role_name == "Customer" else discord.Color.green(),
            )
        await interaction.user.add_roles(role)


class ClaimRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎟️ Claim Roles", style=ButtonStyle.green, custom_id="claim_roles_button")
    async def claim_roles(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ClaimRoleModal())
