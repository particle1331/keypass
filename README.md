# keypass: Password Vault

A lightweight, local password manager that combines simplicity with strong encryption.

- 🔑 Encryption using Fernet symmetric cryptography
- 🔒 Secure storage with portable SQLite database
- ✨ Full CRUD operations support
- 🌐 Clean web interface for easy access
- 🎲 Automatic strong password generation
- 📋 Clipboard support for masked password copying


## Installation

Clone this repository:
```bash
git clone git@github.com:particle1331/keypass.git
cd keypass
```

## Usage 

1. Start the server:
```bash
uv run python -m keypass.main
```

2. When prompted, enter your master password

3. Open your browser at http://localhost:8000

> [!WARNING]  
> The master password cannot be changed or recovered.
> Make sure to remember it and keep it secure.
> If lost, the encrypted data cannot be recovered.


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
2. Backup your `.db` file regularly but keep it secure.
3. Don't expose the server to the internet - it's designed for local use only.
4. There is no recovery mechanism for a lost password.
