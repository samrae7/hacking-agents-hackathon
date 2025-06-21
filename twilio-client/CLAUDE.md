# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Node.js voice application that integrates Twilio Voice API with ConversationRelay for speech-to-text processing and connects to a Langflow agent for AI responses. The app handles incoming calls, processes speech, and responds with AI-generated text-to-speech.

## Development Commands

- `npm install` - Install project dependencies
- `npm start` - Start the production server
- `npm run dev` - Start development server with nodemon
- `ngrok http 3000` - Expose local server for Twilio webhooks (development)

## Architecture

**Core Components:**
- **Express Server** (`server.js`): HTTP server handling Twilio webhooks and WebSocket connections
- **Twilio Integration**: Handles incoming voice calls via TwiML and ConversationRelay
- **WebSocket Server**: Real-time communication with Twilio ConversationRelay
- **Langflow Integration**: HTTP client for AI agent communication

**Data Flow:**
1. Incoming call → Twilio webhook (`/voice`) → TwiML with ConversationRelay
2. ConversationRelay → WebSocket connection → Speech-to-text processing
3. Transcribed text → Langflow agent (HTTP POST) → AI response
4. AI response → ConversationRelay → Text-to-speech → Caller

**Key Files:**
- `server.js` - Main application server with WebSocket and HTTP endpoints
- `.env` - Environment configuration (Twilio credentials, Langflow URL)
- `package.json` - Dependencies: express, twilio, ws, axios, dotenv

## Configuration Requirements

**Environment Variables:**
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - Twilio credentials
- `LANGFLOW_URL` - Langflow agent endpoint
- `LANGFLOW_API_KEY` - Optional Langflow authentication
- `PORT` - Server port (default: 3000)

**Twilio Setup:**
- Phone number webhook URL: `https://your-domain.com/voice` (POST)
- ConversationRelay requires secure WebSocket (`wss://`) connections

## Development Notes

- Use ngrok for local development to expose webhooks
- ConversationRelay WebSocket path: `/websocket`
- Langflow integration expects specific payload format - modify `callLangflowAgent()` as needed
- All WebSocket communication with ConversationRelay uses JSON messages