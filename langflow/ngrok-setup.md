# Ngrok Setup for Event Web Server (Free Plan)

This guide shows how to expose your Flask event web server via ngrok using the free plan's multi-tunnel configuration.

## Current Setup
- **Existing service**: Port 3000 
- **New Flask server**: Port 5001
- **Ngrok Free Plan**: Limited to 1 agent session (multiple tunnels from single session)

## Step-by-Step Setup

### 1. Configuration Complete ✅
Your ngrok config has been updated to support both tunnels:
```yaml
tunnels:
  existing-service:
    addr: 3000
    proto: http
  event-api:
    addr: 5001
    proto: http
```

### 2. Start the Flask Server
```bash
python webServer.py
```
The server will start on `http://localhost:5001`

### 3. Stop Current Ngrok Session
In the terminal running ngrok, press `Ctrl+C` to stop the current session.

### 4. Start Both Tunnels from Single Session
```bash
ngrok start --all
```

This will start both tunnels in a single ngrok session (free plan compatible).

### 3. Get Your Public URL
After running the command above, you'll see output like:
```
ngrok                                                                           

Session Status    online                                                         
Account           your-account@example.com                              
Version           3.x.x                                                          
Region            Europe (eu)                                                    
Latency           20ms                                                           
Web Interface     http://127.0.0.1:4040                                         
Forwarding        https://abcd-1234-5678.ngrok-free.app -> http://localhost:5001

Connections       ttl     opn     rt1     rt5     p50     p90                   
                  0       0       0.00    0.00    0.00    0.00   
```

Your Flask API will be available at: `https://abcd-1234-5678.ngrok-free.app`

### 4. Test Your API
Try these endpoints with your new ngrok URL:
```bash
# API documentation
curl https://your-ngrok-url.ngrok-free.app/

# Get all event data
curl https://your-ngrok-url.ngrok-free.app/api/event

# Get just the schedule
curl https://your-ngrok-url.ngrok-free.app/api/schedule

# Get attendees
curl https://your-ngrok-url.ngrok-free.app/api/attendees
```

## Multiple Tunnels Management

### Check All Active Tunnels
Visit: `http://localhost:4040` in your browser to see the ngrok web interface showing both tunnels.

Or use the API:
```bash
curl http://localhost:4040/api/tunnels | python3 -m json.tool
```

### Your Running Services
- **Port 3000**: Your existing service → `https://c6b0-2a02-8012-902f-0-ec3b-b2d6-ffa6-cfe6.ngrok-free.app`
- **Port 5001**: Flask Event API → `https://your-new-url.ngrok-free.app`

## Alternative: Named Tunnels (Advanced)

If you want more control, you can create named tunnels using an ngrok config file:

### 1. Create/Edit ngrok config
```bash
ngrok config edit
```

### 2. Add tunnel configurations
```yaml
version: "2"
authtoken: your-auth-token

tunnels:
  existing-service:
    addr: 3000
    proto: http
  event-api:
    addr: 5001
    proto: http
```

### 3. Start both tunnels
```bash
ngrok start existing-service event-api
```

## Important Notes
- Each ngrok tunnel runs in its own terminal/process
- Free ngrok accounts have limits on concurrent tunnels
- Both tunnels will show in the web interface at `http://localhost:4040`
- Your existing tunnel will continue running unaffected

## Stopping Tunnels
- To stop the new tunnel: Press `Ctrl+C` in the terminal running `ngrok http 5001`
- Your existing tunnel on port 3000 will continue running
- To stop the Flask server: Press `Ctrl+C` in the terminal running `python webServer.py`