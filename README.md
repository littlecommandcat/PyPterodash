# Pterodactyl & Discord Automation Panel

A FastAPI-based web application that automates Pterodactyl server deployment and management, integrated with Discord OAuth2 authentication and database logging.

## 🚀 Prerequisites

Before setting up the project, ensure your environment meets the following requirements:

* **Python:** `python 3.11` (or higher)
* **Panel:** [Pterodactyl Panel](https://pterodactyl.io/) (Admin access required)
* **Database:** MongoDB instance
* **Discord:** Webhook

---

## 🛠️ Environment Configuration

1. Copy the `.env.example` file to create your own configuration:
```bash
cp .env.example .env
```


2. Open `.env` and fill in your variables:

```ini
# Discord Bot OAuth2 Secret
client_secret="YOUR_DISCORD_BOT_SECRET"

# MongoDB Database Settings
mongo_uri="mongodb://localhost:27017"

# Pterodactyl Panel Key
panel_key="ptla_your_admin_api_key_here"

# System Logs & Notifications (Discord Webhook)
discord_webhook="https://discord.com/api/webhooks/..."
```

3. Open `setting.yml` and fill your dash settings:

```yml
# Application Configuration
app:
  # Host address to bind the web server
  host: "0.0.0.0"

  # Port used by the web server
  port: 8000

  # Enable debug mode
  debug: false

  # Debug secret key (If debug is true)
  key: "sfjsdghfdkjdlk"

  # Enable docs route
  docs: false


# Discord OAuth2 Configuration
discord:
  # OAuth2 callback URL
  # This URL must match the redirect URL configured in Discord Developer Portal
  callback: "http://localhost:8000/api/auth/callback"

  # Discord Application Client ID
  client_id: "YOUR_DISCORD_CLIENT_ID"

  # Discord server invite link
  invite: "https://discord.gg/YOUR_INVITE_CODE"


# Database Configuration
database:
  # Database name
  db: "your_database_name"

  # Collection name
  collection: "your_collection_name"


# Pterodactyl Configuration
pterodactyl:
  # Pterodactyl panel URL
  url: "https://panel.example.com"

  # Default Nest ID used when creating servers
  nest_id: 1

  # Available location IDs for server deployment
  location_ids: [1]

  # Allowed port allocation range
  # Leave empty to disable custom port restriction
  port_range: []


# Pricing Configuration
price:
  # Price per CPU
  cpu: 5

  # Price per MB of RAM
  ram: 10

  # Price per MB of disk storage
  disk: 5
```

### 📋 Configuration Fields Explained

| Variable | Description |
| --- | --- |
| `client_id` / `client_secret` | Obtained from the [Discord Developer Portal](https://discord.com/developers/applications). Used for user authentication. |
| `callback` | The URL Discord redirects to after successful login. Must match the redirect URI set in the Discord portal. |
| `mongo_*` / `database` | Credentials to connect to your local or remote MongoDB instance for caching and user quota tracking. |
| `panel_key` / `panel` | Your Pterodactyl panel domain and an **Application API Key** with full administrator privileges. |
| `nest_id` | The ID of the default Pterodactyl Nest used for deploying new servers (e.g., Node.js, Python Nests). |
| `location_ids` | A list of node location IDs where new servers are allowed to be created. |
| `webhook` | A Discord webhook URL used to log panel activities (e.g., server creation/deletion events). |

---

## ⚡ Installation & Setup

1. Clone this repository and navigate to the project directory:
```bash
git clone https://github.com/littlecommandcat/PyPterodash.git
```


2. Create a virtual environment using Python 3.11:
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```


3. Install the dependencies:
```bash
pip install -r requirements.txt
```

---

## ⚡ Running the Development Server

You can start the development server using either of the following methods:

* **Method 1: Using Uvicorn (Recommended)**
```bash
uvicorn app.main:app --reload --port 8000
```

* **Method 2: Using the Python Script**
```bash
python main.py
```

## ⭐ Support the Project

If this project helped you or you find it useful, please consider giving it a **Star**! It means a lot to us and helps keep the project alive. 🌟

