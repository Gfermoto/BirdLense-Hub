# BirdLense Application

## x86 / Docker (Go2RTC)

BirdLense runs on x86 with video from Go2RTC (no RPi hardware required).

### Запуск

```bash
cd BirdLense/app
make build && make start

# С Go2RTC в составе (профиль hybrid):
docker compose -f docker-compose.base.yml -f docker-compose.prod.yml -f docker-compose.go2rtc.yml --profile hybrid up -d

# Без Go2RTC (minimal): укажите GO2RTC_URL в .env на внешний инстанс
```

### Конфигурация

- `app_config/user_config.yaml` или env
- Примеры: `cp configs/minimal.yaml app_config/user_config.yaml`
- **Профили конфигов:** `configs/minimal.yaml`, `configs/full.yaml`, `configs/frigate-only.yaml`

### Режимы конфигов

```bash
cp configs/minimal.yaml app_config/user_config.yaml   # OpenCV, одна камера
cp configs/full.yaml app_config/user_config.yaml     # MQTT, несколько камер, HA
cp configs/frigate-only.yaml app_config/user_config.yaml  # только Frigate
```

### Разработка

```bash
# Без MQTT брокера (fake motion):
python src/main.py --mock-mqtt
```

### Live

`http://localhost/processor/live` — все камеры на одной странице.

---

## Raspberry Pi Setup

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS Lite (64-bit)**:

- Set hostname: `birdlense`
- Enable SSH with password or key
- Configure WiFi and timezone

## Quick Start

1. **SSH into Raspberry Pi**

   ```bash
   ssh user@birdlense.local
   ```

2. **Clone and install:**

   ```bash
   sudo apt install git && git clone https://github.com/Gfermoto/BirdLense-Hub
   cd BirdLense/app
   chmod +x install.sh && ./install.sh
   ```

   Restart terminal session to apply permission changes.

3. **Start the application:**

   ```bash
   cd BirdLense/app
   make start
   ```

   Web interface available at `http://birdlense.local`. View logs with `make logs`.

## Configuration

Visit the **Settings** page first to configure your location (ZIP code) and OpenWeather API key.

## Notifications

Local notifications via bundled ntfy server (nothing shared outside your network):

1. Install ntfy app: [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) | [iOS](https://apps.apple.com/app/ntfy/id1625396347)
2. Add server: `http://birdlense.local:8081`, channel: `birdlense`

## Development

### Docker Commands

```bash
make build-dev    # Build development containers
make start-dev    # Start development mode
make stop-dev     # Stop containers
make logs         # View logs
```

### Project Structure

```
app/
├── app_config/     # YAML configuration files
├── data/           # Recordings, samples
├── processor/      # Video/audio processing (Python)
├── web/            # Flask API backend
├── ui/             # React frontend (Vite + MUI)
└── nginx/          # Reverse proxy configuration
```

## Architecture

### x86 / Docker (Go2RTC + MQTT)

```mermaid
flowchart TB
    subgraph External["Внешние сервисы"]
        GO2RTC[Go2RTC]
        MQTT[MQTT Broker]
        FRIGATE[Frigate]
        BIRDNET_MQTT[BirdNET]
        HA[Home Assistant]
    end

    subgraph BirdLense["BirdLense"]
        subgraph processor[Processor]
            SOURCE[Go2RTCStreamSource]
            MOTION[Motion: MQTT / OpenCV]
            YOLO[YOLO + ByteTrack]
            MERGE[Merge YOLO+Frigate+BirdNET]
            AUDIO[BirdNET Audio]
        end

        subgraph web[Web]
            API[Flask API]
            DB[(SQLite)]
        end

        UI[React UI]
        NGINX[Nginx]
    end

    GO2RTC -->|RTSP| SOURCE
    FRIGATE -->|frigate/events| MQTT
    BIRDNET_MQTT -->|birdnet/sightings| MQTT
    MQTT -->|trigger| MOTION
    processor -->|birdlense/detections| MQTT
    MQTT --> HA

    SOURCE --> MOTION
    MOTION --> YOLO
    YOLO --> MERGE
    MERGE --> API
    API --> DB
    UI --> NGINX
    NGINX --> API
    NGINX -->|MJPEG| processor
```

### Raspberry Pi (legacy)

```mermaid
flowchart TB
    subgraph Hardware
        CAM[Pi Camera]
        MIC[USB Microphone]
        PIR[PIR Sensor]
    end

    subgraph Docker["Docker Containers"]
        subgraph processor[Processor]
            YOLO[YOLO Detection]
            TRACK[ByteTrack]
            BIRDNET[BirdNET Audio]
        end

        subgraph web[Web API]
            API[Flask]
            DB[(SQLite)]
        end

        UI[React UI]
        NGINX[Nginx]
        NTFY[Ntfy]
    end

    CAM --> processor
    MIC --> processor
    PIR --> processor
    processor -- Detections --> web
    processor -- Stream --> NGINX
    UI --> NGINX
    NGINX --> web
    NGINX --> processor
```

## Components

| Container     | Purpose                                                                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Processor** | Captures video, runs YOLO detection with ByteTrack tracking, processes audio with BirdNET |
| **Web**       | Flask API, SQLite database, visit analytics |
| **UI**        | React + Material UI, video playback with track overlays, timeline, species stats                                               |
| **Nginx**     | Reverse proxy, static file serving, MJPEG stream routing                                                                       |
| **Ntfy**      | Local push notifications                                                                                                       |

## Detection Pipeline

1. **Motion trigger** → PIR sensor or continuous mode
2. **Binary detection** → Fast YOLO model detects any bird
3. **Object tracking** → ByteTrack assigns stable IDs across frames
4. **Species classification** → Classifier model identifies species
5. **Blur filtering** → Rejects blurry frames for classification
6. **Audio processing** → BirdNET identifies species from audio

## MCP Integration

For AI agent integration (e.g., Claude Desktop):

1. Download `web/birdlense_mcp.py`
2. Reference in your `claude_desktop_config.json`
3. See [MCP docs](https://modelcontextprotocol.io/quickstart/server)

## FAQ

**Camera not recognized?**

Adjust `/boot/firmware/config.txt`. Example for PiCam v2 on Pi 5:

```
dtoverlay=imx219,cam0
camera_auto_detect=0
```

Then reboot.

## Hardware Wiring (Raspberry Pi 4B)

### PIR Motion Sensor

| PIR Pin | Pi Pin         | Description |
| ------- | -------------- | ----------- |
| VCC     | Pin 2          | 5V Power    |
| OUT     | Pin 7 (GPIO 4) | Signal      |
| GND     | Pin 6          | Ground      |

### Cooling Fan

Connect directly to 5V power for continuous cooling:

| Fan Wire  | Pi Pin | Description |
| --------- | ------ | ----------- |
| Red (+)   | Pin 4  | 5V Power    |
| Black (-) | Pin 6  | Ground      |

> [!TIP]
> Small fans draw minimal power (~0.1W) and continuous cooling improves Pi longevity during 24/7 operation.
