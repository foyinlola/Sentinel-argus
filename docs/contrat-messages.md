# Contrat des messages Sentinel-X

## Topics MQTT
- Mesures (circuit -> serveur) : sentinel/G<n>/telemetry
- Commandes (serveur -> circuit) : sentinel/G<n>/command

## Message mesures (toutes les 2 s)
{"device_id":"SX-001","ts":1760000000,"temperature":24.5,"humidity":48,"gas":310,"motion":false}

## Message commande
{"actuator":"buzzer","state":"on"}

## Alerte API
POST /api/v1/alerts
{"device_id":"SX-001","type":"gas_anomaly","level":"critical","ts":1760000000}

Règle : personne ne change un nom sans prévenir le groupe.
