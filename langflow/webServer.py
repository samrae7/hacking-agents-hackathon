#!/usr/bin/env python3
"""
Event Data Web Server

A Flask web server that serves event data from event.json file.
Provides REST API endpoints for accessing event information including
schedule, attendees, organizers, FAQ, and real-time updates.

Usage:
    python webServer.py

The server will start on http://localhost:5000
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("event-web-server")

class EventDataLoader:
    """Handles loading and serving event data"""
    
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.event_data = {}
        self.load_event_data()
    
    def load_event_data(self) -> Dict[str, Any]:
        """Load event data from JSON file"""
        try:
            with open(self.data_path, 'r') as f:
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
    
    def get_all_data(self) -> Dict[str, Any]:
        """Get all event data"""
        self.load_event_data()  # Refresh data
        return self.event_data
    
    def get_schedule(self) -> list:
        """Get event schedule"""
        self.load_event_data()
        return self.event_data.get('schedule', [])
    
    def get_attendees(self) -> list:
        """Get attendee list"""
        self.load_event_data()
        return self.event_data.get('attendees', [])
    
    def get_organizers(self) -> list:
        """Get organizer list"""
        self.load_event_data()
        return self.event_data.get('organizers', [])
    
    def get_faq(self) -> Dict[str, str]:
        """Get FAQ data"""
        self.load_event_data()
        return self.event_data.get('faq', {})
    
    def get_changelog(self, limit: Optional[int] = None) -> list:
        """Get changelog data"""
        self.load_event_data()
        changelog = self.event_data.get('changelog', [])
        if limit:
            return changelog[-limit:]
        return changelog
    
    def get_event_info(self) -> Dict[str, Any]:
        """Get basic event information"""
        self.load_event_data()
        return {
            'event_id': self.event_data.get('event_id'),
            'name': self.event_data.get('name'),
            'date': self.event_data.get('date'),
            'location': self.event_data.get('location', {})
        }
    
    def get_dietary_requirements(self) -> Dict[str, Any]:
        """Get dietary requirements summary"""
        self.load_event_data()
        attendees = self.event_data.get('attendees', [])
        
        dietary_summary = {}
        dietary_details = []
        
        for attendee in attendees:
            dietary = attendee.get('dietary_restrictions', 'none')
            dietary_details.append({
                'name': attendee.get('name'),
                'company': attendee.get('company'),
                'dietary_restrictions': dietary
            })
            
            if dietary in dietary_summary:
                dietary_summary[dietary] += 1
            else:
                dietary_summary[dietary] = 1
        
        return {
            'total_attendees': len(attendees),
            'dietary_summary': dietary_summary,
            'detailed_requirements': dietary_details
        }

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Initialize event data loader
EVENT_DATA_PATH = Path("data/event.json")
event_loader = EventDataLoader(EVENT_DATA_PATH)

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'event-web-server',
        'data_file': str(EVENT_DATA_PATH)
    })

# Main endpoints
@app.route('/api/event')
def get_all_event_data():
    """Get complete event data"""
    try:
        data = event_loader.get_all_data()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting all event data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/event/info')
def get_event_info():
    """Get basic event information"""
    try:
        data = event_loader.get_event_info()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting event info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/schedule')
def get_schedule():
    """Get event schedule"""
    try:
        schedule = event_loader.get_schedule()
        return jsonify({
            'success': True,
            'data': schedule,
            'count': len(schedule)
        })
    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/attendees')
def get_attendees():
    """Get attendee list"""
    try:
        attendees = event_loader.get_attendees()
        return jsonify({
            'success': True,
            'data': attendees,
            'count': len(attendees)
        })
    except Exception as e:
        logger.error(f"Error getting attendees: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/organizers')
def get_organizers():
    """Get organizer list"""
    try:
        organizers = event_loader.get_organizers()
        return jsonify({
            'success': True,
            'data': organizers,
            'count': len(organizers)
        })
    except Exception as e:
        logger.error(f"Error getting organizers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/faq')
def get_faq():
    """Get FAQ data"""
    try:
        faq = event_loader.get_faq()
        return jsonify({
            'success': True,
            'data': faq,
            'count': len(faq)
        })
    except Exception as e:
        logger.error(f"Error getting FAQ: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/changelog')
def get_changelog():
    """Get changelog data"""
    try:
        limit = request.args.get('limit', type=int)
        changelog = event_loader.get_changelog(limit)
        return jsonify({
            'success': True,
            'data': changelog,
            'count': len(changelog),
            'limit': limit
        })
    except Exception as e:
        logger.error(f"Error getting changelog: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/dietary')
def get_dietary_requirements():
    """Get dietary requirements summary"""
    try:
        dietary_data = event_loader.get_dietary_requirements()
        return jsonify({
            'success': True,
            'data': dietary_data
        })
    except Exception as e:
        logger.error(f"Error getting dietary requirements: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Specific item endpoints
@app.route('/api/schedule/<item_id>')
def get_schedule_item(item_id):
    """Get specific schedule item"""
    try:
        schedule = event_loader.get_schedule()
        item = next((item for item in schedule if item.get('id') == item_id), None)
        
        if item:
            return jsonify({
                'success': True,
                'data': item
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Schedule item not found: {item_id}'
            }), 404
    except Exception as e:
        logger.error(f"Error getting schedule item {item_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/attendees/<attendee_id>')
def get_attendee(attendee_id):
    """Get specific attendee"""
    try:
        attendees = event_loader.get_attendees()
        attendee = next((att for att in attendees if att.get('id') == attendee_id), None)
        
        if attendee:
            return jsonify({
                'success': True,
                'data': attendee
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Attendee not found: {attendee_id}'
            }), 404
    except Exception as e:
        logger.error(f"Error getting attendee {attendee_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Root endpoint with API documentation
@app.route('/')
def api_documentation():
    """API documentation endpoint"""
    return jsonify({
        'service': 'Event Data Web Server',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health - Health check',
            'event_data': '/api/event - Complete event data',
            'event_info': '/api/event/info - Basic event information',
            'schedule': '/api/schedule - Event schedule',
            'attendees': '/api/attendees - Attendee list',
            'organizers': '/api/organizers - Organizer list',
            'faq': '/api/faq - FAQ data',
            'changelog': '/api/changelog?limit=N - Changelog (optional limit)',
            'dietary': '/api/dietary - Dietary requirements summary',
            'schedule_item': '/api/schedule/<item_id> - Specific schedule item',
            'attendee': '/api/attendees/<attendee_id> - Specific attendee'
        },
        'data_source': str(EVENT_DATA_PATH)
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'message': 'Please check the API documentation at /'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

if __name__ == '__main__':
    logger.info("Starting Event Data Web Server...")
    logger.info(f"Serving data from: {EVENT_DATA_PATH}")
    logger.info("Server will be available at: http://localhost:5001")
    logger.info("API documentation at: http://localhost:5001/")
    
    # Run the Flask development server
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )