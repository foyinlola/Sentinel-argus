# Contrat des messages Sentinel-X (Groupe 1)

Broker de test : broker.hivemq.com:1883 (public, aucun secret)
Broker final : Mosquitto du serveur (TLS, port 8883)

## Topics
| Topic                 | Publié par | Contenu                          |
|-----------------------|------------|----------------------------------|
| sentinel/G1/telemetry | Circuit    | Mesures toutes les 2 s           |
| sentinel/G1/status    | Circuit    | "online" / "offline" (retain)    |
| sentinel/G1/alert     | Circuit    | Changement d'état du boîtier     |
| sentinel/G1/command   | Dashboard  | Ordres buzzer / LED rouge        |

## telemetry
{"device":"sentinel-sim-01","seq":14,"uptime_s":32,"temperature":24.0,"humidity":45.0,
 "gas_raw":1563,"gas_index":38,"pir":false,"state":"NORMAL","rssi":-84,"heap":226760}

Valeurs de state : NORMAL, SURVEILLANCE, CRITIQUE
L'heure est ajoutée par le serveur à la réception (pas d'horloge sur l'ESP).

## status
"online" à la connexion, "offline" publié automatiquement (testament) si le circuit se coupe.

## alert
{"device":"sentinel-sim-01","previous":"NORMAL","current":"SURVEILLANCE",
 "temperature":36.2,"gas_index":47,"pir":false}

## command
{"buzzer": true}      allume le buzzer   ({"buzzer": false} pour l'éteindre)
{"led_red": true}     allume la LED rouge
{"action": "reset"}   éteint buzzer et LED rouge
Note : en état CRITIQUE, le buzzer reste forcé par le circuit.

Règle : personne ne change un nom sans prévenir le groupe.
