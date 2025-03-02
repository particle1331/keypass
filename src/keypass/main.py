from fastapi import FastAPI, HTTPException, Depends
import sqlite3
from pydantic import BaseModel
from cryptography.fernet import Fernet
import os
import secrets
import string
import argparse
import base64
import cryptography


app = FastAPI()
pw = base64.b64encode(bytes((os.environ["PASSWORD"] * 10)[:32], "utf-8"))
cipher = Fernet(pw)
DB_PATH = ".db"


class PasswordEntry(BaseModel):
    website: str
    username: str
    password: str = None         # Optional, can be generated
    generate: bool = False       # Whether to generate a random password


def get_db():
    """Dependency to get the database connection."""
    conn = sqlite3.connect(DB_PATH)
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
                website TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                UNIQUE (website, username)
            )
        """)
        conn.commit()


init_db()


def encrypt(password: str) -> str:
    return cipher.encrypt(password.encode()).decode()

def decrypt(encrypted_password: str) -> str:
    return cipher.decrypt(encrypted_password.encode()).decode()

def generate_password(length: int = 16) -> str:
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(characters) for _ in range(length))


@app.post("/passwords/", response_model=PasswordEntry)
def create_password(entry: PasswordEntry, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    entry.password = generate_password() if entry.generate else entry.password
    encrypted_password = encrypt(entry.password)
    try:
        query = "INSERT INTO passwords (website, username, password) VALUES (?, ?, ?)"
        cursor.execute(query, (entry.website, entry.username, encrypted_password))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400, 
            detail="Username already exists for this website.",
        )

    return entry


@app.get("/passwords/{website}", response_model=list[dict])
def read_password(website: str, conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    query = "SELECT website, username, password FROM passwords WHERE website = ?"
    cursor.execute(query, (website,))
    records = cursor.fetchall()
    if not records:
        raise HTTPException(status_code=404, detail="Website not found.")

    out = []
    for row in records:
        try:
            password = decrypt(row[2])
        except cryptography.fernet.InvalidToken:
            message = "Invalid credentials. Set main password correctly."
            raise HTTPException(status_code=401, detail=message)
        
        out.append(dict(
            website=row[0], 
            username=row[1], 
            password=password
        )) 
    
    return out


@app.delete("/passwords/{website}/{username}")
def delete_password(
    website: str, 
    username: str, 
    conn: sqlite3.Connection = Depends(get_db)
):
    cursor = conn.cursor()
    query = "DELETE FROM passwords WHERE website = ? AND username = ?"
    cursor.execute(query, (website, username))
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
    query = "SELECT id FROM passwords WHERE website = ? AND username = ?"
    ids = cursor.execute(query, (entry.website, entry.username))
    if len(ids.fetchall()) == 0:
        raise HTTPException(status_code=404, detail="Password entry not found.")
    
    if entry.generate:
        entry.password = generate_password()
    
    encrypted_password = encrypt(entry.password)
    query = "UPDATE passwords SET password = ? WHERE website = ? AND username = ?"
    cursor.execute(query, (encrypted_password, entry.website, entry.username))
    conn.commit()

    return entry


@app.get("/websites/", response_model=list[str])
def list_websites(conn: sqlite3.Connection = Depends(get_db)):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT website FROM passwords")
    records = cursor.fetchall()
    return [row[0] for row in records]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
