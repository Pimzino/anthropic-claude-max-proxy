# Anthropic Claude Max Proxy

Pure Anthropic proxy for Claude Pro/Max subscriptions using OAuth.

## SUPPORT MY WORK
<a href="https://buymeacoffee.com/Pimzino" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## DISCLAIMER

**FOR EDUCATIONAL PURPOSES ONLY**

This tool:
- Is NOT affiliated with or endorsed by Anthropic
- Uses undocumented OAuth flows from Claude Code
- May violate Anthropic's Terms of Service
- Could stop working at any time without notice
- Comes with NO WARRANTY or support

**USE AT YOUR OWN RISK. The authors assume no liability for any consequences.**

For official access, use Claude Code or Anthropic's API with console API keys.

## Prerequisites

- Active Claude Pro or Claude Max subscription
- **Option 1: Traditional Setup**
  - Python 3.8+
  - pip
- **Option 2: Docker Setup**
  - Docker installed and running

## Quick Start

### Option 1: Docker Setup

**One-command setup and run:**
```bash
./run-docker.sh
# Or specify custom port:
./run-docker.sh 8082
```

This will automatically:
- Build the Docker image
- Create persistent volume for authentication tokens
- Guide you through the OAuth authentication
- Start the proxy server in background

**Features:**
- Automatic token refresh if container is already running
- Persistent authentication across container restarts
- Port conflict detection and automatic resolution
- Clean container lifecycle management

### Option 2: Traditional Python Setup

1. **Virtual Environment Setup**
```bash
python -m venv venv
```

2. **Install:**
```bash
venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

3. **Configure (optional):**
```bash
cp config.example.json config.json
```

4. **Run:**
```bash
python cli.py
# Or with custom bind address:
python cli.py --bind 127.0.0.1
```

5. **Authenticate:**
- Select option 2 (Login)
- Browser opens automatically
- Complete login at claude.ai
- Copy the authorization code
- Paste in terminal

6. **Start proxy:**
- Select option 1 (Start Proxy Server)
- Server runs at `http://0.0.0.0:8081` (default, listens on all interfaces)

## Docker Management Commands

When using Docker setup:

**Check container status:**
```bash
docker ps -f name=claude-proxy-server
```

**View logs:**
```bash
docker logs claude-proxy-server -f
```

**Stop the server:**
```bash
docker stop claude-proxy-server
```

**Remove container:**
```bash
docker rm claude-proxy-server
```

**Re-run to refresh authentication:**
```bash
./run-docker.sh
```

## Client Configuration

Configure your Anthropic API client:

- **Base URL:** `http://<proxy-host>:8081` (default: `http://0.0.0.0:8081`)
- **API Key:** Any non-empty string (e.g., "dummy")
- **Model:** `claude-sonnet-4-20250514` (or any available Claude model)
- **Endpoint:** `/v1/messages`

## Available Models

- Supports all Anthropic Models that you have access to with your Claude Pro / Max subscription.

## Tested & Supported features

- Browser use
- Images

these are features that are not available or not user friendly in CC.

## Docker Architecture

The Docker setup uses:
- **Persistent Volume:** `claude-tokens` - Stores authentication tokens across container restarts
- **Container Name:** `claude-proxy-server` - Fixed name for easy management
- **Automatic Restart:** `unless-stopped` policy ensures service continuity
- **Smart Authentication:** Only re-authenticates when tokens expire
- **Port Management:** Automatic port conflict resolution for default port

## Configuration Priority

1. Environment variables (highest)
2. config.json file
3. Built-in defaults (lowest)

## License

MIT License - see [LICENSE](LICENSE) file

This software is provided for educational purposes only. Users assume all risks.
