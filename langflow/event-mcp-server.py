#!/usr/bin/env python3
"""
eMCeeP Event Management MCP Server

This MCP server provides event management tools for Langflow integration:
- Event data retrieval and updates
- Intent classification for voice commands
- Schedule management with changelog tracking
- Notification capabilities
- SMS messaging via Twilio

Usage:
    python event_mcp_server.py

Then in Langflow, you can connect to this MCP server to access event management tools.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel import NotificationOptions
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    CallToolRequest,
    CallToolResult,
    ListResourcesRequest,
    ListResourcesResult,
    ListToolsRequest,
    ListToolsResult,
    ReadResourceRequest,
    ReadResourceResult,
)
from pydantic import AnyUrl
import mcp.server.stdio

# Twilio imports for SMS functionality
try:
    from twilio.rest import Client

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("emceep-mcp-server")

# Log Twilio availability after logger is defined
if not TWILIO_AVAILABLE:
    logger.warning("Twilio not available. SMS functionality will be disabled.")


class EventManager:
    """Handles event data management operations"""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.event_data = {}
        self.load_event_data()

    def load_event_data(self) -> Dict:
        """Load event data from JSON file"""
        try:
            with open(self.data_path, "r") as f:
                self.event_data = json.load(f)
            logger.info(f"Loaded event data from {self.data_path}")
            return self.event_data
        except FileNotFoundError:
            logger.error(f"Event data file not found: {self.data_path}")
            self.event_data = {}
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in event data file: {e}")
            self.event_data = {}
            return {}

    def save_event_data(self) -> bool:
        """Save event data back to JSON file"""
        try:
            with open(self.data_path, "w") as f:
                json.dump(self.event_data, f, indent=2)
            logger.info(f"Saved event data to {self.data_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save event data: {e}")
            return False

    def find_schedule_item(self, identifier: str) -> Optional[Dict]:
        """Find a schedule item by ID or title"""
        for item in self.event_data.get("schedule", []):
            if (
                item.get("id", "").lower() == identifier.lower()
                or identifier.lower() in item.get("title", "").lower()
            ):
                return item
        return None

    def update_schedule_time(
        self, item_id: str, new_time: str, new_end_time: Optional[str] = None
    ) -> bool:
        """Update schedule item time"""
        item = self.find_schedule_item(item_id)
        if not item:
            return False

        old_time = item.get("time")
        item["time"] = new_time
        if new_end_time:
            item["end_time"] = new_end_time

        # Add to changelog
        self.add_changelog_entry(
            {
                "type": "time_change",
                "description": f"Moved {item.get('title')} from {old_time} to {new_time}",
                "timestamp": datetime.now().isoformat(),
                "old_value": old_time,
                "new_value": new_time,
                "item_id": item.get("id"),
            }
        )

        return True

    def update_schedule_location(self, item_id: str, new_location: str) -> bool:
        """Update schedule item location"""
        item = self.find_schedule_item(item_id)
        if not item:
            return False

        old_location = item.get("location")
        item["location"] = new_location

        # Add to changelog
        self.add_changelog_entry(
            {
                "type": "location_change",
                "description": f"Moved {item.get('title')} to {new_location}",
                "timestamp": datetime.now().isoformat(),
                "old_value": old_location,
                "new_value": new_location,
                "item_id": item.get("id"),
            }
        )

        return True

    def add_changelog_entry(self, entry: Dict):
        """Add entry to changelog"""
        if "changelog" not in self.event_data:
            self.event_data["changelog"] = []

        entry["timestamp"] = datetime.now().isoformat()
        self.event_data["changelog"].append(entry)

    def update_faq(self, key: str, value: str) -> bool:
        """Update or add FAQ entry"""
        try:
            if "faq" not in self.event_data:
                self.event_data["faq"] = {}

            old_value = self.event_data["faq"].get(key)
            self.event_data["faq"][key] = value

            # Log the change
            if old_value:
                self.add_changelog_entry(
                    {
                        "action": "update_faq",
                        "key": key,
                        "old_value": old_value,
                        "new_value": value,
                    }
                )
            else:
                self.add_changelog_entry(
                    {"action": "add_faq", "key": key, "value": value}
                )

            return True
        except Exception as e:
            logger.error(f"Error updating FAQ: {e}")
            return False

    def update_organizer(self, field: str, value: str) -> bool:
        """Update organizer information"""
        try:
            if "organizer" not in self.event_data:
                self.event_data["organizer"] = {}

            old_value = self.event_data["organizer"].get(field)
            self.event_data["organizer"][field] = value

            self.add_changelog_entry(
                {
                    "action": "update_organizer",
                    "field": field,
                    "old_value": old_value,
                    "new_value": value,
                }
            )

            return True
        except Exception as e:
            logger.error(f"Error updating organizer: {e}")
            return False

    def add_schedule_item(
        self,
        title: str,
        time: str,
        end_time: str,
        location: str,
        description: Optional[str] = None,
        speaker: Optional[str] = None,
    ) -> bool:
        """Add a new schedule item"""
        try:
            if "schedule" not in self.event_data:
                self.event_data["schedule"] = []

            new_item = {
                "id": f"item_{len(self.event_data['schedule']) + 1}",
                "title": title,
                "time": time,
                "end_time": end_time,
                "location": location,
            }

            if description:
                new_item["description"] = description
            if speaker:
                new_item["speaker"] = speaker

            self.event_data["schedule"].append(new_item)

            self.add_changelog_entry({"action": "add_schedule_item", "item": new_item})

            return True
        except Exception as e:
            logger.error(f"Error adding schedule item: {e}")
            return False

    def remove_schedule_item(self, identifier: str) -> bool:
        """Remove a schedule item"""
        try:
            item = self.find_schedule_item(identifier)
            if not item:
                return False

            self.event_data["schedule"].remove(item)

            self.add_changelog_entry(
                {"action": "remove_schedule_item", "removed_item": item}
            )

            return True
        except Exception as e:
            logger.error(f"Error removing schedule item: {e}")
            return False

    def update_event_details(self, field: str, value: str) -> bool:
        """Update general event information"""
        try:
            old_value = self.event_data.get(field)
            self.event_data[field] = value

            self.add_changelog_entry(
                {
                    "action": "update_event_details",
                    "field": field,
                    "old_value": old_value,
                    "new_value": value,
                }
            )

            return True
        except Exception as e:
            logger.error(f"Error updating event details: {e}")
            return False

    def add_attendee(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        dietary_restrictions: str = "none",
    ) -> bool:
        """Add a new attendee to the event"""
        try:
            if "attendees" not in self.event_data:
                self.event_data["attendees"] = []

            # Generate new attendee ID
            existing_ids = [att.get("id", "") for att in self.event_data["attendees"]]
            next_id = len(existing_ids) + 1
            while f"att_{next_id:03d}" in existing_ids:
                next_id += 1

            new_attendee = {
                "id": f"att_{next_id:03d}",
                "name": name,
                "dietary_restrictions": dietary_restrictions,
            }

            if email:
                new_attendee["email"] = email
            if phone:
                new_attendee["phone"] = phone
            if company:
                new_attendee["company"] = company

            self.event_data["attendees"].append(new_attendee)

            self.add_changelog_entry(
                {"action": "add_attendee", "attendee": new_attendee}
            )

            return True
        except Exception as e:
            logger.error(f"Error adding attendee: {e}")
            return False

    def find_attendee(self, identifier: str) -> Optional[Dict]:
        """Find attendee by ID, name, email, or phone number"""
        attendees = self.event_data.get("attendees", [])
        identifier_lower = identifier.lower()

        for attendee in attendees:
            if (
                attendee.get("id", "").lower() == identifier_lower
                or attendee.get("name", "").lower() == identifier_lower
                or attendee.get("email", "").lower() == identifier_lower
                or attendee.get("phone", "") == identifier
            ):  # Exact match for phone numbers
                return attendee
        return None

    def find_organizer(self, identifier: str) -> Optional[Dict]:
        """Find organizer by ID, name, email, or phone number"""
        organizers = self.event_data.get("organizers", [])
        identifier_lower = identifier.lower()

        for organizer in organizers:
            if (
                organizer.get("id", "").lower() == identifier_lower
                or organizer.get("name", "").lower() == identifier_lower
                or organizer.get("email", "").lower() == identifier_lower
                or organizer.get("phone", "") == identifier
            ):  # Exact match for phone numbers
                return organizer
        return None

    def find_person(self, identifier: str) -> Optional[Dict]:
        """Find person (attendee or organizer) by ID, name, email, or phone number"""
        # Try to find as attendee first
        person = self.find_attendee(identifier)
        if person:
            person["_type"] = "attendee"
            return person

        # Try to find as organizer
        person = self.find_organizer(identifier)
        if person:
            person["_type"] = "organizer"
            return person

        return None

    def remove_attendee(self, identifier: str) -> bool:
        """Remove an attendee from the event"""
        try:
            attendee = self.find_attendee(identifier)
            if not attendee:
                return False

            self.event_data["attendees"].remove(attendee)

            self.add_changelog_entry(
                {"action": "remove_attendee", "removed_attendee": attendee}
            )

            return True
        except Exception as e:
            logger.error(f"Error removing attendee: {e}")
            return False

    def update_attendee(self, identifier: str, field: str, value: str) -> bool:
        """Update attendee information"""
        try:
            attendee = self.find_attendee(identifier)
            if not attendee:
                return False

            old_value = attendee.get(field)
            attendee[field] = value

            self.add_changelog_entry(
                {
                    "action": "update_attendee",
                    "attendee_id": attendee.get("id"),
                    "field": field,
                    "old_value": old_value,
                    "new_value": value,
                }
            )

            return True
        except Exception as e:
            logger.error(f"Error updating attendee: {e}")
            return False

    def send_sms(self, person_identifier: str, message: str) -> Dict[str, Any]:
        """Send an SMS message to a specific person (attendee or organizer)"""
        if not TWILIO_AVAILABLE:
            return {
                "success": False,
                "message": "Twilio not available. SMS functionality disabled.",
                "error": "twilio_unavailable",
            }

        # Find the person (attendee or organizer)
        person = self.find_person(person_identifier)
        if not person:
            return {
                "success": False,
                "message": f"Person not found: {person_identifier}",
                "error": "person_not_found",
            }

        # Check if person has a phone number
        phone_number = person.get("phone")
        if not phone_number:
            person_type = person.get("_type", "person")
            return {
                "success": False,
                "message": f"No phone number found for {person_type}: {person.get('name', person_identifier)}",
                "error": "no_phone_number",
            }

        try:
            # Load Twilio credentials
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")

            if not account_sid or not auth_token or not twilio_phone:
                return {
                    "success": False,
                    "message": "Twilio credentials not found in environment variables",
                    "error": "missing_credentials",
                }

            # Create Twilio client
            client = Client(account_sid, auth_token)

            # Send SMS
            sms_message = client.messages.create(
                to=phone_number, from_=twilio_phone, body=message
            )

            # Log the successful SMS
            person_type = person.get("_type", "person")
            self.add_changelog_entry(
                {
                    "type": "sms_sent",
                    "description": f"SMS sent to {person_type} {person.get('name', person_identifier)}",
                    "person_id": person.get("id"),
                    "person_name": person.get("name"),
                    "person_type": person_type,
                    "phone_number": phone_number,
                    "message_body": (
                        message[:50] + "..." if len(message) > 50 else message
                    ),
                    "message_sid": sms_message.sid,
                }
            )

            logger.info(
                f"SMS sent to {person_type} {person.get('name')} ({phone_number}) with SID: {sms_message.sid}"
            )

            return {
                "success": True,
                "message": f"SMS sent successfully to {person_type} {person.get('name', person_identifier)}",
                "person_name": person.get("name"),
                "person_type": person_type,
                "phone_number": phone_number,
                "message_sid": sms_message.sid,
            }

        except Exception as e:
            logger.error(
                f"Error sending SMS to {person.get('name', person_identifier)}: {e}"
            )
            return {
                "success": False,
                "message": f"Failed to send SMS: {str(e)}",
                "error": "send_failed",
            }


class IntentClassifier:
    """LLM-based intent classification for voice commands"""

    def __init__(self):
        # Improved intent patterns with better scoring
        self.intent_patterns = {
            "time_change": {
                "keywords": [
                    "move",
                    "change time",
                    "reschedule",
                    "shift",
                    "delay",
                    "earlier",
                    "later",
                    "from",
                    "to",
                ],
                "boost_patterns": [
                    r"from \d+:\d+ to \d+:\d+",
                    r"at \d+:\d+",
                    r"time.*change",
                ],
            },
            "location_change": {
                "keywords": [
                    "move to",
                    "change location",
                    "relocate",
                    "different room",
                    "new venue",
                    "room",
                    "hall",
                ],
                "boost_patterns": [
                    r"to room [a-z]",
                    r"move.*to.*room",
                    r"location.*change",
                ],
            },
            "speaker_change": {
                "keywords": [
                    "replace speaker",
                    "new speaker",
                    "speaker change",
                    "substitute",
                ],
                "boost_patterns": [r"speaker.*change", r"replace.*speaker"],
            },
            "cancel_event": {
                "keywords": ["cancel", "remove", "delete event", "call off"],
                "boost_patterns": [r"cancel.*event", r"cancel.*workshop", r"call off"],
            },
            "add_event": {
                "keywords": ["add", "create", "new event", "schedule"],
                "boost_patterns": [r"add.*event", r"create.*event", r"new.*event"],
            },
            "query_info": {
                "keywords": [
                    "what",
                    "when",
                    "where",
                    "who",
                    "how",
                    "tell me",
                    "info about",
                ],
                "boost_patterns": [
                    r"what.*\?",
                    r"when.*\?",
                    r"where.*\?",
                    r"tell me about",
                ],
            },
        }

    def classify_intent(self, text: str) -> Dict[str, Any]:
        """Classify intent from text using improved pattern matching"""
        text_lower = text.lower()

        # Pattern matching with improved scoring
        intent_scores = {}
        for intent, patterns in self.intent_patterns.items():
            score = 0

            # Base keyword matching
            keyword_matches = sum(
                1 for keyword in patterns["keywords"] if keyword in text_lower
            )
            score += keyword_matches * 0.3

            # Boost patterns (higher weight)
            for boost_pattern in patterns["boost_patterns"]:
                if re.search(boost_pattern, text_lower):
                    score += 0.8

            # Special handling for location change detection
            if intent == "location_change":
                if re.search(r"move.*to\s+room\s+[a-z]", text_lower):
                    score += 1.0
                if "room" in text_lower and "move" in text_lower:
                    score += 0.7

            # Special handling for cancel detection
            if intent == "cancel_event":
                if "cancel" in text_lower:
                    score += 0.8

            if score > 0:
                intent_scores[intent] = score

        if not intent_scores:
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "parameters": {},
                "suggested_action": "Please rephrase your request more clearly",
            }

        # Get the highest scoring intent (fix type issue)
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
        confidence = min(intent_scores[best_intent], 1.0)  # Cap at 1.0

        # Extract parameters based on intent
        parameters = self._extract_parameters(text, best_intent)

        # Generate suggested action
        suggested_action = self._generate_suggested_action(best_intent, parameters)

        return {
            "intent": best_intent,
            "confidence": confidence,
            "parameters": parameters,
            "suggested_action": suggested_action,
        }

    def _extract_parameters(self, text: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from text based on intent"""
        parameters = {}
        text_lower = text.lower()

        if intent == "time_change":
            # Extract time patterns
            time_pattern = r"from (\d{1,2}:?\d{0,2})\s*(?:am|pm)?\s*to (\d{1,2}:?\d{0,2})\s*(?:am|pm)?"
            match = re.search(time_pattern, text_lower)
            if match:
                parameters["old_time"] = match.group(1)
                parameters["new_time"] = match.group(2)

            # Extract event name
            event_keywords = [
                "keynote",
                "lunch",
                "panel",
                "workshop",
                "registration",
                "coffee",
                "break",
            ]
            for keyword in event_keywords:
                if keyword in text_lower:
                    parameters["event_name"] = keyword
                    break

        elif intent == "location_change":
            # Extract location patterns - improved to handle "Room B" format
            location_patterns = [
                r"to (room [a-z])",
                r"to (.+?)(?:\s+due to|\s+because|\s*$)",
            ]

            for pattern in location_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    parameters["new_location"] = match.group(1).strip()
                    break

            # Also extract event name for location changes
            event_keywords = [
                "keynote",
                "lunch",
                "panel",
                "workshop",
                "registration",
                "coffee",
                "break",
            ]
            for keyword in event_keywords:
                if keyword in text_lower:
                    parameters["event_name"] = keyword
                    break

        elif intent == "query_info":
            # Extract query subjects
            query_keywords = [
                "wifi",
                "password",
                "parking",
                "location",
                "schedule",
                "lunch",
                "time",
            ]
            for keyword in query_keywords:
                if keyword in text_lower:
                    parameters["query_subject"] = keyword
                    break

        return parameters

    def _generate_suggested_action(
        self, intent: str, parameters: Dict[str, Any]
    ) -> str:
        """Generate suggested action based on intent and parameters"""
        if intent == "time_change":
            event_name = parameters.get("event_name", "event")
            old_time = parameters.get("old_time", "current time")
            new_time = parameters.get("new_time", "new time")
            return f"Update {event_name} time from {old_time} to {new_time} and notify attendees"

        elif intent == "location_change":
            new_location = parameters.get("new_location", "new location")
            return f"Change event location to {new_location} and notify attendees"

        elif intent == "query_info":
            subject = parameters.get("query_subject", "information")
            return f"Provide {subject} information from event data"

        elif intent == "cancel_event":
            return "Cancel the specified event and notify all attendees"

        else:
            return "Process the request according to the identified intent"


