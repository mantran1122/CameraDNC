import sqlite3
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from config import STORAGE_DIR

DB_PATH = STORAGE_DIR / "camera_metadata.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table for raw and processed events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_code TEXT NOT NULL,
        event_type TEXT NOT NULL, -- 'audio_anomaly', 'video_anomaly', 'normal_metadata'
        channel INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT NOT NULL, -- 'high', 'medium', 'info'
        audio_level_db REAL,
        metadata_json TEXT,
        clip_filename TEXT,
        clip_duration_sec INTEGER DEFAULT 10
    );
    """)
    
    # Table for aggregated daily summary
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        date_str TEXT PRIMARY KEY,
        total_events INTEGER DEFAULT 0,
        anomaly_video_count INTEGER DEFAULT 0,
        anomaly_audio_count INTEGER DEFAULT 0,
        total_human_count INTEGER DEFAULT 0,
        total_vehicle_count INTEGER DEFAULT 0,
        peak_hour INTEGER DEFAULT 12,
        summary_text TEXT
    );
    """)
    
    conn.commit()
    conn.close()

def save_event(
    event_code: str,
    event_type: str,
    channel: int,
    timestamp: str,
    description: str,
    severity: str = "medium",
    audio_level_db: Optional[float] = None,
    metadata_dict: Optional[Dict[str, Any]] = None,
    clip_filename: Optional[str] = None,
    clip_duration_sec: int = 10
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    meta_json = json.dumps(metadata_dict or {}, ensure_ascii=False)
    cursor.execute("""
        INSERT INTO events (
            event_code, event_type, channel, timestamp, description, severity, audio_level_db, metadata_json, clip_filename, clip_duration_sec
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (event_code, event_type, channel, timestamp, description, severity, audio_level_db, meta_json, clip_filename, clip_duration_sec))
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_events(
    event_type: Optional[str] = None,
    channel: Optional[int] = None,
    limit: int = 50,
    only_anomalies: bool = False
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    
    if only_anomalies:
        query += " AND event_type IN ('audio_anomaly', 'video_anomaly')"
    elif event_type:
        query += " AND event_type = ?"
        params.append(event_type)
        
    if channel:
        query += " AND channel = ?"
        params.append(channel)
        
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        if item["metadata_json"]:
            try:
                item["metadata"] = json.loads(item["metadata_json"])
            except Exception:
                item["metadata"] = {}
        else:
            item["metadata"] = {}
        del item["metadata_json"]
        result.append(item)
    return result

def get_event_by_id(event_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    if item["metadata_json"]:
        try:
            item["metadata"] = json.loads(item["metadata_json"])
        except Exception:
            item["metadata"] = {}
    del item["metadata_json"]
    return item

def update_event_clip(event_id: int, clip_filename: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET clip_filename = ? WHERE id = ?", (clip_filename, event_id))
    conn.commit()
    conn.close()

# Initialize DB on module import
init_db()
