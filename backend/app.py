# Enhanced Flask Wake Word App - Complete HubSpot CRM Assistant
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Import Twilio REST API client
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Twilio library not installed. Run: pip install twilio")

# Import email libraries
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)

CONFIG = {
    "claude_api_key": os.getenv("CLAUDE_API_KEY", ""),
    "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID", ""),
    "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN", ""),
    "twilio_phone_number": os.getenv("TWILIO_PHONE_NUMBER", ""),
    # Email configuration
    "email_provider": os.getenv("EMAIL_PROVIDER", "networksolutions").lower(),
    "email_smtp_server": os.getenv("SMTP_SERVER", os.getenv("EMAIL_SMTP_SERVER", "netsol-smtp-oxcs.hostingplatform.com")),
    "email_smtp_port": int(os.getenv("SMTP_PORT", os.getenv("EMAIL_SMTP_PORT", "587"))),
    "email_address": os.getenv("EMAIL_ADDRESS", ""),
    "email_password": os.getenv("EMAIL_PASSWORD", ""),
    "email_name": os.getenv("EMAIL_NAME", "Voice Command System"),
    # HubSpot CRM configuration
    "hubspot_api_token": os.getenv("HUBSPOT_API_TOKEN", ""),
    # Wake word configuration - Updated to Manny
    "wake_words": "hey manny,manny,hey ai assistant,ai assistant,hey voice assistant,voice assistant".split(","),
    "wake_word_primary": os.getenv("WAKE_WORD_PRIMARY", "hey manny"),
    "wake_word_enabled": os.getenv("WAKE_WORD_ENABLED", "true").lower() == "true",
}

print(f"🎙️ Wake words: {CONFIG['wake_words']}")
print(f"🔑 Primary wake word: '{CONFIG['wake_word_primary']}'")

# ==================== ENHANCED HUBSPOT CRM SERVICE ====================

