"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the src directory to the path so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Store original state
    original_activities = {
        key: {
            "description": value["description"],
            "schedule": value["schedule"],
            "max_participants": value["max_participants"],
            "participants": value["participants"].copy()
        }
        for key, value in activities.items()
    }
    
    yield
    
    # Restore original state
    for key in activities:
        activities[key]["participants"] = original_activities[key]["participants"].copy()


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Basketball Team" in data
    
    def test_get_activities_contains_required_fields(self, client):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_data in data.items():
            assert "description" in activity_data
            assert "schedule" in activity_data
            assert "max_participants" in activity_data
            assert "participants" in activity_data
            assert isinstance(activity_data["participants"], list)
    
    def test_get_activities_participants_are_emails(self, client):
        """Test that participants are valid email addresses"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_data in data.values():
            for participant in activity_data["participants"]:
                assert "@" in participant
                assert ".edu" in participant


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_empty_activity(self, client, reset_activities):
        """Test signing up for an activity with no participants"""
        initial_count = len(activities["Basketball Team"]["participants"])
        
        response = client.post(
            "/activities/Basketball Team/signup",
            params={"email": "test@mergington.edu"}
        )
        
        assert response.status_code == 200
        assert "Signed up" in response.json()["message"]
        assert len(activities["Basketball Team"]["participants"]) == initial_count + 1
        assert "test@mergington.edu" in activities["Basketball Team"]["participants"]
    
    def test_signup_for_activity_with_participants(self, client, reset_activities):
        """Test signing up for an activity that already has participants"""
        response = client.post(
            "/activities/Chess Club/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        
        assert response.status_code == 200
        assert "newstudent@mergington.edu" in activities["Chess Club"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client):
        """Test signing up for an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Club/signup",
            params={"email": "test@mergington.edu"}
        )
        
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_cannot_signup_twice(self, client, reset_activities):
        """Test that a student cannot sign up for multiple activities"""
        # Sign up for first activity
        response1 = client.post(
            "/activities/Basketball Team/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response1.status_code == 200
        
        # Try to sign up for second activity
        response2 = client.post(
            "/activities/Soccer Club/signup",
            params={"email": "student@mergington.edu"}
        )
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]
    
    def test_signup_returns_confirmation_message(self, client, reset_activities):
        """Test that signup returns a confirmation message"""
        response = client.post(
            "/activities/Basketball Team/signup",
            params={"email": "newstudent@mergington.edu"}
        )
        
        assert response.status_code == 200
        message = response.json()["message"]
        assert "newstudent@mergington.edu" in message
        assert "Basketball Team" in message


class TestUnregisterFromActivity:
    """Tests for POST /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self, client, reset_activities):
        """Test unregistering a participant from an activity"""
        # Verify participant is there
        assert "michael@mergington.edu" in activities["Chess Club"]["participants"]
        
        response = client.post(
            "/activities/Chess Club/unregister",
            params={"email": "michael@mergington.edu"}
        )
        
        assert response.status_code == 200
        assert "Unregistered" in response.json()["message"]
        assert "michael@mergington.edu" not in activities["Chess Club"]["participants"]
    
    def test_unregister_from_nonexistent_activity(self, client):
        """Test unregistering from an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Club/unregister",
            params={"email": "student@mergington.edu"}
        )
        
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_nonexistent_participant(self, client, reset_activities):
        """Test unregistering a participant who isn't in the activity"""
        response = client.post(
            "/activities/Chess Club/unregister",
            params={"email": "nonexistent@mergington.edu"}
        )
        
        assert response.status_code == 404
        assert "Participant not found" in response.json()["detail"]
    
    def test_unregister_returns_confirmation_message(self, client, reset_activities):
        """Test that unregister returns a confirmation message"""
        response = client.post(
            "/activities/Chess Club/unregister",
            params={"email": "michael@mergington.edu"}
        )
        
        assert response.status_code == 200
        message = response.json()["message"]
        assert "michael@mergington.edu" in message
        assert "Chess Club" in message


class TestRootEndpoint:
    """Tests for GET / endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static HTML"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/static/index.html" in response.headers["location"]


class TestActivityCapacity:
    """Tests for activity capacity constraints"""
    
    def test_can_signup_below_max_capacity(self, client, reset_activities):
        """Test that students can sign up when activity has open spots"""
        # Basketball Team has max 15 participants and currently has 0
        response = client.post(
            "/activities/Basketball Team/signup",
            params={"email": "student1@mergington.edu"}
        )
        assert response.status_code == 200
    
    def test_activity_tracks_participant_count(self, client, reset_activities):
        """Test that participant count is tracked correctly"""
        response = client.get("/activities")
        data = response.json()
        
        # Chess Club should have 2 participants
        assert len(data["Chess Club"]["participants"]) == 2
        
        # Basketball Team should have 0 participants
        assert len(data["Basketball Team"]["participants"]) == 0


class TestEmailValidation:
    """Tests for email parameter validation"""
    
    def test_signup_with_various_email_formats(self, client, reset_activities):
        """Test signup with different email formats"""
        emails = [
            "student@mergington.edu",
            "john.doe@mergington.edu",
            "jane_smith@mergington.edu",
        ]
        
        for i, email in enumerate(emails):
            # Each student signs up for a different activity
            activities_list = ["Basketball Team", "Soccer Club", "Art Club"]
            response = client.post(
                f"/activities/{activities_list[i]}/signup",
                params={"email": email}
            )
            # All should succeed since they're different activities
            assert response.status_code == 200
