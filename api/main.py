import os, json
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json
import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Literal

# ---------- Configuration (lue dans infra/.env, jamais en clair) ----------
load_dotenv("../infra/.env")
DB_URL = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
          f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/sentinel")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
PREFIX = os.getenv("MQTT_PREFIX", "sentinel/G1")

TELEMETRY_FIELDS = ["device", "seq", "temperature", "humidity", "gas_raw",
                    "gas_index", "pir", "state", "rssi", "heap"]

def db():
    return psycopg.connect(DB_URL, row_factory=dict_row, autocommit=True)

# ---------- Création des tables au démarrage ----------
def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS telemetry (
            id SERIAL PRIMARY KEY, received_at TIMESTAMPTZ DEFAULT now(),
            device TEXT, seq INT, temperature REAL, humidity REAL,
            gas_raw INT, gas_index INT, pir BOOLEAN, state TEXT, rssi INT, heap INT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY, received_at TIMESTAMPTZ DEFAULT now(),
            source TEXT, device TEXT, type TEXT, level TEXT, payload JSONB)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS device_status (
            prefix TEXT PRIMARY KEY, status TEXT, updated_at TIMESTAMPTZ DEFAULT now())""")

# ---------- La "secrétaire" MQTT : écoute et range ----------
def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(f"{PREFIX}/#")
    print(f"[MQTT] Connectée, abonnée à {PREFIX}/#")

def on_message(client, userdata, msg):
    topic = msg.topic.removeprefix(PREFIX + "/")
    payload = msg.payload.decode()
    try:
        with db() as conn:
            if topic == "telemetry":
                data = json.loads(payload)
                row = {k: data.get(k) for k in TELEMETRY_FIELDS}
                conn.execute(
                    "INSERT INTO telemetry (device, seq, temperature, humidity, gas_raw, "
                    "gas_index, pir, state, rssi, heap) VALUES (%(device)s, %(seq)s, "
                    "%(temperature)s, %(humidity)s, %(gas_raw)s, %(gas_index)s, %(pir)s, "
                    "%(state)s, %(rssi)s, %(heap)s)", row)
            elif topic == "alert":
                data = json.loads(payload)
                conn.execute(
                    "INSERT INTO alerts (source, device, type, level, payload) "
                    "VALUES ('device', %s, 'state_change', %s, %s)",
                    (data.get("device"), data.get("current"), Json(data)))
            elif topic == "status":
                conn.execute(
                    "INSERT INTO device_status (prefix, status) VALUES (%s, %s) "
                    "ON CONFLICT (prefix) DO UPDATE SET status = EXCLUDED.status, "
                    "updated_at = now()", (PREFIX, payload))
    except Exception as e:
        print(f"[MQTT] Message ignoré sur {msg.topic} : {e}")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sentinel-api")
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

@asynccontextmanager
async def lifespan(app):
    init_db()
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()
    yield
    mqtt_client.loop_stop()

app = FastAPI(title="Sentinel-X API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- Les routes ----------
class AlertIn(BaseModel):
    device: str
    type: str          # ex : "gas_anomaly", "intrusion"
    level: str         # ex : "warning", "critical"
    details: dict | None = None

class CommandIn(BaseModel):
    buzzer: bool | None = None
    led_red: bool | None = None
    action: Literal["reset"] | None = None  # "reset"

@app.get("/api/v1/health")
def health():
    return {"api": "ok", "mqtt": mqtt_client.is_connected()}

@app.get("/api/v1/telemetry")
def telemetry(limit: int = 100):
    with db() as conn:
        rows = conn.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
    return list(reversed(rows))

@app.get("/api/v1/telemetry/latest")
def telemetry_latest():
    with db() as conn:
        return conn.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 1").fetchone()

@app.get("/api/v1/status")
def status():
    with db() as conn:
        return conn.execute("SELECT * FROM device_status WHERE prefix = %s", (PREFIX,)).fetchone()

@app.get("/api/v1/alerts")
def alerts(limit: int = 50):
    with db() as conn:
        return conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT %s", (limit,)).fetchall()

@app.post("/api/v1/alerts", status_code=201)
def create_alert(alert: AlertIn):
    with db() as conn:
        return conn.execute(
            "INSERT INTO alerts (source, device, type, level, payload) "
            "VALUES ('api', %s, %s, %s, %s) RETURNING *",
            (alert.device, alert.type, alert.level, Json(alert.details or {}))).fetchone()

@app.post("/api/v1/commands")
def send_command(cmd: CommandIn):
    message = cmd.model_dump(exclude_none=True)
    mqtt_client.publish(f"{PREFIX}/command", json.dumps(message), qos=1)
    return {"sent": message}