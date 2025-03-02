from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request

import sqlite3
from pydantic import BaseModel
from cryptography.fernet import Fernet
import os
import secrets
import string
import base64
import pathlib
import cryptography

app = FastAPI()
DB_PATH = ".db"
PASSWORD = base64.b64encode(bytes((os.environ["PASSWORD"] * 10)[:32], "utf-8"))
cipher = Fernet(PASSWORD)

static_dir = pathlib.Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Route to serve the HTML frontend
@app.get("/", response_class=HTMLResponse)
async def get_html_frontend(request: Request):
    with open(static_dir / "index.html", "r", encoding="utf8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


class PasswordEntry(BaseModel):
    title: str
    username: str
    url: str = "N/A"             # Optional
    password: str = None         # Optional, can be generated
    generate: bool = False       # Whether to generate a random password

def get_db():
    """Dependency to get the database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
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
        conn.commit()

init_db()

def encrypt(password: str) -> str:
    return cipher.encrypt(password.encode()).decode()

def decrypt(encrypted_password: str) -> str:
    return cipher.decrypt(encrypted_password.encode()).decode()

def generate_password(length: int = 16) -> str:
    characters = set(string.ascii_letters) | set(string.digits) | set(string.punctuation)
    characters = list(characters - set(['\\']))
    return "".join(secrets.choice(characters) for _ in range(length))

@app.post("/passwords/", response_model=PasswordEntry)
def create_password(entry: PasswordEntry, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    entry.password = generate_password() if entry.generate else entry.password
    encrypted_password = encrypt(entry.password)
    try:
        query = "INSERT INTO passwords (title, username, url, password) VALUES (?, ?, ?, ?)"
        cursor.execute(query, (entry.title, entry.username, entry.url, encrypted_password))
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
        
        out.append(dict(
            title=row[0], 
            username=row[1], 
            url=row[2],
            password=password
        )) 
    
    return out

@app.get("/passwords/{title}/{username}", response_model=dict)
def read_one_password(title: str, username: str, conn: sqlite3.Connection = Depends(get_db)):
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
    title: str, 
    username: str, 
    conn: sqlite3.Connection = Depends(get_db)
):
    cursor = conn.cursor()
    query = "DELETE FROM passwords WHERE title = ? AND username = ?"
    cursor.execute(query, (title, username))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Password entry not found.")
    return {"message": "Password entry deleted."}

@app.put("/passwords/", response_model=PasswordEntry)
def update_password(
    entry: PasswordEntry, 
    conn: sqlite3.Connection = Depends(get_db)
):
    cursor = conn.cursor()
    query = "SELECT id FROM passwords WHERE title = ? AND username = ?"
    ids = cursor.execute(query, (entry.title, entry.username))
    if not ids.fetchall():
        raise HTTPException(status_code=404, detail="Password entry not found.")
    
    if entry.generate:
        entry.password = generate_password()
    
    encrypted_password = encrypt(entry.password)
    query = "UPDATE passwords SET password = ?, url = ? WHERE title = ? AND username = ?"
    cursor.execute(query, (encrypted_password, entry.url, entry.title, entry.username))
    conn.commit()

    return entry

@app.get("/titles/", response_model=list[str])
def list_titles(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT title FROM passwords")
    records = cursor.fetchall()
    return [row[0] for row in records]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
