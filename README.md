# KeyPass - Lightweight Password Manager

A password manager built with FastAPI that combines simplicity with strong encryption.

## Features

- 🔑 Encryption using Fernet symmetric cryptography
- 🔒 Secure storage with portable SQLite database
- 📱 Multi-device compatible
- ✨ Full CRUD operations support
- 🌐 Clean web interface for easy access
- 🎲 Automatic strong password generation
- 📋 Clipboard support for masked password copying


## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd keypass
```

2. Install dependencies using pip or uv:
```
uv pip install -r requirements.txt
```

## Usage 

1. Start the server:
```bash
uv run main.py
```

2. When prompted, enter your master password (input will be hidden)

3. Open your browser at http://localhost:8000

> [!NOTE]  
> The password entered at startup is used to encrypt/decrypt entries.
> Entries created in a session can only be decrypted with the same master password used during creation.
> If you use different master passwords across sessions, entries will only be accessible with their corresponding master password.


## Database Structure

```sql
CREATE TABLE passwords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    username TEXT NOT NULL,
    url TEXT NOT NULL,
    password TEXT NOT NULL,
    UNIQUE (title, username)
)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| GET | `/titles/` | List all unique titles |
| POST | `/passwords/` | Create new password entry |
| GET | `/passwords/{title}` | Get all entries for a title |
| GET | `/passwords/{title}/{username}` | Get specific entry |
| PUT | `/passwords/` | Update password entry |
| DELETE | `/passwords/{title}/{username}` | Delete entry |

## Security Best practices

1. Keep your master password secure and don't share it.
1. Use different master passwords for different security levels.
2. Backup your `.db` file regularly but keep it secure.
3. Don't expose the server to the internet - it's designed for local use only.
