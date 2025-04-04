from discord.ui import Modal, TextInput, Button, View
from discord.ext import commands
from discord import Button,ui,ButtonStyle
import discord , tls_client,yaml
config = open('config.yaml','r')
config = yaml.safe_load(config)
base = config['base_url']
authtoken = config['authtoken']


headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {authtoken}'}

ses = tls_client.Session()
ses.headers.update(headers)

class HWIDModal(ui.Modal, title="HWID Reset Panel"):
    def __init__(self):
        super().__init__()
        self.license = ui.TextInput(label="License", placeholder="Enter Your License Key", required=True)
        self.add_item(self.license)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True,ephemeral=True)  # Defer response for smoother interaction

        data = {
            "license_key": self.license.value,
            "user": str(interaction.user.id)  # Automatically assigns user ID
        }

        r =  ses.post(f'{base}/reset-hwid', json=data) 

        if r.status_code == 200:
            embed = discord.Embed(
                title="✅ HWID Reset Successful",
                description=f"**🔑 License Key:** `{self.license.value}`\n**🟢 Status:** `HWID Reset Completed`",
                color=0x32CD32  # Green color
            )
        elif r.status_code == 404:
            embed = discord.Embed(
                title="❌ License Not Found",
                description="No active license found with the given key.",
                color=0xFFA500  # Orange
            )
        elif r.status_code == 400:
            embed = discord.Embed(
                title="⚠️ Invalid Request",
                description="Invalid or missing license key.",
                color=0xFFFF00  # Yellow
            )
        elif r.status_code == 401:
            embed = discord.Embed(
                title="❌ Unauthorized",
                description="Invalid API authentication.",
                color=0xFF0000  # Red
            )
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while resetting HWID.",
                color=0xFFFF00
            )

        embed.set_footer(
            text="Asta Authentication",
            icon_url="https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class HWIDResetView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Reset HWID", style=ButtonStyle.green, custom_id="reset_hwid_button")
    async def reset_hwid(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(HWIDModal())