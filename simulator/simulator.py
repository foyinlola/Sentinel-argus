import json, random, time
import paho.mqtt.client as mqtt

BROKER = "localhost"        # "broker.hivemq.com" pour tester avec le broker public
PORT = 1883
PREFIX = "sentinel/G1"
DEVICE = "sentinel-sim-py"

temperature, humidity, gas_raw = 24.0, 45.0, 1500.0
pir = False
remote_buzzer = remote_red = False
state = "NORMAL"
seq, start = 0, time.time()
anomaly_steps = 0

def compute_state():
    # Même logique que le circuit
    gas_index = min(100, max(0, int(gas_raw * 100 / 4095)))
    warning = temperature >= 35 or gas_index >= 45
    danger = temperature >= 40 or gas_index >= 65
    if danger and pir:
        return "CRITIQUE"
    if warning or pir:
        return "SURVEILLANCE"
    return "NORMAL"

def on_message(client, userdata, msg):
    global remote_buzzer, remote_red
    cmd = json.loads(msg.payload)
    if "buzzer" in cmd:
        remote_buzzer = bool(cmd["buzzer"])
    if "led_red" in cmd:
        remote_red = bool(cmd["led_red"])
    if cmd.get("action") == "reset":
        remote_buzzer = remote_red = False
    print(f"📥 Commande reçue : {cmd} -> buzzer={remote_buzzer} led_red={remote_red}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE)
client.on_message = on_message
client.will_set(f"{PREFIX}/status", "offline", qos=1, retain=True)  # testament
client.connect(BROKER, PORT)
client.publish(f"{PREFIX}/status", "online", qos=1, retain=True)
client.subscribe(f"{PREFIX}/command", qos=1)
client.loop_start()

print("Simulateur démarré (Ctrl+C pour arrêter)")
while True:
    if anomaly_steps == 0 and random.random() < 0.03:
        anomaly_steps = 12
        print("⚠️  Simulation d'une fuite de gaz")

    if anomaly_steps > 0:
        gas_raw += random.uniform(120, 220)
        temperature += random.uniform(0.2, 0.5)
        anomaly_steps -= 1
    else:
        gas_raw += (1500 - gas_raw) * 0.2 + random.uniform(-40, 40)
        temperature += (24 - temperature) * 0.1 + random.uniform(-0.2, 0.2)

    humidity += random.uniform(-0.5, 0.5)
    pir = random.random() < 0.05
    gas_raw = min(4095, max(0, gas_raw))

    previous, state = state, compute_state()
    seq += 1
    telemetry = {
        "device": DEVICE,
        "seq": seq,
        "uptime_s": int(time.time() - start),
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
        "gas_raw": int(gas_raw),
        "gas_index": min(100, max(0, int(gas_raw * 100 / 4095))),
        "pir": pir,
        "state": state,
        "rssi": random.randint(-90, -60),
        "heap": 226760,
    }
    client.publish(f"{PREFIX}/telemetry", json.dumps(telemetry))
    print("📤", telemetry)

    if state != previous:
        alert = {"device": DEVICE, "previous": previous, "current": state,
                 "temperature": telemetry["temperature"],
                 "gas_index": telemetry["gas_index"], "pir": pir}
        client.publish(f"{PREFIX}/alert", json.dumps(alert))
        print("🚨", alert)

    time.sleep(2)
