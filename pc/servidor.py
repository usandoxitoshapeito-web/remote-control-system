#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
from uuid import uuid4
from datetime import datetime
import sqlite3
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Database
DB_PATH = Path("devices.db")

def init_db():
    """Inicializa o banco de dados"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            nickname TEXT,
            photo_path TEXT,
            status TEXT DEFAULT 'offline',
            token TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            last_seen TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            event_type TEXT,
            data TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (device_id) REFERENCES devices (device_id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    """Retorna conexão com banco"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# FastAPI App
app = FastAPI(
    title="Remote Control Server",
    description="Servidor de controle remoto para Android",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazena conexões WebSocket ativas
active_connections = {}

# Rotas HTTP

@app.on_event("startup")
async def startup():
    """Inicializa no startup"""
    init_db()
    print("✓ Servidor iniciado")
    print("✓ Banco de dados pronto")

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Remote Control Server",
        "version": "1.0.0"
    }

@app.post("/device/register")
async def register_device(device_name: str, nickname: str = "", photo_path: str = ""):
    """Registra um novo dispositivo"""
    device_id = str(uuid4())
    token = str(uuid4())
    now = datetime.utcnow().isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO devices (device_id, device_name, nickname, photo_path, status, token, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, device_name, nickname or device_name, photo_path, "offline", token, now)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    
    conn.close()
    
    return {
        "device_id": device_id,
        "token": token,
        "status": "registered",
        "message": "Dispositivo registrado com sucesso"
    }

@app.get("/devices")
async def list_devices():
    """Lista todos os dispositivos"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT device_id, device_name, nickname, status, token, photo_path, last_seen FROM devices ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    
    devices = []
    for row in rows:
        devices.append({
            "device_id": row[0],
            "device_name": row[1],
            "nickname": row[2],
            "status": row[3],
            "token": row[4],
            "photo_path": row[5],
            "last_seen": row[6]
        })
    
    return devices

@app.get("/device/{device_id}")
async def get_device(device_id: str):
    """Retorna informações de um dispositivo"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT device_id, device_name, nickname, status, token, photo_path, last_seen FROM devices WHERE device_id = ?",
        (device_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    
    return {
        "device_id": row[0],
        "device_name": row[1],
        "nickname": row[2],
        "status": row[3],
        "token": row[4],
        "photo_path": row[5],
        "last_seen": row[6]
    }

@app.delete("/device/{device_id}")
async def delete_device(device_id: str):
    """Remove um dispositivo"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()
    
    return {"status": "deleted"}

# WebSocket

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """Conexão WebSocket para dispositivo Android"""
    
    # Valida token
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, device_name FROM devices WHERE token = ?", (token,))
    device = cursor.fetchone()
    conn.close()
    
    if not device:
        await websocket.close(code=1008, reason="Token inválido")
        return
    
    device_id = device[0]
    device_name = device[1]
    
    await websocket.accept()
    active_connections[device_id] = websocket
    
    # Atualiza status para online
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE devices SET status = ?, last_seen = ? WHERE device_id = ?",
        ("online", datetime.utcnow().isoformat(), device_id)
    )
    conn.commit()
    conn.close()
    
    print(f"✓ Dispositivo conectado: {device_name} ({device_id})")
    
    try:
        while True:
            # Recebe mensagem do Android
            data = await websocket.receive_text()
            message = json.loads(data)
            
            print(f"[{device_name}] {message}")
            
            # Processa heartbeat
            if message.get("type") == "heartbeat":
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE devices SET last_seen = ? WHERE device_id = ?",
                    (datetime.utcnow().isoformat(), device_id)
                )
                conn.commit()
                conn.close()
                
                await websocket.send_text(json.dumps({"type": "heartbeat_ack"}))
            
            # Processa screen frames
            elif message.get("type") == "screen_frame":
                # Salva evento
                event_id = str(uuid4())
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO events (event_id, device_id, event_type, data, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (event_id, device_id, "screen_frame", json.dumps(message), datetime.utcnow().isoformat())
                )
                conn.commit()
                conn.close()
                
                await websocket.send_text(json.dumps({"type": "frame_received"}))
            
            # Processa input (toque, swipe)
            elif message.get("type") == "input":
                await websocket.send_text(json.dumps({"type": "input_ack"}))
    
    except WebSocketDisconnect:
        active_connections.pop(device_id, None)
        
        # Atualiza status para offline
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE devices SET status = ? WHERE device_id = ?",
            ("offline", device_id)
        )
        conn.commit()
        conn.close()
        
        print(f"✗ Dispositivo desconectado: {device_name}")

# Função para enviar comando do PC para Android
async def send_command_to_device(device_id: str, command: dict):
    """Envia comando do PC para o Android"""
    if device_id in active_connections:
        try:
            await active_connections[device_id].send_text(json.dumps(command))
            return True
        except Exception as e:
            print(f"Erro ao enviar comando: {e}")
            return False
    return False

if __name__ == "__main__":
    init_db()
    print("🚀 Iniciando Remote Control Server")
    print("📡 Servidor em http://127.0.0.1:8000")
    print("📚 Docs em http://127.0.0.1:8000/docs")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
