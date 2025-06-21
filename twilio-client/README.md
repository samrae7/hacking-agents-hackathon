# Twilio Voice App with ConversationRelay and Langflow

A voice application that receives calls through Twilio, converts speech to text using ConversationRelay, processes the text with a Langflow agent, and responds back to the caller with text-to-speech.

## Features

- **Incoming Call Handling**: Receives voice calls via Twilio webhooks
- **Speech-to-Text**: Uses Twilio ConversationRelay for real-time speech transcription
- **AI Agent Integration**: Sends transcribed text to your Langflow agent
- **Text-to-Speech**: Converts AI responses back to speech for the caller
- **WebSocket Communication**: Real-time bidirectional communication with ConversationRelay

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your configuration:
   - `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
   - `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
   - `TWILIO_PHONE_NUMBER`: Your Twilio phone number
   - `LANGFLOW_URL`: Your Langflow agent endpoint
   - `LANGFLOW_API_KEY`: Your Langflow API key (if required)
   - `PORT`: Server port (default: 3000)

3. **Start the server**:
   ```bash
   npm run dev
   ```

## Development Setup

1. **Expose your local server** using ngrok:
   ```bash
   ngrok http 3000
   ```

2. **Configure Twilio webhook**:
   - Go to your Twilio Console
   - Navigate to Phone Numbers > Manage > Active numbers
   - Select your phone number
   - Set the webhook URL to: `https://your-ngrok-url.ngrok.io/voice`
   - Set HTTP method to POST

## How it Works

1. **Incoming Call**: When someone calls your Twilio number, Twilio sends a webhook to `/voice`
2. **ConversationRelay Setup**: The webhook responds with TwiML that connects the call to ConversationRelay
3. **WebSocket Connection**: ConversationRelay establishes a WebSocket connection to `/websocket`
4. **Speech Processing**: 
   - User speaks → ConversationRelay converts to text
   - Text sent to your Langflow agent via HTTP
   - Agent response sent back to ConversationRelay
   - ConversationRelay converts response to speech for the caller

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /voice` - Twilio webhook for incoming calls
- `WS /websocket` - WebSocket endpoint for ConversationRelay

## Langflow Integration

The app expects your Langflow agent to:
- Accept HTTP POST requests
- Process the `input_value` field containing the user's message
- Return a response in the format your agent provides

Modify the `callLangflowAgent` function in `server.js` to match your specific Langflow agent's API format.

## Testing

Call your Twilio phone number and speak to test the full flow:
1. The app will greet you
2. Speak your message
3. The app will process it through your Langflow agent
4. You'll hear the AI response

## Troubleshooting

- Check that your ngrok URL is correctly configured in Twilio
- Ensure your Langflow agent is running and accessible
- Monitor the console logs for WebSocket connection status
- Verify environment variables are correctly set