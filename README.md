<p align="center">
  <img src="app/ui/public/logo.png" width="200" alt="BirdLense Logo">
</p>

# Bird Lense

A Raspberry Pi-powered smart bird feeder that uses computer vision and audio recognition to detect, identify, record, and analyze birds. Built with Python, React, and runs entirely on local network using Docker.

<details>
<summary>📷 Photos (click to expand)</summary>
<br>
<p align="center">
  <img src="https://github.com/user-attachments/assets/1b166d35-d42d-44de-bc27-63c8b1483c1b" width="600" alt="Bird Feeder Setup">
</p>
<p align="center">
  <img src="screenshots/dashboard1.jpg" width="800" alt="Dashboard Overview">
</p>
<p align="center">
  <img src="screenshots/dashboard2.jpg" width="800" alt="Activity Charts">
</p>
<p align="center">
  <img src="screenshots/video-details.jpg" width="800" alt="Video Details">
</p>
</details>

## Features

- 🎥 Live video streaming with real-time detection overlays
- 🦜 Bird detection using custom-trained YOLO with ByteTrack object tracking
- 🔬 Two-stage detection: binary bird detector + species classifier
- 🎤 Bird sound identification using [BirdNET](https://github.com/kahst/BirdNET-Analyzer)
- 🤖 Optional LLM verification (Google Gemini) to validate low-confidence detections
- 📊 Species visit tracking with statistics and daily AI summaries
- 📅 Timeline view with video playback and track visualization
- 📱 Modern Material UI mobile-friendly web interface
- 🌡️ Weather integration with hourly temperature correlation
- 🔔 Local push notifications via [ntfy](https://ntfy.sh)
- 🔌 MCP (Model Context Protocol) support for AI agent integrations
- 🚫 No cloud dependencies, runs completely local
- 🖨️ Custom 3D printing models for enclosure and feeder

## Sections

- [Application](./app) - Raspberry Pi software
- [3D Printing](./3d_printing) - Printable enclosure and feeder models

## Prerequisites

- Raspberry Pi 4B or 5 with a minimum of 4GB RAM
- High-capacity microSD card (128 GB+ recommended)
- Raspberry Pi Camera Module
- USB Microphone
- [Optional] PIR motion sensor for wake-on-motion
- [Optional] 3D printer for custom enclosure

## Getting Started

**Quick start (Docker):**
```bash
git clone https://github.com/Gfermoto/BirdLense-Hub.git
cd BirdLense-Hub/app
make pull
```
UI: http://localhost:8085

Подробнее: [Application README](./app/README.md)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) for object detection
- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer) for audio identification
- [NABirds](https://dl.allaboutbirds.org/nabirds) dataset for model training
- [Material-UI](https://mui.com/) for UI components
- [OpenWeatherMap](https://openweathermap.org/) for weather data
