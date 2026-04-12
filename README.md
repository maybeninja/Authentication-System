# 🔐 Auth System v2.0

A license management backend with Flask API, Discord bot, and web dashboard.

## Structure
```
Authentication-System/
├── server.py           # Flask REST API
├── bot.py              # Discord bot
├── panel.py            # Discord UI components
├── requirements.txt    # Python dependencies
├── config.yaml         # Your config (never commit this!)
├── frontend/
│   └── dashboard.html  # Web dashboard (admin + user portal)
└── docs/
    └── index.html      # API documentation site
```

## Setup
```bash
pip install -r requirements.txt
python server.py   # Start API server
python bot.py      # Start Discord bot (separate terminal)
```

## config.yaml
```yaml
authtoken: your_secret_token_here
port: 5000
base_url: http://localhost:5000/Auth
token: your_discord_bot_token
```

## Docs
Open `docs/index.html` in your browser for full API documentation.

## Dashboard
Open `frontend/dashboard.html` in your browser for the admin + user portal.
