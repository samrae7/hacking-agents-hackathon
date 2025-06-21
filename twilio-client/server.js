const express = require('express');
const { WebSocketServer } = require('ws');
const twilio = require('twilio');
const axios = require('axios');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const VoiceResponse = twilio.twiml.VoiceResponse;

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Webhook endpoint for incoming calls
app.post('/voice', (req, res) => {
    const response = new VoiceResponse();
    const connect = response.connect();
    connect.conversationRelay({
        url: `wss://${req.get('host')}/websocket`,
        welcomeGreeting: 'Hello! I\'m P, the event MC. How can I help you today?',
        language: 'en-US'
    });

    res.type('text/xml');
    res.send(response.toString());
});

// Start HTTP server
const server = app.listen(port, () => {
    console.log(`Server running on port ${port}`);
    console.log(`Webhook URL: http://localhost:${port}/voice`);
});

// Create WebSocket server
const wss = new WebSocketServer({
    server,
    path: '/websocket'
});

// Handle WebSocket connections from ConversationRelay
wss.on('connection', (ws) => {
    console.log('ConversationRelay WebSocket connected');

    ws.on('message', async (data) => {
        try {
            const message = JSON.parse(data.toString());
            console.log('Received message:', JSON.stringify(message, null, 2));

            // Handle different message types from ConversationRelay
            switch (message.type) {
                case 'setup':
                    console.log('ConversationRelay setup completed');
                    break;

                case 'prompt':
                    // This is the transcribed speech from the caller
                    const userText = message.voicePrompt;
                    console.log('User said:', userText);

                    // Send to Langflow agent
                    const agentResponse = await callLangflowAgent(userText);

                    // Send response back to ConversationRelay using the correct format
                    const responseMessage = {
                        type: 'text',
                        token: agentResponse,
                        last: true,
                        interruptible: true
                    };

                    console.log('Sending response:', JSON.stringify(responseMessage));
                    ws.send(JSON.stringify(responseMessage));
                    break;

                case 'interrupt':
                    console.log('User interrupted the response');
                    break;

                default:
                    console.log('Unknown message type:', message.type);
            }
        } catch (error) {
            console.error('Error processing WebSocket message:', error);
        }
    });

    ws.on('close', () => {
        console.log('ConversationRelay WebSocket disconnected');
    });

    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
    });
});

// Function to call your Langflow agent
async function callLangflowAgent(userMessage) {
    try {
        const langflowUrl = process.env.LANGFLOW_URL;
        const apiKey = process.env.LANGFLOW_API_KEY;

        if (!langflowUrl) {
            throw new Error('LANGFLOW_URL not configured');
        }

        const payload = {
            input_value: userMessage,
            output_type: "chat",
            input_type: "chat"
        };

        const headers = {
            'Content-Type': 'application/json'
        };

        if (apiKey) {
            headers['Authorization'] = `Bearer ${apiKey}`;
        }

        console.log('Calling Langflow agent with:', userMessage);
        const response = await axios.post(langflowUrl, payload, { headers });

        // Extract the response text from Langflow response
        const agentResponse = response.data?.outputs?.[0]?.outputs?.[0]?.results?.message?.text ||
            response.data?.message ||
            "I'm sorry, I didn't understand that. Could you please try again?";

        console.log('Langflow agent response:', agentResponse);
        return agentResponse;

    } catch (error) {
        console.error('Error calling Langflow agent:', error);
        return "I'm sorry, I'm having trouble processing your request right now. Please try again later.";
    }
}

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully');
    server.close(() => {
        console.log('Server closed');
        process.exit(0);
    });
});