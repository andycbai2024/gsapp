⚙️ English | [中文](./README.md)

<div align="center">
  <img src="./frontend/assets/logo.svg" width="56px"/>
  <h1>Management Platform</h1>
</div>

A minimalist and lightweight video streaming management platform — out of the box and easy to extend.

> This management platform is built on [ZLMediaKit](https://github.com/ZLMediaKit/ZLMediaKit) and [Layui](https://github.com/layui/layui). The overall design uses blue-green (`#16baaa`) as the primary color and follows the principles of “simple, easy to use, and extensible”. We continuously balance code complexity and feature implementation, and keep pursuing the beauty of minimalism.

### Features

✅ Supports pull-proxy ingestion and saving for mainstream protocols such as RTSP/RTMP/HLS/WebRTC/RTP/GB28181.

✅ Supports push ingestion for protocols such as RTSP/RTMP/RTP.

✅ Supports stream distribution via RTSP/WebRTC/RTMP/FLV/HLS/HLS-fMP4/HTTP-TS/HTTP-fMP4 and more.

✅ Supports 1x1, 2x2, 3x3 multi-screen playback.

✅ Supports local recording, playback, download, automatic cleanup, and more.

This platform focuses on stream management. It currently does not support ONVIF/GB28181 device discovery, stream ingestion, or PTZ control.

### Quick Start

This project is recommended to be deployed with Docker Compose.

```shell
cd ./docker
docker compose up -d
```

After it starts, open `http://{your server IP}` in your browser and log in to the management platform.

The default password is `123456`. You can change it in [login.html](./frontend/login.html).

### Tips

After the first startup, it’s recommended to go to the [Basic Settings] page first and adjust the configuration as needed.

- Consider enabling on-demand forwarding: saves bandwidth, but the first viewer may need to wait for the forwarded stream to start.
- Consider disabling protocols you don’t need to forward. For example, if you don’t need RTMP distribution, disable RTMP forwarding.
- Consider enabling faststart: allows fast seeking during playback, but consumes a bit more storage during recording.
- Consider increasing the GOP cache: smoother playback and longer event video backtracking time, but increases memory usage.

For more options, refer to ZLMediaKit [configuration](https://github.com/ZLMediaKit/ZLMediaKit/tree/master/conf).

### Snapshots

<table>
    <tr>
        <td ><center><img src="assets/login.png" >Login</center></td>
        <td ><center><img src="assets/home.png" >Home</center></td>
    </tr>
    <tr>
        <td ><center><img src="assets/pull-stream.png" >Pull Stream</center></td>
        <td ><center><img src="assets/video-wall.png" >Video Wall</center></td>
    </tr>
</table>

### Architecture

This management platform is designed for minimal implementation. The frontend does not use heavy frameworks such as Vue or React, and the backend avoids complex Java Spring ecosystems, choosing a lightweight combination of Layui and FastAPI. The overall architecture is clean and easy to understand for secondary development.

Project structure:

```bash
├── backend
│   ├── db  # Database
│   ├── main.py  # APIs
│   ├── scheduler.py  # Scheduled jobs
│   └── utils.py  # Utilities
│
├── frontend
│   ├── assets  # Static assets
│   ├── index.html  # Main page
│   ├── login.html  # Login page
│   └── pages
│       ├── home.html  # Overview
│       ├── playback.html  # Playback
│       ├── pull-stream.html  # Pull stream
│       ├── settings.html  # Basic settings
│       ├── push-stream.html  # Push stream
│       └── wall.html  # Video wall
```

Architecture diagram:

<p style="margin: 10px 0px" align="center">
  <img src="assets/arch.png" alt="framework" style="width: 40%" />
</p>

You can add new features or modify existing ones based on this platform, such as ONVIF/GB28181 device discovery, stream ingestion, PTZ control, etc.

### Thanks

- [ZLMediaKit](https://github.com/ZLMediaKit/ZLMediaKit)
- [Layui](https://github.com/layui/layui)
- [FastAPI](https://fastapi.tiangolo.com/)

🥰 Our project is now recommended by https://github.com/ZLMediaKit/ZLMediaKit

### License

This platform is licensed under the [MIT License](./LICENSE)
