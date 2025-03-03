import base64
import hashlib
import pathlib
import secrets
import sqlite3
import string
from getpass import getpass

import cryptography
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT_DIR = pathlib.Path(__file__).parent.parent.parent
DB_PATH = str(ROOT_DIR / ".db")
STATIC_DIR = ROOT_DIR / "static"
cipher = None


def init_cipher(master_password: str):
    global cipher
    encoded_pass = base64.b64encode(bytes((master_password * 8)[:32], "utf-8"))
    cipher = Fernet(encoded_pass)


def get_cipher():
    if not cipher:
        raise RuntimeError("Cipher not initialized. Start server with CLI.")
    return cipher


def hash_password(master_password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(master_password.encode()).hexdigest()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Route to serve the HTML frontend
@app.get("/", response_class=HTMLResponse)
async def get_html_frontend():
    html_path = STATIC_DIR / "index.html"
    with open(html_path, "r", encoding="utf8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


class PasswordEntry(BaseModel):
    title: str
    username: str
    url: str = "N/A"  # Optional
    password: str = None  # Optional, can be generated
    generate: bool = False  # Whether to generate a random password


def get_db():
    """Dependency to get the database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


def create_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Create passwords table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                username TEXT NOT NULL,
                url TEXT NOT NULL,
                password TEXT NOT NULL,
                UNIQUE (title, username)
            )
        """)

        # Simplified master_password table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_password (
                id INTEGER PRIMARY KEY,
                password_hash TEXT NOT NULL
            )
        """)
        conn.commit()


def is_db_initialized() -> bool:
    """Check if master password is set."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM master_password")
        return cursor.fetchone()[0] > 0


def setup_master_password():
    """Initial setup of master password."""

    print("\nWelcome to KeyPass! Setting up your master password...")
    print("\n⚠️ WARNING: \nThis password cannot be changed or recovered.")
    print("Make sure to remember it and keep it secure. 🗃️🗝️\n")

    while True:
        password = getpass("🔑 Create master password: ")
        if len(password) < 4:
            print("❌ Password must be at least 4 characters long.")
            continue

        confirm = getpass("🔄 Verify master password: ")
        if password == confirm:
            break
        else:
            print("❌ Passwords don't match. Try again.\n")
            continue

    print("\n✨ Setting up your vault...")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO master_password (password_hash) VALUES (?)",
            (hash_password(password),),
        )
        conn.commit()

    print("✅ Setup complete! Your vault is ready.")
    return password


def verify_master_password(password: str) -> bool:
    """Verify if master password is correct."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM master_password")
        stored_hash = cursor.fetchone()[0]
        return hash_password(password) == stored_hash


def encrypt(password: str) -> str:
    return get_cipher().encrypt(password.encode()).decode()


def decrypt(encrypted_password: str) -> str:
    return get_cipher().decrypt(encrypted_password.encode()).decode()


def generate_password(length: int = 16) -> str:
    characters = (
        set(string.ascii_letters) | set(string.digits) | set(string.punctuation)
    )
    characters = list(characters - set(["\\"]))
    return "".join(secrets.choice(characters) for _ in range(length))


@app.post("/passwords/", response_model=PasswordEntry)
def create_password(entry: PasswordEntry, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    entry.password = generate_password() if entry.generate else entry.password
    encrypted_password = encrypt(entry.password)
    try:
        query = (
            "INSERT INTO passwords (title, username, url, password) VALUES (?, ?, ?, ?)"
        )
        cursor.execute(
            query, (entry.title, entry.username, entry.url, encrypted_password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Username already exists for this title.",
        )

    return entry


@app.get("/passwords/{title}", response_model=list[dict])
def read_password(title: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    query = "SELECT title, username, url, password FROM passwords WHERE title = ?"
    cursor.execute(query, (title,))
    records = cursor.fetchall()
    if not records:
        raise HTTPException(status_code=404, detail="title not found.")

    out = []
    for row in records:
        try:
            password = decrypt(row[3])
        except cryptography.fernet.InvalidToken:
            message = "Invalid credentials. Set main password correctly."
            raise HTTPException(status_code=401, detail=message)

        out.append(dict(title=row[0], username=row[1], url=row[2], password=password))

    return out


@app.get("/passwords/{title}/{username}", response_model=dict)
def read_one_password(
    title: str, username: str, conn: sqlite3.Connection = Depends(get_db)
):
    cursor = conn.cursor()
    query = "SELECT url, password FROM passwords WHERE title = ? AND username = ?"
    cursor.execute(query, (title, username))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found.")

    try:
        password = decrypt(row[1])
    except cryptography.fernet.InvalidToken:
        message = "Invalid credentials. Set main password correctly."
        raise HTTPException(status_code=401, detail=message)

    return dict(title=title, username=username, url=row[0], password=password)


@app.delete("/passwords/{title}/{username}")
def delete_password(
    title: str, username: str, conn: sqlite3.Connection = Depends(get_db)
):
    cursor = conn.cursor()
    query = "DELETE FROM passwords WHERE title = ? AND username = ?"
    cursor.execute(query, (title, username))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Password entry not found.")
    return {"message": "Password entry deleted."}


@app.put("/passwords/", response_model=PasswordEntry)
def update_password(entry: PasswordEntry, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    query = "SELECT id FROM passwords WHERE title = ? AND username = ?"
    ids = cursor.execute(query, (entry.title, entry.username))
    if not ids.fetchall():
        raise HTTPException(status_code=404, detail="Password entry not found.")

    if entry.generate:
        entry.password = generate_password()

    encrypted_password = encrypt(entry.password)
    query = (
        "UPDATE passwords SET password = ?, url = ? WHERE title = ? AND username = ?"
    )
    cursor.execute(query, (encrypted_password, entry.url, entry.title, entry.username))
    conn.commit()

    return entry


@app.get("/titles/", response_model=list[str])
def list_titles(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT title FROM passwords")
    records = cursor.fetchall()
    return [row[0] for row in records]


BANNER = """

██╗  ██╗███████╗██╗   ██╗██████╗  █████╗ ███████╗███████╗
██║ ██╔╝██╔════╝╚██╗ ██╔╝██╔══██╗██╔══██╗██╔════╝██╔════╝
█████╔╝ █████╗   ╚████╔╝ ██████╔╝███████║███████╗███████╗
██╔═██╗ ██╔══╝    ╚██╔╝  ██╔═══╝ ██╔══██║╚════██║╚════██║
██║  ██╗███████╗   ██║   ██║     ██║  ██║███████║███████║
╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝
"""


if __name__ == "__main__":
    import sys
    import uvicorn

    print(BANNER)

    create_db()
    if not is_db_initialized():
        password = setup_master_password()
    else:
        print("\n🔒 Enter master password: ")
        attempts = 0
        while attempts < 3:
            password = getpass("")
            if verify_master_password(password):
                print("✅ Authentication successful!")
                break
            attempts += 1
            print(f"❌ {3 - attempts} attempts remaining.")
        else:
            print("\nMaximum attempts reached. Exiting...")
            sys.exit(0)

    print("\n🚀 Starting server...")
    init_cipher(password)
    print("✨ Server is ready! Access your vault at http://localhost:8000\n")
    uvicorn.run(app, host="localhost", port=8000)