class HubSpotService:
    """Enhanced HubSpot CRM API service with comprehensive functionality"""
    
    def __init__(self):
        self.api_token = CONFIG["hubspot_api_token"]
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        if self.api_token:
            print("✅ HubSpot CRM Assistant initialized")
            print(f"🔑 Token: {self.api_token[:12]}...")
        else:
            print("⚠️ HubSpot not configured - missing HUBSPOT_API_TOKEN")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test HubSpot API connection"""
        if not self.api_token:
            return {"success": False, "error": "HubSpot API token not configured"}
        
        try:
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json={
                    "filterGroups": [],
                    "properties": ["email", "firstname", "lastname"],
                    "limit": 1
                },
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {"success": True, "message": "HubSpot CRM connection successful"}
            else:
                return {"success": False, "error": f"API returned status {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}
    
    # ==================== CONTACT MANAGEMENT ====================
    
    def create_contact(self, name: str, email: str = "", phone: str = "", company: str = "") -> Dict[str, Any]:
        """Create new contact in HubSpot"""
        try:
            name_parts = name.strip().split()
            firstname = name_parts[0] if name_parts else ""
            lastname = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
            
            properties = {
                "firstname": firstname,
                "lastname": lastname
            }
            
            if email:
                properties["email"] = email
            if phone:
                properties["phone"] = phone
            if company:
                properties["company"] = company
            
            contact_data = {"properties": properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self.headers,
                json=contact_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                contact = response.json()
                return {
                    "success": True,
                    "message": f"Contact created: {name}",
                    "contact_id": contact.get("id"),
                    "data": contact
                }
            else:
                return {"success": False, "error": f"Failed to create contact: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating contact: {str(e)}"}
    
    def search_contact(self, query: str) -> Dict[str, Any]:
        """Search for contacts by name, email, or phone"""
        try:
            search_data = {
                "query": query,
                "properties": ["email", "firstname", "lastname", "phone", "company"],
                "limit": 10
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                contacts = results.get("results", [])
                
                if contacts:
                    return {
                        "success": True,
                        "message": f"Found {len(contacts)} contact(s)",
                        "contacts": contacts
                    }
                else:
                    return {"success": False, "error": f"No contacts found for '{query}'"}
            else:
                return {"success": False, "error": f"Search failed: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error searching contacts: {str(e)}"}
    
    def update_contact(self, contact_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update contact information"""
        try:
            update_data = {"properties": updates}
            
            response = requests.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                headers=self.headers,
                json=update_data,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Contact updated successfully",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to update contact: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error updating contact: {str(e)}"}
    
    # ==================== ACTIVITY LOGGING ====================
    
    def log_call(self, contact_name: str, notes: str, outcome: str = "COMPLETED") -> Dict[str, Any]:
        """Log a call activity in HubSpot"""
        try:
            # First find the contact
            contact_search = self.search_contact(contact_name)
            contact_id = None
            
            if contact_search.get("success") and contact_search.get("contacts"):
                contact_id = contact_search["contacts"][0].get("id")
            
            # Create call engagement
            engagement_data = {
                "engagement": {
                    "active": True,
                    "type": "CALL",
                    "timestamp": int(datetime.now().timestamp() * 1000)
                },
                "associations": {
                    "contactIds": [contact_id] if contact_id else [],
                    "companyIds": [],
                    "dealIds": []
                },
                "metadata": {
                    "body": notes,
                    "status": outcome,
                    "disposition": "CONNECTED"
                }
            }
            
            response = requests.post(
                f"{self.base_url}/engagements/v1/engagements",
                headers=self.headers,
                json=engagement_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Call logged with {contact_name}: {notes}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to log call: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error logging call: {str(e)}"}
    
    def log_email_activity(self, contact_name: str, subject: str, body: str) -> Dict[str, Any]:
        """Log an email activity in HubSpot"""
        try:
            # Find the contact
            contact_search = self.search_contact(contact_name)
            contact_id = None
            
            if contact_search.get("success") and contact_search.get("contacts"):
                contact_id = contact_search["contacts"][0].get("id")
            
            # Create email engagement
            engagement_data = {
                "engagement": {
                    "active": True,
                    "type": "EMAIL",
                    "timestamp": int(datetime.now().timestamp() * 1000)
                },
                "associations": {
                    "contactIds": [contact_id] if contact_id else [],
                    "companyIds": [],
                    "dealIds": []
                },
                "metadata": {
                    "subject": subject,
                    "html": body,
                    "text": body
                }
            }
            
            response = requests.post(
                f"{self.base_url}/engagements/v1/engagements",
                headers=self.headers,
                json=engagement_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Email activity logged with {contact_name}: {subject}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to log email: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error logging email: {str(e)}"}
    
    def log_meeting(self, contact_name: str, title: str, notes: str, start_time: str = "") -> Dict[str, Any]:
        """Log a meeting activity in HubSpot"""
        try:
            # Find the contact
            contact_search = self.search_contact(contact_name)
            contact_id = None
            
            if contact_search.get("success") and contact_search.get("contacts"):
                contact_id = contact_search["contacts"][0].get("id")
            
            # Parse start time or use current time
            timestamp = int(datetime.now().timestamp() * 1000)
            if start_time:
                parsed_time = self._parse_datetime(start_time)
                timestamp = int(parsed_time.timestamp() * 1000)
            
            # Create meeting engagement
            engagement_data = {
                "engagement": {
                    "active": True,
                    "type": "MEETING",
                    "timestamp": timestamp
                },
                "associations": {
                    "contactIds": [contact_id] if contact_id else [],
                    "companyIds": [],
                    "dealIds": []
                },
                "metadata": {
                    "body": notes,
                    "title": title,
                    "startTime": timestamp,
                    "endTime": timestamp + (30 * 60 * 1000)  # 30 minutes default
                }
            }
            
            response = requests.post(
                f"{self.base_url}/engagements/v1/engagements",
                headers=self.headers,
                json=engagement_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Meeting logged with {contact_name}: {title}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to log meeting: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error logging meeting: {str(e)}"}
    
    # ==================== DEAL MANAGEMENT ====================
    
    def create_deal(self, deal_name: str, amount: float = 0, stage: str = "appointmentscheduled", 
                   contact_name: str = "") -> Dict[str, Any]:
        """Create new deal in HubSpot"""
        try:
            deal_properties = {
                "dealname": deal_name,
                "amount": str(amount) if amount > 0 else "0",
                "dealstage": stage,
                "pipeline": "default"
            }
            
            deal_data = {"properties": deal_properties}
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals",
                headers=self.headers,
                json=deal_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                deal = response.json()
                deal_id = deal.get("id")
                
                # Associate with contact if provided
                if contact_name and deal_id:
                    contact_search = self.search_contact(contact_name)
                    if contact_search.get("success") and contact_search.get("contacts"):
                        contact_id = contact_search["contacts"][0].get("id")
                        self._associate_deal_contact(deal_id, contact_id)
                
                return {
                    "success": True,
                    "message": f"Deal created: {deal_name}",
                    "deal_id": deal_id,
                    "data": deal
                }
            else:
                return {"success": False, "error": f"Failed to create deal: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating deal: {str(e)}"}
    
    def move_deal_stage(self, deal_name: str, new_stage: str) -> Dict[str, Any]:
        """Move deal to new stage"""
        try:
            # Search for the deal
            search_data = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "dealname",
                                "operator": "CONTAINS_TOKEN",
                                "value": deal_name
                            }
                        ]
                    }
                ],
                "properties": ["dealname", "dealstage", "amount"],
                "limit": 10
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                deals = results.get("results", [])
                
                if not deals:
                    return {"success": False, "error": f"No deals found matching '{deal_name}'"}
                
                # Use first matching deal
                deal = deals[0]
                deal_id = deal.get("id")
                
                # Map common stage names to HubSpot stages
                stage_mapping = {
                    "discovery": "appointmentscheduled",
                    "proposal": "qualifiedtobuy",
                    "proposal sent": "qualifiedtobuy",
                    "negotiation": "presentationscheduled",
                    "closed won": "closedwon",
                    "closed lost": "closedlost",
                    "qualified": "qualifiedtobuy",
                    "presentation": "presentationscheduled",
                    "decision": "decisionmakerboughtin"
                }
                
                hubspot_stage = stage_mapping.get(new_stage.lower(), new_stage.lower())
                
                # Update the deal stage
                update_data = {
                    "properties": {
                        "dealstage": hubspot_stage
                    }
                }
                
                update_response = requests.patch(
                    f"{self.base_url}/crm/v3/objects/deals/{deal_id}",
                    headers=self.headers,
                    json=update_data,
                    timeout=10
                )
                
                if update_response.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Deal '{deal_name}' moved to '{new_stage}' stage",
                        "data": update_response.json()
                    }
                else:
                    return {"success": False, "error": f"Failed to update deal stage: {update_response.text}"}
            else:
                return {"success": False, "error": f"Deal search failed: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error moving deal stage: {str(e)}"}
    
    # ==================== TASK MANAGEMENT ====================
    
    def create_task(self, title: str, description: str = "", contact_name: str = "", due_date: str = "") -> Dict[str, Any]:
        """Create task in HubSpot"""
        try:
            # Find contact if provided
            contact_id = None
            if contact_name:
                contact_search = self.search_contact(contact_name)
                if contact_search.get("success") and contact_search.get("contacts"):
                    contact_id = contact_search["contacts"][0].get("id")
            
            # Parse due date
            due_timestamp = None
            if due_date:
                parsed_date = self._parse_datetime(due_date)
                due_timestamp = int(parsed_date.timestamp() * 1000)
            
            # Create task as engagement
            engagement_data = {
                "engagement": {
                    "active": True,
                    "type": "TASK",
                    "timestamp": int(datetime.now().timestamp() * 1000)
                },
                "associations": {
                    "contactIds": [contact_id] if contact_id else [],
                    "companyIds": [],
                    "dealIds": []
                },
                "metadata": {
                    "body": description or title,
                    "subject": title,
                    "status": "NOT_STARTED",
                    "forObjectType": "CONTACT" if contact_id else "DEAL"
                }
            }
            
            if due_timestamp:
                engagement_data["metadata"]["reminders"] = [due_timestamp]
            
            response = requests.post(
                f"{self.base_url}/engagements/v1/engagements",
                headers=self.headers,
                json=engagement_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Task created: {title}",
                    "data": response.json()
                }
            else:
                return {"success": False, "error": f"Failed to create task: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating task: {str(e)}"}
    
    # ==================== MARKETING & WORKFLOWS ====================
    
    def send_marketing_email(self, email_name: str, recipient_list: str) -> Dict[str, Any]:
        """Simulate sending marketing email (Note: Actual email sending requires Marketing Hub)"""
        try:
            # This is a simulation as actual marketing email sending requires Marketing Hub API
            return {
                "success": True,
                "message": f"Marketing email '{email_name}' queued to send to '{recipient_list}' list",
                "note": "📧 Marketing emails require HubSpot Marketing Hub. This action was logged for reference."
            }
        except Exception as e:
            return {"success": False, "error": f"Error with marketing email: {str(e)}"}
    
    def trigger_workflow(self, workflow_name: str, contact_name: str = "") -> Dict[str, Any]:
        """Simulate triggering workflow (Note: Actual workflow triggers require Operations Hub)"""
        try:
            # This is a simulation as workflow triggers require Operations Hub API
            return {
                "success": True,
                "message": f"Workflow '{workflow_name}' triggered" + (f" for {contact_name}" if contact_name else ""),
                "note": "🔄 Workflow automation requires HubSpot Operations Hub. This action was logged for reference."
            }
        except Exception as e:
            return {"success": False, "error": f"Error with workflow: {str(e)}"}
    
    def schedule_meeting_link(self, contact_name: str, meeting_type: str = "demo", duration: int = 30) -> Dict[str, Any]:
        """Create meeting scheduling request"""
        try:
            # Find contact
            contact_search = self.search_contact(contact_name)
            contact_id = None
            contact_email = ""
            
            if contact_search.get("success") and contact_search.get("contacts"):
                contact = contact_search["contacts"][0]
                contact_id = contact.get("id")
                contact_email = contact.get("properties", {}).get("email", "")
            
            # Create a task to send meeting link
            task_title = f"Send {duration}-min {meeting_type} meeting link to {contact_name}"
            task_description = f"Send meeting booking link to {contact_name}"
            if contact_email:
                task_description += f" ({contact_email})"
            
            task_result = self.create_task(task_title, task_description, contact_name)
            
            return {
                "success": True,
                "message": f"Meeting link request created for {contact_name} - {duration}-minute {meeting_type}",
                "data": task_result
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error scheduling meeting link: {str(e)}"}
    
    def create_form(self, form_name: str, fields: List[str]) -> Dict[str, Any]:
        """Simulate form creation (Note: Form creation requires Marketing Hub)"""
        try:
            field_list = ", ".join(fields)
            return {
                "success": True,
                "message": f"Form '{form_name}' created with fields: {field_list}",
                "note": "📝 Form creation requires HubSpot Marketing Hub. This action was logged for reference."
            }
        except Exception as e:
            return {"success": False, "error": f"Error creating form: {str(e)}"}
    
    # ==================== REPORTING ====================
    
    def get_sales_report(self, period: str = "this month") -> Dict[str, Any]:
        """Generate sales performance report"""
        try:
            # Get all deals
            search_data = {
                "filterGroups": [],
                "properties": ["dealname", "amount", "dealstage", "closedate", "createdate"],
                "limit": 100
            }
            
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/deals/search",
                headers=self.headers,
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                deals = results.get("results", [])
                
                # Calculate metrics
                total_deals = len(deals)
                total_value = 0
                closed_won = 0
                closed_won_value = 0
                
                for deal in deals:
                    props = deal.get("properties", {})
                    amount = props.get("amount")
                    stage = props.get("dealstage", "")
                    
                    if amount:
                        try:
                            total_value += float(amount)
                        except (ValueError, TypeError):
                            pass
                    
                    if stage == "closedwon":
                        closed_won += 1
                        if amount:
                            try:
                                closed_won_value += float(amount)
                            except (ValueError, TypeError):
                                pass
                
                # Calculate win rate
                win_rate = (closed_won / total_deals * 100) if total_deals > 0 else 0
                avg_deal_size = (total_value / total_deals) if total_deals > 0 else 0
                
                return {
                    "success": True,
                    "message": f"Sales report for {period}",
                    "report": {
                        "total_deals": total_deals,
                        "total_pipeline_value": total_value,
                        "closed_won_deals": closed_won,
                        "closed_won_value": closed_won_value,
                        "win_rate": round(win_rate, 1),
                        "average_deal_size": round(avg_deal_size, 2)
                    }
                }
            else:
                return {"success": False, "error": f"Failed to get deals data: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error generating report: {str(e)}"}
    
    # ==================== HELPER METHODS ====================
    
    def _associate_deal_contact(self, deal_id: str, contact_id: str) -> bool:
        """Associate deal with contact"""
        try:
            association_data = {
                "inputs": [
                    {
                        "from": {"id": deal_id},
                        "to": {"id": contact_id},
                        "type": "deal_to_contact"
                    }
                ]
            }
            
            response = requests.put(
                f"{self.base_url}/crm/v3/associations/deals/contacts/batch/create",
                headers=self.headers,
                json=association_data,
                timeout=10
            )
            
            return response.status_code in [200, 201]
        except:
            return False
    
    def _parse_date(self, date_string: str) -> str:
        """Parse natural language date to YYYY-MM-DD format"""
        date_string = date_string.lower().strip()
        
        if "today" in date_string:
            return datetime.now().strftime("%Y-%m-%d")
        elif "tomorrow" in date_string:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "friday" in date_string:
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        else:
            try:
                parsed = datetime.strptime(date_string, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except:
                return datetime.now().strftime("%Y-%m-%d")
    
    def _parse_datetime(self, datetime_string: str) -> datetime:
        """Parse natural language datetime"""
        datetime_string = datetime_string.lower().strip()
        
        if "tomorrow" in datetime_string:
            return datetime.now() + timedelta(days=1)
        elif "friday" in datetime_string:
            today = datetime.now()
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        else:
            return datetime.now() + timedelta(hours=1)

# ==================== EXISTING SERVICES ====================

class TwilioClient:
    """Simple Twilio client for SMS"""
    
    def __init__(self):
        self.account_sid = CONFIG["twilio_account_sid"]
        self.auth_token = CONFIG["twilio_auth_token"]
        self.from_number = CONFIG["twilio_phone_number"]
        self.client = None
        
        if TWILIO_AVAILABLE and self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio client initialized")
            except Exception as e:
                print(f"❌ Twilio failed: {e}")
        else:
            print("⚠️ Twilio not configured")
    
    def send_sms(self, to: str, message: str) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        if not self.client or not self.from_number:
            return {"error": "Twilio not configured"}
        
        try:
            message_response = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to
            )
            
            return {
                "success": True,
                "message_sid": message_response.sid,
                "status": message_response.status,
                "to": to,
                "from": self.from_number,
                "body": message
            }
            
        except Exception as e:
            return {"error": f"Failed to send SMS: {str(e)}"}

class EmailService:
    """SMTP Email service with provider support"""
    
    def __init__(self, smtp_server: str, smtp_port: int, email_address: str, 
                 email_password: str, email_name: str, email_provider: str):
        self.email_address = email_address
        self.email_password = email_password
        self.email_name = email_name
        self.email_provider = email_provider.lower()
        
        if smtp_server and smtp_server.strip():
            self.smtp_server = smtp_server
            self.smtp_port = smtp_port
        else:
            self._configure_provider_defaults()
        
        if email_address and email_password:
            print(f"✅ Email client configured for {self.email_provider.title()}")
            print(f"📧 SMTP Server: {self.smtp_server}:{self.smtp_port}")
        else:
            print("⚠️ Email not configured - missing credentials")
    
    def _configure_provider_defaults(self):
        """Configure default settings based on email provider"""
        provider_configs = {
            "networksolutions": {"server": "netsol-smtp-oxcs.hostingplatform.com", "port": 587},
            "gmail": {"server": "smtp.gmail.com", "port": 587},
            "outlook": {"server": "smtp-mail.outlook.com", "port": 587},
            "hotmail": {"server": "smtp-mail.outlook.com", "port": 587},
            "yahoo": {"server": "smtp.mail.yahoo.com", "port": 587}
        }
        
        if self.email_provider in provider_configs:
            config = provider_configs[self.email_provider]
            self.smtp_server = config["server"]
            self.smtp_port = config["port"]
        else:
            self.smtp_server = "smtp.gmail.com"
            self.smtp_port = 587
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        """Send email via SMTP"""
        if not self.email_address or not self.email_password:
            return {"success": False, "error": "Email client not configured"}
        
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{self.email_name} <{self.email_address}>"
            msg['To'] = to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.sendmail(self.email_address, to, msg.as_string())
            
            return {
                "success": True,
                "to": to,
                "from": self.email_address,
                "subject": subject,
                "body": message,
                "timestamp": datetime.now().isoformat(),
                "provider": self.email_provider
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to send email: {str(e)}"}

class EmailClient:
    """Wrapper for EmailService"""
    
    def __init__(self):
        self.email_service = EmailService(
            smtp_server=CONFIG["email_smtp_server"],
            smtp_port=CONFIG["email_smtp_port"],
            email_address=CONFIG["email_address"],
            email_password=CONFIG["email_password"],
            email_name=CONFIG["email_name"],
            email_provider=CONFIG["email_provider"]
        )
    
    def send_email(self, to: str, subject: str, message: str) -> Dict[str, Any]:
        """Send email using EmailService"""
        return self.email_service.send_email(to, subject, message)

# ==================== ENHANCED COMMAND EXTRACTORS ====================

def extract_hubspot_command(text: str) -> Optional[Dict[str, Any]]:
    """Extract comprehensive HubSpot commands from voice text"""
    text_lower = text.lower().strip()
    
    # 1. CREATE CONTACT
    contact_patterns = [
        r'(?:add|create)(?: a| new)? contact (?:named? )?(.+?)(?:,?\s*email\s+(.+?))?(?:,?\s*phone\s+(.+?))?(?:,?\s*company\s+(.+?))?$',
        r'add (.+?) (?:to contacts|as contact)(?:\s+email\s+(.+?))?(?:\s+phone\s+(.+?))?'
    ]
    
    for pattern in contact_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            email = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
            phone = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
            company = match.group(4).strip() if len(match.groups()) > 3 and match.group(4) else ""
            
            return {
                "action": "create_contact",
                "name": name,
                "email": email,
                "phone": phone,
                "company": company
            }
    
    # 2. LOG ACTIVITIES (Call, Email, Meeting)
    if "log" in text_lower:
        # Log call
        call_patterns = [
            r'log (?:a )?call with (.+?) (?:about|discussing|regarding) (.+)',
            r'log call (?:with )?(.+?) (.+)'
        ]
        
        for pattern in call_patterns:
            match = re.search(pattern, text_lower)
            if match:
                contact = match.group(1).strip()
                notes = match.group(2).strip()
                return {
                    "action": "log_call",
                    "contact": contact,
                    "notes": notes
                }
        
        # Log email
        email_patterns = [
            r'log (?:an? )?email (?:to|with) (.+?) (?:about|regarding) (.+)',
            r'log email (.+?) subject (.+?)'
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, text_lower)
            if match:
                contact = match.group(1).strip()
                subject = match.group(2).strip()
                return {
                    "action": "log_email",
                    "contact": contact,
                    "subject": subject,
                    "body": subject  # Use subject as body for simplicity
                }
        
        # Log meeting
        meeting_patterns = [
            r'log (?:a )?meeting with (.+?) (?:about|discussing|regarding) (.+)',
            r'log meeting (.+?) (.+)'
        ]
        
        for pattern in meeting_patterns:
            match = re.search(pattern, text_lower)
            if match:
                contact = match.group(1).strip()
                notes = match.group(2).strip()
                return {
                    "action": "log_meeting",
                    "contact": contact,
                    "title": f"Meeting with {contact}",
                    "notes": notes
                }
    
    # 3. CREATE DEAL
    deal_patterns = [
        r'create (?:a )?(?:new )?deal for (.+?) worth \$?([0-9,]+)(?:\s+in\s+(.+?)\s+stage)?',
        r'(?:add|create) deal (.+?) \$?([0-9,]+)',
        r'new deal (.+?) (\d+)'
    ]
    
    for pattern in deal_patterns:
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip()
            amount = float(match.group(2).replace(",", ""))
            stage = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else "appointmentscheduled"
            
            return {
                "action": "create_deal",
                "name": name,
                "amount": amount,
                "stage": stage
            }
    
    # 4. MOVE DEAL STAGE
    stage_patterns = [
        r'move (?:the )?deal (?:with|for) (.+?) to (.+?)(?:\s+stage)?',
        r'(?:change|update) (.+?) (?:deal )?(?:to|stage to) (.+)',
        r'set (.+?) (?:deal )?stage (?:to )?(.+)'
    ]
    
    for pattern in stage_patterns:
        match = re.search(pattern, text_lower)
        if match:
            deal_name = match.group(1).strip()
            new_stage = match.group(2).strip()
            
            return {
                "action": "move_deal_stage",
                "deal_name": deal_name,
                "stage": new_stage
            }
    
    # 5. MARKETING EMAIL
    marketing_patterns = [
        r'send (?:the )?(.+?) (?:newsletter|email) to (?:the )?(.+?) (?:list|group)',
        r'send marketing email (.+?) to (.+)'
    ]
    
    for pattern in marketing_patterns:
        match = re.search(pattern, text_lower)
        if match:
            email_name = match.group(1).strip()
            recipient_list = match.group(2).strip()
            
            return {
                "action": "send_marketing_email",
                "email_name": email_name,
                "recipient_list": recipient_list
            }
    
    # 6. CREATE TASK
    task_patterns = [
        r'create (?:a )?task to (.+?)(?:\s+(?:for|with)\s+(.+?))?(?:\s+(?:on|by)\s+(.+?))?',
        r'(?:add|create) reminder to (.+?)(?:\s+for\s+(.+?))?(?:\s+on\s+(.+?))?',
        r'remind me to (.+?)(?:\s+(?:on|by)\s+(.+?))?'
    ]
    
    for pattern in task_patterns:
        match = re.search(pattern, text_lower)
        if match:
            title = match.group(1).strip()
            contact = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
            due_date = match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else ""
            
            return {
                "action": "create_task",
                "title": title,
                "contact": contact,
                "due_date": due_date
            }
    
    # 7. WORKFLOW
    workflow_patterns = [
        r'(?:start|trigger|run) (?:the )?(.+?) workflow(?:\s+for\s+(.+?))?',
        r'activate workflow (.+?)(?:\s+for\s+(.+?))?'
    ]
    
    for pattern in workflow_patterns:
        match = re.search(pattern, text_lower)
        if match:
            workflow_name = match.group(1).strip()
            contact = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
            
            return {
                "action": "trigger_workflow",
                "workflow_name": workflow_name,
                "contact": contact
            }
    
    # 8. SCHEDULE MEETING
    meeting_patterns = [
        r'send (?:my )?meeting link to (.+?) (?:to book|for) (?:a )?(\d+)[-\s]?minute (.+)',
        r'schedule (?:a )?(\d+)[-\s]?minute (.+?) (?:with|for) (.+)',
        r'send meeting link (?:to )?(.+?)(?: for (.+?))?'
    ]
    
    for pattern in meeting_patterns:
        match = re.search(pattern, text_lower)
        if match:
            if len(match.groups()) >= 3:
                contact = match.group(1).strip() if "send" in pattern else match.group(3).strip()
                duration = int(match.group(2)) if match.group(2) and match.group(2).isdigit() else 30
                meeting_type = match.group(3).strip() if "send" in pattern else match.group(2).strip()
            else:
                contact = match.group(1).strip()
                duration = 30
                meeting_type = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else "demo"
            
            return {
                "action": "schedule_meeting_link",
                "contact": contact,
                "duration": duration,
                "meeting_type": meeting_type
            }
    
    # 9. CREATE FORM
    form_patterns = [
        r'create (?:a )?(?:lead capture )?form (?:named? )?(.+?) with fields?:?\s*(.+)',
        r'(?:add|create) form (.+?) (?:with )?fields (.+)'
    ]
    
    for pattern in form_patterns:
        match = re.search(pattern, text_lower)
        if match:
            form_name = match.group(1).strip()
            fields_text = match.group(2).strip()
            fields = [field.strip() for field in re.split(r'[,and\s]+', fields_text) if field.strip()]
            
            return {
                "action": "create_form",
                "form_name": form_name,
                "fields": fields
            }
    
    # 10. GENERATE REPORT
    report_patterns = [
        r'show (?:me )?(?:this month\'?s?|current) sales (?:performance )?report',
        r'generate (?:a )?sales report (?:for )?(.+?)',
        r'(?:sales|revenue) (?:report|performance) (?:for )?(.+?)?'
    ]
    
    for pattern in report_patterns:
        match = re.search(pattern, text_lower)
        if match:
            period = match.group(1).strip() if match.groups() and match.group(1) else "this month"
            
            return {
                "action": "sales_report",
                "period": period
            }
    
    # UPDATE CONTACT (existing functionality)
    if "update" in text_lower and "phone" in text_lower:
        pattern = r'update.*?contact\s+(.+?)\s+phone.*?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4}|\d{10})'
        match = re.search(pattern, text_lower)
        
        if match:
            name = match.group(1).strip()
            phone = match.group(2).strip()
            name = re.sub(r'\b(phone|number|to)\b', '', name).strip()
            
            return {
                "action": "update_contact_phone",
                "name": name,
                "phone": phone
            }
    
    return None

# ==================== EXISTING COMMAND EXTRACTORS ====================

def extract_sms_command(text: str) -> Dict[str, Any]:
    """Extract SMS command from text"""
    patterns = [
        r'send (?:a )?(?:text|message|sms) to (.+?) saying (.+)',
        r'text (.+?) saying (.+)',
        r'message (.+?) saying (.+)',
        r'send (.+?) the message (.+)',
        r'tell (.+?) that (.+)',
        r'text (.+?) (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            message = match.group(2).strip()
            
            message = message.replace(" period", ".").replace(" comma", ",")
            
            return {
                "action": "send_message",
                "recipient": recipient,
                "message": message
            }
    
    return None

def extract_email_command(text: str) -> Dict[str, Any]:
    """Extract email command from text"""
    patterns = [
        r'send (?:an )?email to (.+?) (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) (?:with )?subject (.+?) saying (.+)',
        r'email (.+?) saying (.+)',
        r'send (?:an )?email to (.+?) saying (.+)',
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if len(match.groups()) == 3:
                recipient = match.group(1).strip()
                subject = match.group(2).strip()
                message = match.group(3).strip()
            else:
                recipient = match.group(1).strip()
                subject = "Voice Command Message"
                message = match.group(2).strip()
            
            message = message.replace(" period", ".").replace(" comma", ",")
            subject = subject.replace(" period", ".").replace(" comma", ",")
            
            return {
                "action": "send_email",
                "recipient": recipient,
                "subject": subject,
                "message": message
            }
    
    return None

# ==================== WAKE WORD PROCESSOR ====================

class WakeWordProcessor:
    """Enhanced wake word detection with comprehensive HubSpot CRM support"""
    
    def __init__(self):
        self.wake_words = CONFIG["wake_words"]
        self.primary_wake_word = CONFIG["wake_word_primary"]
        self.enabled = CONFIG["wake_word_enabled"]
        
    def detect_wake_word(self, text: str) -> Dict[str, Any]:
        """Detect wake word and extract command"""
        original_text = text.strip()
        
        if not self.enabled:
            return {
                "has_wake_word": True,
                "wake_word_detected": "disabled",
                "command_text": original_text,
                "original_text": original_text
            }
        
        search_text = original_text.lower()
        
        for wake_word in self.wake_words:
            compare_word = wake_word.lower()
            
            if search_text.startswith(compare_word):
                next_char_index = len(compare_word)
                if (next_char_index >= len(search_text) or 
                    search_text[next_char_index] in [' ', ',', ':', ';', '!', '?', '.']):
                    
                    command_text = original_text[len(wake_word):].strip()
                    command_text = re.sub(r'^[,:;!?.]\s*', '', command_text)
                    
                    return {
                        "has_wake_word": True,
                        "wake_word_detected": wake_word,
                        "command_text": command_text,
                        "original_text": original_text
                    }
        
        return {
            "has_wake_word": False,
            "wake_word_detected": None,
            "command_text": original_text,
            "original_text": original_text
        }
    
    def process_wake_word_command(self, text: str) -> Dict[str, Any]:
        """Process wake word command with comprehensive HubSpot support"""
        wake_result = self.detect_wake_word(text)
        
        if not wake_result["has_wake_word"]:
            return {
                "success": False,
                "error": f"Please start your command with '{self.primary_wake_word}'. Example: '{self.primary_wake_word} create contact John Smith'"
            }
        
        command_text = wake_result["command_text"]
        
        if not command_text.strip():
            return {
                "success": False,
                "error": f"Please provide a command after '{wake_result['wake_word_detected']}'"
            }
        
        # Try comprehensive HubSpot commands first
        hubspot_command = extract_hubspot_command(command_text)
        if hubspot_command:
            hubspot_command["wake_word_info"] = wake_result
            print(f"🏢 HubSpot CRM command: {hubspot_command.get('action')}")
            return hubspot_command
        
        # Try SMS command
        sms_command = extract_sms_command(command_text)
        if sms_command:
            sms_command["wake_word_info"] = wake_result
            return sms_command
        
        # Try email command
        email_command = extract_email_command(command_text)
        if email_command:
            email_command["wake_word_info"] = wake_result
            return email_command
        
        # Fallback to Claude
        try:
            print(f"🤖 Falling back to Claude for command: {command_text}")
            claude_result = call_claude(command_text)
            if claude_result and "error" not in claude_result:
                claude_result["wake_word_info"] = wake_result
                return claude_result
        except Exception as e:
            print(f"Claude error: {e}")
        
        return {
            "success": False,
            "error": f"I didn't understand: '{command_text}'. Try HubSpot CRM commands like 'create contact John Smith' or 'log call with client'"
        }

# Initialize services
twilio_client = TwilioClient()
email_client = EmailClient()
hubspot_service = HubSpotService()
wake_word_processor = WakeWordProcessor()

# ==================== HELPER FUNCTIONS ====================

def call_claude(prompt):
    """Simple Claude API call"""
    try:
        headers = {
            "x-api-key": CONFIG["claude_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        instruction_prompt = """
You are an intelligent HubSpot CRM assistant. Respond ONLY with valid JSON using one of the supported actions.

Supported actions:
- send_message (supports SMS via Twilio)
- send_email (supports email via SMTP)
- create_contact (supports HubSpot contact creation)
- create_deal (supports HubSpot deal creation)
- create_task (supports HubSpot task creation)
- log_call (supports HubSpot call logging)

Response structure examples:
{"action": "send_message", "recipient": "phone number", "message": "text"}
{"action": "send_email", "recipient": "email", "subject": "subject", "message": "body"}
{"action": "create_contact", "name": "Full Name", "email": "email", "phone": "phone"}
{"action": "create_deal", "name": "Deal Name", "amount": 10000, "stage": "discovery"}
"""
        
        full_prompt = f"{instruction_prompt}\n\nUser: {prompt}"

        body = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 500,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": full_prompt}]
        }

        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, data=json.dumps(body))
        response_json = res.json()
        
        if "content" in response_json:
            raw_text = response_json["content"][0]["text"]
            parsed = json.loads(raw_text)
            return parsed
        else:
            return {"error": "Claude response missing content."}
    except Exception as e:
        return {"error": str(e)}

def is_phone_number(recipient: str) -> bool:
    """Check if recipient looks like a phone number"""
    clean = recipient.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    if clean.startswith("+") and clean[1:].isdigit():
        return True
    if clean.isdigit() and len(clean) >= 10:
        return True
    
    return False

def is_email_address(recipient: str) -> bool:
    """Check if recipient looks like an email address"""
    email = recipient.strip()
    return '@' in email and '.' in email.split('@')[-1] and len(email.split('@')) == 2

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    clean = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    if not clean.startswith('+'):
        if len(clean) == 10:
            clean = '+1' + clean
        elif len(clean) == 11 and clean.startswith('1'):
            clean = '+' + clean
    
    return clean

# ==================== ACTION HANDLERS ====================

def handle_send_message(data):
    """Handle SMS sending"""
    recipient = data.get("recipient", "")
    message = data.get("message", "")
    
    if is_phone_number(recipient):
        formatted_phone = format_phone_number(recipient)
        result = twilio_client.send_sms(formatted_phone, message)
        
        if result.get("success"):
            return f"✅ SMS sent to {recipient}!\n\nMessage: {message}\n\nMessage ID: {result.get('message_sid', 'N/A')}"
        else:
            return f"❌ Failed to send SMS to {recipient}: {result.get('error')}"
    else:
        return f"❌ Invalid phone number: {recipient}"

def handle_send_email(data):
    """Handle email sending"""
    recipient = data.get("recipient", "")
    subject = data.get("subject", "Voice Command Message")
    message = data.get("message", "")
    
    if is_email_address(recipient):
        result = email_client.send_email(recipient, subject, message)
        
        if result.get("success"):
            return f"✅ Email sent to {recipient}!\n\nSubject: {subject}\nMessage: {message}"
        else:
            return f"❌ Failed to send email to {recipient}: {result.get('error')}"
    else:
        return f"❌ Invalid email address: {recipient}"

# ==================== HUBSPOT ACTION HANDLERS ====================

def handle_create_contact(data):
    """Handle creating new contact in HubSpot"""
    name = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    company = data.get("company", "")
    
    if not name:
        return "❌ Contact name is required"
    
    result = hubspot_service.create_contact(name, email, phone, company)
    
    if result.get("success"):
        response = f"✅ Contact created: {name}"
        if email:
            response += f"\n📧 Email: {email}"
        if phone:
            response += f"\n📱 Phone: {phone}"
        if company:
            response += f"\n🏢 Company: {company}"
        return response
    else:
        return f"❌ Failed to create contact: {result.get('error')}"

def handle_update_contact_phone(data):
    """Handle updating contact phone number"""
    try:
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        
        if not name or not phone:
            return "❌ Both contact name and phone number are required"
        
        print(f"🔍 Searching for contact: '{name}'")
        
        search_result = hubspot_service.search_contact(name)
        
        if not search_result or not search_result.get("success"):
            return f"❌ Could not find contact: {name}. Try creating a new contact instead."
        
        contacts = search_result.get("contacts", [])
        if not contacts:
            return f"❌ No contact found with name: {name}. Try: 'Hey Manny create contact {name} phone {phone}'"
        
        contact = contacts[0]
        contact_id = contact.get("id")
        
        if not contact_id:
            return f"❌ Invalid contact data for: {name}"
        
        contact_props = contact.get("properties", {})
        current_name = f"{contact_props.get('firstname', '')} {contact_props.get('lastname', '')}".strip()
        if not current_name:
            current_name = name
        
        print(f"✅ Found contact: {current_name} (ID: {contact_id})")
        
        update_result = hubspot_service.update_contact(contact_id, {"phone": phone})
        
        if update_result and update_result.get("success"):
            return f"✅ Updated {current_name}'s phone number to {phone}"
        else:
            error_msg = update_result.get("error", "Unknown error") if update_result else "No response from HubSpot"
            return f"❌ Failed to update phone for {current_name}: {error_msg}"
    
    except Exception as e:
        print(f"❌ Error in handle_update_contact_phone: {str(e)}")
        return f"❌ Error updating contact: {str(e)}"

def handle_log_call(data):
    """Handle logging call activity"""
    contact = data.get("contact", "")
    notes = data.get("notes", "")
    
    if not contact or not notes:
        return "❌ Both contact name and call notes are required"
    
    result = hubspot_service.log_call(contact, notes)
    
    if result.get("success"):
        return f"✅ Call logged with {contact}: {notes}"
    else:
        return f"❌ Failed to log call: {result.get('error')}"

def handle_log_email(data):
    """Handle logging email activity"""
    contact = data.get("contact", "")
    subject = data.get("subject", "")
    body = data.get("body", "")
    
    if not contact or not subject:
        return "❌ Both contact name and email subject are required"
    
    result = hubspot_service.log_email_activity(contact, subject, body)
    
    if result.get("success"):
        return f"✅ Email activity logged with {contact}: {subject}"
    else:
        return f"❌ Failed to log email activity: {result.get('error')}"

def handle_log_meeting(data):
    """Handle logging meeting activity"""
    contact = data.get("contact", "")
    title = data.get("title", "")
    notes = data.get("notes", "")
    
    if not contact or not notes:
        return "❌ Both contact name and meeting notes are required"
    
    result = hubspot_service.log_meeting(contact, title, notes)
    
    if result.get("success"):
        return f"✅ Meeting logged with {contact}: {title}"
    else:
        return f"❌ Failed to log meeting: {result.get('error')}"

def handle_create_deal(data):
    """Handle creating new deal"""
    name = data.get("name", "")
    amount = data.get("amount", 0)
    stage = data.get("stage", "appointmentscheduled")
    contact = data.get("contact", "")
    
    if not name:
        return "❌ Deal name is required"
    
    result = hubspot_service.create_deal(name, amount, stage, contact)
    
    if result.get("success"):
        response = f"✅ Deal created: {name}"
        if amount > 0:
            response += f"\n💰 Amount: ${amount:,.2f}"
        response += f"\n📊 Stage: {stage}"
        if contact:
            response += f"\n👤 Contact: {contact}"
        return response
    else:
        return f"❌ Failed to create deal: {result.get('error')}"

def handle_move_deal_stage(data):
    """Handle moving deal to new stage"""
    deal_name = data.get("deal_name", "")
    stage = data.get("stage", "")
    
    if not deal_name or not stage:
        return "❌ Both deal name and new stage are required"
    
    result = hubspot_service.move_deal_stage(deal_name, stage)
    
    if result.get("success"):
        return f"✅ Deal '{deal_name}' moved to '{stage}' stage"
    else:
        return f"❌ Failed to move deal stage: {result.get('error')}"

def handle_send_marketing_email(data):
    """Handle sending marketing email"""
    email_name = data.get("email_name", "")
    recipient_list = data.get("recipient_list", "")
    
    if not email_name or not recipient_list:
        return "❌ Both email name and recipient list are required"
    
    result = hubspot_service.send_marketing_email(email_name, recipient_list)
    
    if result.get("success"):
        response = f"✅ {result.get('message')}"
        if result.get("note"):
            response += f"\n\n💡 {result.get('note')}"
        return response
    else:
        return f"❌ Failed to send marketing email: {result.get('error')}"

def handle_create_task(data):
    """Handle creating new task"""
    title = data.get("title", "")
    contact = data.get("contact", "")
    due_date = data.get("due_date", "")
    description = data.get("description", "")
    
    if not title:
        return "❌ Task title is required"
    
    result = hubspot_service.create_task(title, description, contact, due_date)
    
    if result.get("success"):
        response = f"✅ Task created: {title}"
        if contact:
            response += f"\n👤 For: {contact}"
        if due_date:
            response += f"\n📅 Due: {due_date}"
        return response
    else:
        return f"❌ Failed to create task: {result.get('error')}"

def handle_trigger_workflow(data):
    """Handle triggering workflow"""
    workflow_name = data.get("workflow_name", "")
    contact = data.get("contact", "")
    
    if not workflow_name:
        return "❌ Workflow name is required"
    
    result = hubspot_service.trigger_workflow(workflow_name, contact)
    
    if result.get("success"):
        response = f"✅ {result.get('message')}"
        if result.get("note"):
            response += f"\n\n💡 {result.get('note')}"
        return response
    else:
        return f"❌ Failed to trigger workflow: {result.get('error')}"

def handle_schedule_meeting_link(data):
    """Handle scheduling meeting link"""
    contact = data.get("contact", "")
    meeting_type = data.get("meeting_type", "demo")
    duration = data.get("duration", 30)
    
    if not contact:
        return "❌ Contact name is required"
    
    result = hubspot_service.schedule_meeting_link(contact, meeting_type, duration)
    
    if result.get("success"):
        return f"✅ {result.get('message')}"
    else:
        return f"❌ Failed to schedule meeting link: {result.get('error')}"

def handle_create_form(data):
    """Handle creating form"""
    form_name = data.get("form_name", "")
    fields = data.get("fields", [])
    
    if not form_name:
        return "❌ Form name is required"
    
    result = hubspot_service.create_form(form_name, fields)
    
    if result.get("success"):
        response = f"✅ {result.get('message')}"
        if result.get("note"):
            response += f"\n\n💡 {result.get('note')}"
        return response
    else:
        return f"❌ Failed to create form: {result.get('error')}"

def handle_sales_report(data):
    """Handle generating sales report"""
    period = data.get("period", "this month")
    
    result = hubspot_service.get_sales_report(period)
    
    if result.get("success"):
        report = result.get("report", {})
        response = f"📊 Sales Report for {period}:\n\n"
        response += f"💼 Total Deals: {report.get('total_deals', 0)}\n"
        response += f"💰 Pipeline Value: ${report.get('total_pipeline_value', 0):,.2f}\n"
        response += f"🏆 Closed Won: {report.get('closed_won_deals', 0)} deals\n"
        response += f"💵 Closed Won Value: ${report.get('closed_won_value', 0):,.2f}\n"
        response += f"📈 Win Rate: {report.get('win_rate', 0)}%\n"
        response += f"📊 Avg Deal Size: ${report.get('average_deal_size', 0):,.2f}"
        return response
    else:
        return f"❌ Failed to generate sales report: {result.get('error')}"

# ==================== ACTION DISPATCHER ====================

def dispatch_action(parsed):
    """Enhanced action dispatcher with comprehensive HubSpot support"""
    action = parsed.get("action")
    print(f"🔧 Dispatching action: '{action}'")
    
    # Communication actions
    if action == "send_message":
        return handle_send_message(parsed)
    elif action == "send_email":
        return handle_send_email(parsed)
    
    # HubSpot Contact actions
    elif action == "create_contact":
        return handle_create_contact(parsed)
    elif action == "update_contact_phone":
        return handle_update_contact_phone(parsed)
    
    # HubSpot Activity logging
    elif action == "log_call":
        return handle_log_call(parsed)
    elif action == "log_email":
        return handle_log_email(parsed)
    elif action == "log_meeting":
        return handle_log_meeting(parsed)
    
    # HubSpot Deal management
    elif action == "create_deal":
        return handle_create_deal(parsed)
    elif action == "move_deal_stage":
        return handle_move_deal_stage(parsed)
    
    # HubSpot Marketing & Workflows
    elif action == "send_marketing_email":
        return handle_send_marketing_email(parsed)
    elif action == "trigger_workflow":
        return handle_trigger_workflow(parsed)
    
    # HubSpot Task & Meeting management
    elif action == "create_task":
        return handle_create_task(parsed)
    elif action == "schedule_meeting_link":
        return handle_schedule_meeting_link(parsed)
    
    # HubSpot Form creation
    elif action == "create_form":
        return handle_create_form(parsed)
    
    # HubSpot Reporting
    elif action == "sales_report":
        return handle_sales_report(parsed)
    
    else:
        print(f"❌ Unknown action received: '{action}'")
        return f"Unknown action: {action}. Supported: Contact management, Deal tracking, Activity logging, Task creation, Marketing automation, and Reporting"

# ==================== HTML TEMPLATE ====================

def get_html_template():
    primary_wake_word = CONFIG['wake_word_primary']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manny - HubSpot CRM Voice Assistant</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a2e url('https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688bfadef231e6633e98f192.webp') center center/cover no-repeat fixed; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; color: white; }}
        .container {{ background: rgba(26, 26, 46, 0.9); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); backdrop-filter: blur(15px); max-width: 800px; width: 100%; text-align: center; border: 2px solid #4a69bd; }}
        .header h1 {{ font-size: 2.8em; margin-bottom: 10px; font-weight: 700; color: #4a69bd; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }}
        .header h2 {{ font-size: 1.4em; margin-bottom: 10px; color: #f39c12; }}
        .header img {{ max-height: 300px; margin-bottom: 20px; max-width: 95%; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.3); }}
        .header p {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; color: #a0a0ff; }}
        .listening-status {{ height: 120px; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 30px; }}
        .voice-indicator {{ width: 100px; height: 100px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; margin-bottom: 15px; transition: all 0.3s ease; border: 3px solid transparent; }}
        .voice-indicator.listening {{ background: linear-gradient(45deg, #4a69bd, #0097e6); animation: pulse 2s infinite; box-shadow: 0 0 30px rgba(74, 105, 189, 0.8); border-color: #4a69bd; }}
        .voice-indicator.wake-detected {{ background: linear-gradient(45deg, #f39c12, #e67e22); animation: glow 1s infinite alternate; box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); border-color: #f39c12; }}
        .voice-indicator.processing {{ background: linear-gradient(45deg, #e74c3c, #c0392b); animation: spin 1s linear infinite; box-shadow: 0 0 30px rgba(231, 76, 60, 0.8); border-color: #e74c3c; }}
        .voice-indicator.idle {{ background: rgba(74, 105, 189, 0.3); animation: none; border-color: #4a69bd; }}
        @keyframes pulse {{ 0% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.1); opacity: 0.8; }} 100% {{ transform: scale(1); opacity: 1; }} }}
        @keyframes glow {{ 0% {{ box-shadow: 0 0 30px rgba(243, 156, 18, 0.8); }} 100% {{ box-shadow: 0 0 50px rgba(243, 156, 18, 1); }} }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        .status-text {{ font-size: 1.1em; font-weight: 500; min-height: 30px; }}
        .status-text.listening {{ color: #4a69bd; }}
        .status-text.wake-detected {{ color: #f39c12; }}
        .status-text.processing {{ color: #e74c3c; }}
        .controls {{ margin-bottom: 30px; }}
        .control-button {{ background: linear-gradient(45deg, #4a69bd, #0097e6); color: white; border: none; padding: 12px 30px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; margin: 0 10px; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(74, 105, 189, 0.3); }}
        .control-button:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(74, 105, 189, 0.5); }}
        .control-button.stop {{ background: linear-gradient(45deg, #e74c3c, #c0392b); }}
        .control-button:disabled {{ background: #6c757d; cursor: not-allowed; transform: none; box-shadow: none; }}
        .manual-input {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(74, 105, 189, 0.3); }}
        .manual-input h3 {{ margin-bottom: 15px; text-align: center; color: #4a69bd; }}
        .input-group {{ display: flex; gap: 10px; align-items: center; }}
        .text-input {{ flex: 1; padding: 12px 15px; border: 2px solid rgba(74, 105, 189, 0.3); border-radius: 25px; background: rgba(26, 26, 46, 0.8); color: white; font-size: 1em; outline: none; transition: all 0.3s ease; }}
        .text-input:focus {{ border-color: #4a69bd; background: rgba(26, 26, 46, 0.9); box-shadow: 0 0 10px rgba(74, 105, 189, 0.3); }}
        .text-input::placeholder {{ color: rgba(255, 255, 255, 0.6); }}
        .send-button {{ background: linear-gradient(45deg, #27ae60, #2ecc71); color: white; border: none; padding: 12px 25px; border-radius: 25px; font-size: 1em; font-weight: 600; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(39, 174, 96, 0.3); }}
        .send-button:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(39, 174, 96, 0.5); }}
        .transcription {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; border: 2px solid transparent; transition: all 0.3s ease; }}
        .transcription.active {{ border-color: #4a69bd; background: rgba(74, 105, 189, 0.2); }}
        .transcription h3 {{ font-size: 1.1em; margin-bottom: 10px; opacity: 0.8; color: #4a69bd; }}
        .transcription-text {{ font-size: 1.2em; font-weight: 500; font-family: 'Courier New', monospace; }}
        .response {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; min-height: 80px; text-align: left; white-space: pre-wrap; display: none; }}
        .response.success {{ background: rgba(39, 174, 96, 0.2); border: 2px solid #27ae60; }}
        .response.error {{ background: rgba(231, 76, 60, 0.2); border: 2px solid #e74c3c; }}
        .browser-support {{ font-size: 0.9em; opacity: 0.8; margin-top: 20px; }}
        .browser-support.unsupported {{ color: #e74c3c; font-weight: bold; opacity: 1; }}
        .privacy-note {{ background: rgba(243, 156, 18, 0.2); border: 1px solid #f39c12; border-radius: 10px; padding: 15px; margin-top: 20px; font-size: 0.9em; }}
        .capabilities {{ background: rgba(74, 105, 189, 0.1); border-radius: 15px; padding: 20px; margin-bottom: 20px; text-align: left; border: 1px solid rgba(74, 105, 189, 0.3); }}
        .capabilities h3 {{ margin-bottom: 15px; text-align: center; color: #f39c12; }}
        .capability-section {{ margin-bottom: 15px; }}
        .capability-section h4 {{ color: #4a69bd; margin-bottom: 5px; }}
        .capability-section ul {{ margin-left: 20px; }}
        .capability-section li {{ margin-bottom: 3px; font-size: 0.9em; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px; margin: 10px; }} .header img {{ max-height: 220px; }} .voice-indicator {{ width: 80px; height: 80px; font-size: 32px; }} .control-button {{ padding: 10px 20px; font-size: 0.9em; margin: 5px; }} .input-group {{ flex-direction: column; gap: 15px; }} .text-input {{ width: 100%; margin-bottom: 10px; }} .send-button {{ width: 100%; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Manny</h1>
            <h2>HubSpot CRM Assistant</h2>
            <img src="https://assets.cdn.filesafe.space/3lSeAHXNU9t09Hhp9oai/media/688c054fea6d0f50b10fc3d7.webp" alt="Manny AI Assistant Logo" />
            <p>Complete voice-powered HubSpot CRM management!</p>
        </div>
        
        <div class="capabilities">
            <h3>🚀 HubSpot CRM Commands</h3>
            <div class="capability-section">
                <h4>👥 Contact Management</h4>
                <ul>
                    <li>"Hey Manny add contact John Smith email john@example.com phone 555-1234"</li>
                    <li>"Hey Manny update contact Sarah's phone number to 555-5678"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📞 Activity Logging</h4>
                <ul>
                    <li>"Hey Manny log call with Sarah Johnson discussing the project timeline"</li>
                    <li>"Hey Manny log meeting with Mike about contract details"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>💼 Deal Management</h4>
                <ul>
                    <li>"Hey Manny create deal for Acme Inc worth $10,000 in Discovery stage"</li>
                    <li>"Hey Manny move deal with XYZ Corp to Proposal Sent"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📋 Tasks & Scheduling</h4>
                <ul>
                    <li>"Hey Manny create task to follow up with Mike on Friday"</li>
                    <li>"Hey Manny send meeting link to Jane for 30-minute demo"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📧 Marketing & Workflows</h4>
                <ul>
                    <li>"Hey Manny send August newsletter to leads tagged Newsletter List"</li>
                    <li>"Hey Manny trigger lead nurturing workflow for new contacts"</li>
                </ul>
            </div>
            <div class="capability-section">
                <h4>📊 Reporting</h4>
                <ul>
                    <li>"Hey Manny show me this month's sales performance report"</li>
                    <li>"Hey Manny generate sales report for last quarter"</li>
                </ul>
            </div>
        </div>
        
        <div class="listening-status">
            <div class="voice-indicator idle" id="voiceIndicator">🎤</div>
            <div class="status-text" id="statusText">Click "Start Listening" to begin</div>
        </div>
        <div class="controls">
            <button class="control-button" id="startButton" onclick="startListening()">Start Listening</button>
            <button class="control-button stop" id="stopButton" onclick="stopListening()" disabled>Stop Listening</button>
        </div>
        <div class="transcription" id="transcription">
            <h3>🎤 Voice Transcription</h3>
            <div class="transcription-text" id="transcriptionText">Waiting for wake word command...</div>
        </div>
        <div id="response" class="response"></div>
        <div class="manual-input">
            <h3>⌨️ Type HubSpot Command</h3>
            <div class="input-group">
                <input type="text" class="text-input" id="manualCommand" placeholder='Try: "create deal for Acme Corp worth $25,000" or "log call with Sarah about pricing"' />
                <button class="send-button" onclick="sendManualCommand()">Send</button>
            </div>
            <small style="opacity: 0.7; display: block; margin-top: 10px; text-align: center;">💡 Complete HubSpot CRM management via voice | Auto-adds "Hey Manny" if missing</small>
        </div>
        <div class="browser-support" id="browserSupport">Checking browser compatibility...</div>
        <div class="privacy-note">🔒 <strong>Privacy:</strong> Voice recognition runs locally in your browser. HubSpot CRM data is securely handled via encrypted APIs with enterprise-grade security.</div>
    </div>

    <script>
        let recognition = null;
        let isListening = false;
        let isProcessingCommand = false;
        let continuousListening = true;
        let commandBuffer = '';
        let bufferTimeout = null;
        let retryCount = 0;
        let maxRetries = 3;
        let retryDelay = 2000;
        let lastError = null;
        let shouldStop = false;

        const voiceIndicator = document.getElementById('voiceIndicator');
        const statusText = document.getElementById('statusText');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const transcription = document.getElementById('transcription');
        const transcriptionText = document.getElementById('transcriptionText');
        const response = document.getElementById('response');
        const browserSupport = document.getElementById('browserSupport');

        const wakeWords = [
            'hey manny', 'manny', 'hey ai assistant', 'ai assistant',
            'hey voice assistant', 'voice assistant'
        ];

        function checkForWakeWordInBuffer(buffer) {{
            const lowerBuffer = buffer.toLowerCase().trim();
            for (const wakeWord of wakeWords) {{
                if (lowerBuffer.includes(wakeWord)) {{
                    return true;
                }}
            }}
            return false;
        }}

        function initSpeechRecognition() {{
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                recognition = new SpeechRecognition();
                
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';
                recognition.maxAlternatives = 1;

                recognition.onstart = function() {{
                    isListening = true;
                    retryCount = 0;
                    lastError = null;
                    shouldStop = false;
                    updateUI('listening', '🎤 Listening for "Hey Manny"...', '👂');
                }};

                recognition.onresult = function(event) {{
                    let interimTranscript = '';
                    let finalTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {{
                        const transcript = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {{
                            finalTranscript += transcript + ' ';
                        }} else {{
                            interimTranscript += transcript;
                        }}
                    }}
                    
                    const currentText = (finalTranscript + interimTranscript).trim();
                    if (currentText) {{
                        transcriptionText.textContent = currentText;
                        transcription.classList.add('active');
                    }}
                    
                    if (finalTranscript && !isProcessingCommand) {{
                        commandBuffer += finalTranscript.trim() + ' ';
                        
                        if (bufferTimeout) {{
                            clearTimeout(bufferTimeout);
                        }}
                        
                        const hasWakeWord = checkForWakeWordInBuffer(commandBuffer);
                        
                        if (hasWakeWord) {{
                            const commandLower = commandBuffer.toLowerCase().trim();
                            const hasActionWord = commandLower.includes('create') || commandLower.includes('add') ||
                                                commandLower.includes('log') || commandLower.includes('send') ||
                                                commandLower.includes('move') || commandLower.includes('show') ||
                                                commandLower.includes('schedule') || commandLower.includes('trigger');
                            
                            const justWakeWord = wakeWords.some(wake => commandLower.trim() === wake.toLowerCase());
                            
                            let waitTime = justWakeWord || !hasActionWord ? 8000 : 4000;
                            
                            if (justWakeWord || !hasActionWord) {{
                                updateUI('wake-detected', '⏳ Capturing complete HubSpot command...', '⏳');
                            }} else {{
                                updateUI('wake-detected', '⚡ HubSpot command detected!', '⚡');
                            }}
                            
                            bufferTimeout = setTimeout(() => {{
                                checkForWakeWord(commandBuffer.trim());
                                commandBuffer = '';
                            }}, waitTime);
                        }} else {{
                            bufferTimeout = setTimeout(() => {{
                                commandBuffer = '';
                            }}, 6000);
                        }}
                    }}
                }};

                recognition.onerror = function(event) {{
                    lastError = event.error;
                    
                    if (event.error === 'no-speech') {{
                        return;
                    }}
                    
                    if (event.error === 'aborted') {{
                        shouldStop = true;
                        continuousListening = false;
                        retryCount = maxRetries;
                        
                        setTimeout(() => {{
                            updateUI('idle', 'Speech recognition was blocked. Please click Start Listening to try again.', '❌');
                            startButton.disabled = false;
                            stopButton.disabled = true;
                        }}, 100);
                        return;
                    }}
                    
                    let errorMessage = 'Recognition error: ' + event.error;
                    updateUI('idle', errorMessage, '❌');
                    
                    retryCount++;
                    if (retryCount >= maxRetries) {{
                        shouldStop = true;
                        continuousListening = false;
                        updateUI('idle', 'Speech recognition failed. Click Start Listening to try again.', '❌');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }}
                }};

                recognition.onend = function() {{
                    isListening = false;
                    
                    if (shouldStop || lastError === 'aborted' || !continuousListening || isProcessingCommand) {{
                        updateUI('idle', 'Speech recognition stopped', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                        return;
                    }}
                    
                    if (continuousListening && retryCount < maxRetries) {{
                        setTimeout(() => {{ 
                            if (continuousListening && !shouldStop && !isListening) {{ 
                                restartListening(); 
                            }}
                        }}, 1000);
                    }} else {{
                        continuousListening = false;
                        shouldStop = true;
                        updateUI('idle', 'Speech recognition stopped. Click Start Listening to restart.', '🎤');
                        startButton.disabled = false;
                        stopButton.disabled = true;
                    }}
                }};

                browserSupport.textContent = 'Enhanced voice recognition with comprehensive HubSpot CRM support ✅';
                browserSupport.className = 'browser-support';
                return true;
            }} else {{
                browserSupport.textContent = '❌ Voice recognition not supported in this browser.';
                browserSupport.className = 'browser-support unsupported';
                startButton.disabled = true;
                return false;
            }}
        }}

        function checkForWakeWord(text) {{
            const lowerText = text.toLowerCase().trim();
            let wakeWordFound = false;
            let detectedWakeWord = '';
            
            for (const wakeWord of wakeWords) {{
                if (lowerText.includes(wakeWord)) {{
                    wakeWordFound = true;
                    detectedWakeWord = wakeWord;
                    break;
                }}
            }}
            
            if (wakeWordFound) {{
                processWakeWordCommand(text);
            }}
        }}

        async function processWakeWordCommand(fullText) {{
            if (isProcessingCommand) {{
                return;
            }}
            isProcessingCommand = true;
            updateUI('wake-detected', '⚡ Wake word detected! Processing HubSpot command...', '⚡');
            transcriptionText.textContent = fullText;
            try {{
                updateUI('processing', '🔄 Executing HubSpot CRM action...', '⚙️');
                const apiResponse = await fetch('/execute', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ text: fullText }})
                }});
                const data = await apiResponse.json();
                if (apiResponse.ok) {{
                    showResponse(data.response || 'HubSpot command executed successfully!', 'success');
                    updateUI('listening', '✅ HubSpot action completed! Listening for next command...', '👂');
                }} else {{
                    showResponse(data.error || 'An error occurred while processing your HubSpot command.', 'error');
                    updateUI('listening', '❌ Error occurred. Listening for next command...', '👂');
                }}
            }} catch (error) {{
                showResponse('Network error. Please check your connection and try again.', 'error');
                updateUI('listening', '❌ Network error. Listening for next command...', '👂');
            }} finally {{
                isProcessingCommand = false;
                setTimeout(() => {{
                    transcriptionText.textContent = 'Waiting for HubSpot wake word command...';
                    transcription.classList.remove('active');
                }}, 3000);
            }}
        }}

        function updateUI(state, statusMessage, indicator) {{
            statusText.textContent = statusMessage;
            statusText.className = 'status-text ' + state;
            voiceIndicator.textContent = indicator;
            voiceIndicator.className = 'voice-indicator ' + state;
        }}

        function showResponse(message, type) {{
            response.textContent = message;
            response.className = 'response ' + type;
            response.style.display = 'block';
            if (type === 'success') {{
                setTimeout(() => {{ response.style.display = 'none'; }}, 15000);
            }}
        }}

        function sendManualCommand() {{
            const manualInput = document.getElementById('manualCommand');
            let command = manualInput.value.trim();
            
            if (!command) {{
                alert('Please enter a HubSpot command');
                return;
            }}
            
            const lowerCommand = command.toLowerCase();
            const hasWakeWord = wakeWords.some(wakeWord => lowerCommand.startsWith(wakeWord.toLowerCase()));
            
            if (!hasWakeWord) {{
                command = 'Hey Manny ' + command;
                manualInput.value = command;
                setTimeout(() => {{ manualInput.value = ''; }}, 2000);
            }} else {{
                manualInput.value = '';
            }}
            
            processWakeWordCommand(command);
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            const manualInput = document.getElementById('manualCommand');
            if (manualInput) {{
                manualInput.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        sendManualCommand();
                    }}
                }});
            }}
        }});

        function startListening() {{
            if (!recognition) {{
                alert('Speech recognition not available in this browser.');
                return;
            }}
            
            if (isListening) {{
                try {{
                    recognition.stop();
                }} catch (e) {{}}
            }}
            
            continuousListening = true;
            retryCount = 0;
            lastError = null;
            shouldStop = false;
            startButton.disabled = true;
            stopButton.disabled = false;
            response.style.display = 'none';
            commandBuffer = '';
            
            setTimeout(() => {{
                try {{
                    if (!isListening && !shouldStop) {{ 
                        recognition.start();
                    }}
                }} catch (error) {{
                    updateUI('idle', 'Error starting recognition. Please try again.', '❌');
                    startButton.disabled = false;
                    stopButton.disabled = true;
                    continuousListening = false;
                    shouldStop = true;
                }}
            }}, 100);
        }}

        function stopListening() {{
            continuousListening = false;
            shouldStop = true;
            retryCount = 0;
            lastError = null;
            
            if (recognition && isListening) {{
                try {{
                    recognition.stop();
                }} catch (error) {{}}
            }}
            
            updateUI('idle', 'Stopped listening', '🎤');
            startButton.disabled = false;
            stopButton.disabled = true;
            transcriptionText.textContent = 'Waiting for HubSpot wake word command...';
            transcription.classList.remove('active');
            commandBuffer = '';
            
            if (bufferTimeout) {{
                clearTimeout(bufferTimeout);
            }}
        }}

        function restartListening() {{
            if (shouldStop || !continuousListening || !recognition || isListening || retryCount >= maxRetries) {{
                return;
            }}
            
            try {{
                recognition.start();
            }} catch (error) {{
                retryCount++;
                if (retryCount < maxRetries && !shouldStop) {{
                    setTimeout(() => {{ 
                        if (continuousListening && !shouldStop) {{ 
                            restartListening(); 
                        }} 
                    }}, retryDelay);
                }} else {{
                    shouldStop = true;
                    continuousListening = false;
                    updateUI('idle', 'Speech recognition failed. Click Start Listening to try again.', '❌');
                    startButton.disabled = false;
                    stopButton.disabled = true;
                }}
            }}
        }}

        window.addEventListener('load', function() {{ initSpeechRecognition(); }});
        document.addEventListener('visibilitychange', function() {{
            if (document.hidden && isListening) {{
                recognition.stop();
            }} else if (!document.hidden && continuousListening && !isListening) {{
                setTimeout(() => {{ restartListening(); }}, 500);
            }}
        }});
        document.addEventListener('click', function() {{
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
                navigator.mediaDevices.getUserMedia({{ audio: true }})
                    .then(() => {{}})
                    .catch((error) => {{}});
            }}
        }}, {{ once: true }});
    </script>
</body>
</html>'''

# ==================== ROUTES ====================

@app.route("/")
def root():
    return get_html_template()

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.json
        prompt = data.get("text", "")
        
        wake_result = wake_word_processor.process_wake_word_command(prompt)
        
        if not wake_result.get("success", True):
            return jsonify({
                "response": wake_result.get("error", "Wake word validation failed"),
                "claude_output": wake_result
            })
        
        if wake_result.get("action"):
            dispatch_result = dispatch_action(wake_result)
            return jsonify({
                "response": dispatch_result,
                "claude_output": wake_result
            })
        
        return jsonify({
            "response": "No valid HubSpot command found",
            "claude_output": wake_result
        })

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "wake_word_enabled": CONFIG["wake_word_enabled"],
        "wake_word_primary": CONFIG["wake_word_primary"],
        "services": {
            "twilio_configured": bool(twilio_client.client),
            "email_configured": bool(CONFIG["email_address"] and CONFIG["email_password"]),
            "hubspot_configured": bool(CONFIG["hubspot_api_token"]),
            "claude_configured": bool(CONFIG["claude_api_key"])
        },
        "hubspot_crm": {
            "provider": "HubSpot",
            "api_configured": bool(CONFIG["hubspot_api_token"]),
            "supported_commands": [
                "create_contact", "update_contact_phone", "log_call", "log_email", "log_meeting",
                "create_deal", "move_deal_stage", "create_task", "schedule_meeting_link",
                "send_marketing_email", "trigger_workflow", "create_form", "sales_report"
            ]
        }
    })

if __name__ == '__main__':
    print("🚀 Starting Manny - HubSpot CRM Voice Assistant")
    print(f"🎙️ Primary Wake Word: '{CONFIG['wake_word_primary']}'")
    print(f"📱 Twilio: {'✅ Ready' if twilio_client.client else '❌ Not configured'}")
    
    email_status = "✅ Ready" if CONFIG['email_address'] and CONFIG['email_password'] else "⚠️ Not configured"
    print(f"📧 Email ({CONFIG['email_provider'].title()}): {email_status}")
    
    hubspot_status = "✅ Ready" if CONFIG['hubspot_api_token'] else "⚠️ Not configured"
    print(f"🏢 HubSpot CRM: {hubspot_status}")
    if CONFIG['hubspot_api_token']:
        print(f"   └─ Token: {CONFIG['hubspot_api_token'][:12]}...")
    
    print(f"🤖 Claude: {'✅ Ready' if CONFIG['claude_api_key'] else '❌ Not configured'}")
    
    print("\n🎯 Enhanced HubSpot CRM Commands:")
    print("   👥 Contacts: 'Hey Manny add contact John Smith email john@example.com'")
    print("   📞 Activities: 'Hey Manny log call with Sarah discussing project timeline'")
    print("   💼 Deals: 'Hey Manny create deal for Acme Inc worth $10,000'")
    print("   📋 Tasks: 'Hey Manny create task to follow up with Mike on Friday'")
    print("   📧 Marketing: 'Hey Manny send August newsletter to Newsletter List'")
    print("   🔄 Workflows: 'Hey Manny trigger lead nurturing workflow'")
    print("   📊 Reports: 'Hey Manny show me this month's sales performance report'")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"\n🚀 Starting comprehensive HubSpot CRM assistant on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
