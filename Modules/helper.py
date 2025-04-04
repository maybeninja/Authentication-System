from dhooks import Webhook, Embed 
import yaml,subprocess,uuid,platform

import requests
import yaml

# Load config
config = yaml.safe_load(open('config.yaml'))
botlogs = config['Webhook']['BotLogs']
apilog = config['Webhook']['APILogs']

def log(type, task, content, color):
    url = 'https://discord.com/api/webhooks/1354847772746059938/UrSH8C7q9uzwyDjKlp872zAp4WEiNeoEzJV7yOe3yFEcx5rVfdBKROYEqCK0ZVRpKClU'

    embed = {
        "title": task,
        "description": content,
        "color": color,
        "footer": {
            "text": "Asta Authentication",
            "icon_url": "https://cdn.discordapp.com/attachments/1347150387978829914/1354349432346378250/9326f77b21c7947fe459484eafc41e9a.png"
        }
    }

    payload = {"embeds": [embed]}

    response = requests.post(url, json=payload)

    if response.status_code != 204:
        print(f"Failed to send log: {response.status_code} - {response.text}")
    else:
        print(f'{"API" if type == "api" else "Bot"} Log Sent To Discord')


def gethwid():
    system = platform.system()

    if system == "Windows":
        hwid = subprocess.check_output("wmic csproduct get uuid", shell=True).decode().split("\n")[1].strip()
      

    elif system == "Linux":
        return str(uuid.getnode()) 

    elif system == "Darwin":  
        hwid = subprocess.check_output("ioreg -l | grep IOPlatformSerialNumber", shell=True).decode().split('"')[-2]
        return hwid
        






    