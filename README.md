# Pterodactyl & Discord Automation Panel

A FastAPI-based web application that automates Pterodactyl server deployment and management, integrated with Discord OAuth2 authentication and database logging.

## 🚀 Prerequisites

Before setting up the project, ensure your environment meets the following requirements:

* **Python:** `python 3.11` (or higher)
* **Game Panel:** [Pterodactyl Panel](https://pterodactyl.io/) (Admin access required)
* **Database:** MongoDB instance

---

## 🛠️ Environment Configuration

1. Copy the `.env.example` file to create your own configuration:
```bash
cp .env.example .env
```


2. Open `.env` and fill in your variables:

```ini
# Discord Bot OAuth2 Configurations
client_id="YOUR_DISCORD_BOT_ID"
client_secret="YOUR_DISCORD_BOT_SECRET"
callback="http://localhost:8000/auth/callback"

# MongoDB Database Settings
mongo_uri="mongodb://localhost:27017"
mongo_db="your_database_name"
mongo_collection="your_collection_name"

# Pterodactyl Panel Settings
panel_url="https://your-panel-url.com"
panel_key="ptla_your_admin_api_key_here"
nest_id=7
location_ids=[2]
PORT_RANGE="[]"

# System Logs & Notifications
webhook="https://discord.com/api/webhooks/..."
```

### 📋 Configuration Fields Explained

| Variable | Description |
| --- | --- |
| `client_id` / `client_secret` | Obtained from the [Discord Developer Portal](https://discord.com/developers/applications). Used for user authentication. |
| `callback` | The URL Discord redirects to after successful login. Must match the redirect URI set in the Discord portal. |
| `mongo_*` | Credentials to connect to your local or remote MongoDB instance for caching and user quota tracking. |
| `panel_url` / `panel_key` | Your Pterodactyl panel domain and an **Application API Key** with full administrator privileges. |
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

## ⚠️ Known Issues

* **Pterodactyl Client:** The application still encounters occasional `Unclosed client session` errors during specific API requests, particularly during server deletion.

## ⭐ Support the Project

If this project helped you or you find it useful, please consider giving it a **Star**! It means a lot to us and helps keep the project alive. 🌟