# Initialize components
EVENT_DATA_PATH = Path("data/event.json")
event_manager = EventManager(EVENT_DATA_PATH)
intent_classifier = IntentClassifier()

# Create MCP server
app = Server("emceep-event-manager")


@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available event resources"""
    return [
        Resource(
            uri=AnyUrl("file://event/schedule"),
            name="Event Schedule",
            description="Current event schedule with all sessions",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("file://event/attendees"),
            name="Event Attendees",
            description="List of registered event attendees",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("file://event/faq"),
            name="Event FAQ",
            description="Frequently asked questions and answers",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("file://event/changelog"),
            name="Event Changelog",
            description="History of changes made to the event",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("file://event/full"),
            name="Complete Event Data",
            description="All event information including schedule, attendees, and settings",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """Read event resource data"""
    # Refresh data from file
    event_manager.load_event_data()

    uri_str = str(uri)
    if uri_str == "file://event/schedule":
        return json.dumps(event_manager.event_data.get("schedule", []), indent=2)
    elif uri_str == "file://event/attendees":
        return json.dumps(event_manager.event_data.get("attendees", []), indent=2)
    elif uri_str == "file://event/faq":
        return json.dumps(event_manager.event_data.get("faq", {}), indent=2)
    elif uri_str == "file://event/changelog":
        return json.dumps(event_manager.event_data.get("changelog", []), indent=2)
    elif uri_str == "file://event/full":
        return json.dumps(event_manager.event_data, indent=2)
    else:
        raise ValueError(f"Unknown resource URI: {uri_str}")


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available event management tools"""
    return [
        Tool(
            name="classify_voice_command",
            description="Classify intent from a voice command or text input",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The voice command or text to classify",
                    }
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="update_event_time",
            description="Update the time of a scheduled event",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_identifier": {
                        "type": "string",
                        "description": "Event ID or name to update",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New time in HH:MM format",
                    },
                    "new_end_time": {
                        "type": "string",
                        "description": "New end time in HH:MM format (optional)",
                    },
                },
                "required": ["event_identifier", "new_time"],
            },
        ),
        Tool(
            name="update_event_location",
            description="Update the location of a scheduled event",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_identifier": {
                        "type": "string",
                        "description": "Event ID or name to update",
                    },
                    "new_location": {
                        "type": "string",
                        "description": "New location for the event",
                    },
                },
                "required": ["event_identifier", "new_location"],
            },
        ),
        Tool(
            name="update_faq",
            description="Add or update FAQ entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "FAQ key/category (e.g., 'wifi', 'parking', 'contact')",
                    },
                    "value": {
                        "type": "string",
                        "description": "FAQ answer/information",
                    },
                },
                "required": ["key", "value"],
            },
        ),
        Tool(
            name="update_organizer",
            description="Update organizer information",
            inputSchema={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Field to update (e.g., 'name', 'email', 'phone', 'website')",
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["field", "value"],
            },
        ),
        Tool(
            name="add_schedule_item",
            description="Add a new item to the event schedule",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the event/session",
                    },
                    "time": {
                        "type": "string",
                        "description": "Start time in HH:MM format",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in HH:MM format",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location/room for the event",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the event",
                    },
                    "speaker": {
                        "type": "string",
                        "description": "Optional speaker name",
                    },
                },
                "required": ["title", "time", "end_time", "location"],
            },
        ),
        Tool(
            name="remove_schedule_item",
            description="Remove an item from the event schedule",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_identifier": {
                        "type": "string",
                        "description": "Event ID or name to remove",
                    }
                },
                "required": ["event_identifier"],
            },
        ),
        Tool(
            name="update_event_details",
            description="Update general event information",
            inputSchema={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Field to update (e.g., 'name', 'date', 'venue', 'description')",
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["field", "value"],
            },
        ),
        Tool(
            name="process_voice_command",
            description="Process a complete voice command: classify intent and execute if appropriate",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The complete voice command to process",
                    },
                    "auto_execute": {
                        "type": "boolean",
                        "description": "Whether to automatically execute high-confidence commands",
                        "default": True,
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="get_schedule",
            description="Get the event schedule with all sessions, times, and locations",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_faq",
            description="Get frequently asked questions and answers",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_organizer",
            description="Get organizer contact information and event details (supports multiple organizers)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_organizers",
            description="Get detailed information about all event organizers including names, emails, phone numbers, and roles",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_attendees",
            description="Get attendee information including names, companies, contact details, and DIETARY RESTRICTIONS. Use this when planning food/catering.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_everything",
            description="Get all event data as fallback when specific information isn't available in other tools",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_dietary_requirements",
            description="Get dietary restrictions and food preferences of all attendees for catering/food planning purposes",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="add_attendee",
            description="Add a new attendee to the event registration",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full name of the attendee",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address of the attendee",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Phone number of the attendee (optional)",
                    },
                    "company": {
                        "type": "string",
                        "description": "Company/organization of the attendee (optional)",
                    },
                    "dietary_restrictions": {
                        "type": "string",
                        "description": "Dietary restrictions (e.g., 'vegetarian', 'gluten-free', 'none')",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="remove_attendee",
            description="Remove an attendee from the event registration",
            inputSchema={
                "type": "object",
                "properties": {
                    "attendee_identifier": {
                        "type": "string",
                        "description": "Attendee ID, name, or email to identify the attendee to remove",
                    }
                },
                "required": ["attendee_identifier"],
            },
        ),
        Tool(
            name="update_attendee",
            description="Update attendee information including dietary restrictions",
            inputSchema={
                "type": "object",
                "properties": {
                    "attendee_identifier": {
                        "type": "string",
                        "description": "Attendee ID, name, or email to identify the attendee",
                    },
                    "field": {
                        "type": "string",
                        "description": "Field to update (name, email, phone, company, dietary_restrictions)",
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["attendee_identifier", "field", "value"],
            },
        ),
        Tool(
            name="update_faq",
            description="Update FAQ entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "FAQ key/category (e.g., 'wifi', 'parking', 'contact')",
                    },
                    "value": {
                        "type": "string",
                        "description": "FAQ answer/information",
                    },
                },
                "required": ["key", "value"],
            },
        ),
        Tool(
            name="update_organizer",
            description="Update organizer information",
            inputSchema={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Field to update (e.g., 'name', 'email', 'phone', 'website')",
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["field", "value"],
            },
        ),
        Tool(
            name="add_schedule_item",
            description="Add a new item to the event schedule",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the event/session",
                    },
                    "time": {
                        "type": "string",
                        "description": "Start time in HH:MM format",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in HH:MM format",
                    },
                    "location": {
                        "type": "string",
                        "description": "Location/room for the event",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the event",
                    },
                    "speaker": {
                        "type": "string",
                        "description": "Optional speaker name",
                    },
                },
                "required": ["title", "time", "end_time", "location"],
            },
        ),
        Tool(
            name="remove_schedule_item",
            description="Remove an item from the event schedule",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_identifier": {
                        "type": "string",
                        "description": "Event ID or name to remove",
                    }
                },
                "required": ["event_identifier"],
            },
        ),
        Tool(
            name="update_event_details",
            description="Update general event information",
            inputSchema={
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "Field to update (e.g., 'name', 'date', 'venue', 'description')",
                    },
                    "value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["field", "value"],
            },
        ),
        Tool(
            name="get_changelog",
            description="Get the history of changes made to the event",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent changes to return",
                        "default": 10,
                    }
                },
            },
        ),
        Tool(
            name="send_sms",
            description="Send an SMS message to a specific person (attendee or organizer) using Twilio",
            inputSchema={
                "type": "object",
                "properties": {
                    "person_identifier": {
                        "type": "string",
                        "description": "Person ID, name, email, or phone number to identify the recipient (works for both attendees and organizers)",
                    },
                    "message": {
                        "type": "string",
                        "description": "The SMS message to send to the person",
                    },
                },
                "required": ["person_identifier", "message"],
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution"""

    if name == "classify_voice_command":
        text = arguments.get("text", "")
        result = intent_classifier.classify_intent(text)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_event_time":
        event_id = arguments.get("event_identifier", "")
        new_time = arguments.get("new_time", "")
        new_end_time = arguments.get("new_end_time")

        success = event_manager.update_schedule_time(event_id, new_time, new_end_time)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully updated {event_id} to {new_time}",
                "event_id": event_id,
                "new_time": new_time,
            }
        else:
            result = {
                "success": False,
                "message": f"Could not find event: {event_id}",
                "event_id": event_id,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_event_location":
        event_id = arguments.get("event_identifier", "")
        new_location = arguments.get("new_location", "")

        success = event_manager.update_schedule_location(event_id, new_location)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully moved {event_id} to {new_location}",
                "event_id": event_id,
                "new_location": new_location,
            }
        else:
            result = {
                "success": False,
                "message": f"Could not find event: {event_id}",
                "event_id": event_id,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "process_voice_command":
        command = arguments.get("command", "")
        auto_execute = arguments.get("auto_execute", True)

        # Step 1: Classify intent
        classification = intent_classifier.classify_intent(command)

        # Step 2: Execute if auto_execute and high confidence
        execution_result = None
        if auto_execute and classification.get("confidence", 0) > 0.5:
            intent = classification.get("intent")
            params = classification.get("parameters", {})

            if intent == "time_change":
                event_name = params.get("event_name", "")
                new_time = params.get("new_time", "")
                if event_name and new_time:
                    success = event_manager.update_schedule_time(event_name, new_time)
                    if success:
                        event_manager.save_event_data()
                    execution_result = {
                        "executed": success,
                        "action": "time_change",
                        "details": (
                            f"Updated {event_name} to {new_time}"
                            if success
                            else f"Failed to find {event_name}"
                        ),
                    }

            elif intent == "location_change":
                event_name = params.get("event_name", "")
                new_location = params.get("new_location", "")
                if event_name and new_location:
                    success = event_manager.update_schedule_location(
                        event_name, new_location
                    )
                    if success:
                        event_manager.save_event_data()
                    execution_result = {
                        "executed": success,
                        "action": "location_change",
                        "details": (
                            f"Moved {event_name} to {new_location}"
                            if success
                            else f"Failed to find {event_name}"
                        ),
                    }

        result = {
            "original_command": command,
            "classification": classification,
            "execution_result": execution_result,
            "status": (
                "completed"
                if execution_result and execution_result.get("executed")
                else "classified_only"
            ),
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_schedule":
        result = {"schedule": event_manager.event_data.get("schedule", [])}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_faq":
        result = {"faq": event_manager.event_data.get("faq", {})}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_organizer":
        # Support both old single organizer format and new multiple organizers format
        organizers = event_manager.event_data.get("organizers", [])
        legacy_organizer = event_manager.event_data.get("organizer", {})

        # If no organizers array but legacy organizer exists, use it
        if not organizers and legacy_organizer:
            organizers = [legacy_organizer]

        result = {
            "organizers": organizers,
            "event_details": {
                "name": event_manager.event_data.get("name"),
                "date": event_manager.event_data.get("date"),
                "venue": event_manager.event_data.get("venue"),
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_organizers":
        organizers = event_manager.event_data.get("organizers", [])
        legacy_organizer = event_manager.event_data.get("organizer", {})

        # If no organizers array but legacy organizer exists, use it
        if not organizers and legacy_organizer:
            organizers = [legacy_organizer]

        # Add contact summary
        organizer_summary = {
            "total_organizers": len(organizers),
            "organizers_with_phone": len(
                [org for org in organizers if org.get("phone")]
            ),
            "organizers_with_email": len(
                [org for org in organizers if org.get("email")]
            ),
        }

        result = {"organizers": organizers, "summary": organizer_summary}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_attendees":
        result = {
            "attendees": event_manager.event_data.get("attendees", []),
            "registration_info": event_manager.event_data.get("registration", {}),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_everything":
        result = {"complete_event_data": event_manager.event_data}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_dietary_requirements":
        attendees = event_manager.event_data.get("attendees", [])

        # Extract dietary information
        dietary_summary = {}
        dietary_details = []

        for attendee in attendees:
            dietary = attendee.get("dietary_restrictions", "none")
            dietary_details.append(
                {
                    "name": attendee.get("name"),
                    "company": attendee.get("company"),
                    "dietary_restrictions": dietary,
                }
            )

            # Count dietary restrictions
            if dietary in dietary_summary:
                dietary_summary[dietary] += 1
            else:
                dietary_summary[dietary] = 1

        result = {
            "total_attendees": len(attendees),
            "dietary_summary": dietary_summary,
            "detailed_requirements": dietary_details,
            "catering_notes": "Consider offering vegetarian, gluten-free, and regular options based on attendee needs",
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "add_attendee":
        name_arg = arguments.get("name", "")
        email = arguments.get("email")
        phone = arguments.get("phone")
        company = arguments.get("company")
        dietary_restrictions = arguments.get("dietary_restrictions", "none")

        success = event_manager.add_attendee(
            name_arg, email, phone, company, dietary_restrictions
        )

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully added attendee '{name_arg}'",
                "name": name_arg,
                "dietary_restrictions": dietary_restrictions,
            }
        else:
            result = {
                "success": False,
                "message": f"Failed to add attendee '{name_arg}'",
                "name": name_arg,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "remove_attendee":
        attendee_id = arguments.get("attendee_identifier", "")

        success = event_manager.remove_attendee(attendee_id)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully removed attendee '{attendee_id}'",
                "attendee_identifier": attendee_id,
            }
        else:
            result = {
                "success": False,
                "message": f"Could not find attendee: {attendee_id}",
                "attendee_identifier": attendee_id,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_attendee":
        attendee_id = arguments.get("attendee_identifier", "")
        field = arguments.get("field", "")
        value = arguments.get("value", "")

        success = event_manager.update_attendee(attendee_id, field, value)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully updated {field} for attendee '{attendee_id}'",
                "attendee_identifier": attendee_id,
                "field": field,
                "value": value,
            }
        else:
            result = {
                "success": False,
                "message": f"Could not find attendee: {attendee_id}",
                "attendee_identifier": attendee_id,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_faq":
        key = arguments.get("key", "")
        value = arguments.get("value", "")

        success = event_manager.update_faq(key, value)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully updated FAQ entry '{key}'",
                "key": key,
                "value": value,
            }
        else:
            result = {
                "success": False,
                "message": f"Failed to update FAQ entry '{key}'",
                "key": key,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_organizer":
        field = arguments.get("field", "")
        value = arguments.get("value", "")

        success = event_manager.update_organizer(field, value)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully updated organizer {field}",
                "field": field,
                "value": value,
            }
        else:
            result = {
                "success": False,
                "message": f"Failed to update organizer {field}",
                "field": field,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "add_schedule_item":
        title = arguments.get("title", "")
        time = arguments.get("time", "")
        end_time = arguments.get("end_time", "")
        location = arguments.get("location", "")
        description = arguments.get("description")
        speaker = arguments.get("speaker")

        success = event_manager.add_schedule_item(
            title, time, end_time, location, description, speaker
        )

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully added '{title}' to schedule",
                "title": title,
                "time": time,
                "end_time": end_time,
                "location": location,
            }
        else:
            result = {
                "success": False,
                "message": f"Failed to add '{title}' to schedule",
                "title": title,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "remove_schedule_item":
        event_id = arguments.get("event_identifier", "")

        success = event_manager.remove_schedule_item(event_id)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully removed '{event_id}' from schedule",
                "event_id": event_id,
            }
        else:
            result = {
                "success": False,
                "message": f"Could not find event: {event_id}",
                "event_id": event_id,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "update_event_details":
        field = arguments.get("field", "")
        value = arguments.get("value", "")

        success = event_manager.update_event_details(field, value)

        if success:
            event_manager.save_event_data()
            result = {
                "success": True,
                "message": f"Successfully updated event {field}",
                "field": field,
                "value": value,
            }
        else:
            result = {
                "success": False,
                "message": f"Failed to update event {field}",
                "field": field,
            }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_changelog":
        limit = arguments.get("limit", 10)

        changelog = event_manager.event_data.get("changelog", [])
        recent_changes = changelog[-limit:] if len(changelog) > limit else changelog

        result = {
            "total_changes": len(changelog),
            "recent_changes": recent_changes,
            "limit": limit,
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "send_sms":
        person_id = arguments.get("person_identifier", "")
        message = arguments.get("message", "")

        result = event_manager.send_sms(person_id, message)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point for the MCP server"""
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="emceep-event-manager",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
