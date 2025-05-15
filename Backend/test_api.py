import requests
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_test_results.log"),
        logging.StreamHandler()
    ]
)

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"

# Test token
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzE2MzU5NjAwfQ.S6FPv8-YpRCTYybNhpxu5qjIq_sGFbCZQw8tAxbSMa0"

def test_auth_me():
    """Test /auth/me endpoint"""
    logging.info("Testing /auth/me endpoint...")
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    try:
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        logging.info(f"Status code: {response.status_code}")
        if response.status_code == 200:
            logging.info(json.dumps(response.json(), indent=2))
        else:
            logging.error(f"Error: {response.text}")
        return response.status_code
    except Exception as e:
        logging.error(f"Exception: {str(e)}")
        return None

def test_chat_sessions():
    """Test /chat/sessions endpoint"""
    logging.info("Testing /chat/sessions endpoint...")
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    try:
        response = requests.get(f"{BASE_URL}/chat/sessions", headers=headers)
        logging.info(f"Status code: {response.status_code}")
        if response.status_code == 200:
            logging.info(json.dumps(response.json(), indent=2))
        else:
            logging.error(f"Error: {response.text}")
        return response.status_code
    except Exception as e:
        logging.error(f"Exception: {str(e)}")
        return None

def test_chat_settings():
    """Test /chat/settings endpoint"""
    logging.info("Testing /chat/settings endpoint...")
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    try:
        response = requests.get(f"{BASE_URL}/chat/settings", headers=headers)
        logging.info(f"Status code: {response.status_code}")
        if response.status_code == 200:
            logging.info(json.dumps(response.json(), indent=2))
        else:
            logging.error(f"Error: {response.text}")
        return response.status_code
    except Exception as e:
        logging.error(f"Exception: {str(e)}")
        return None

# Add a test for the visualization endpoint
def test_visualization_endpoint(client, authenticate_client):
    # First authenticate
    auth_token = authenticate_client()
    
    # Test the visualization endpoint
    response = client.get(
        "/api/v1/visualization/ad-performance-segments?start_date=2023-01-01&end_date=2023-01-31",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Assert that the response is successful and contains expected data
    assert response.status_code == 200
    assert "figure" in response.json() or "message" in response.json()

if __name__ == "__main__":
    logging.info("Starting API tests...")
    auth_result = test_auth_me()
    sessions_result = test_chat_sessions()
    settings_result = test_chat_settings()
    
    # Summary
    logging.info("\nTest Summary:")
    logging.info(f"Auth endpoint: {'SUCCESS' if auth_result == 200 else 'FAILED'}")
    logging.info(f"Chat sessions endpoint: {'SUCCESS' if sessions_result == 200 else 'FAILED'}")
    logging.info(f"Chat settings endpoint: {'SUCCESS' if settings_result == 200 else 'FAILED'}")
    logging.info("All results logged to api_test_results.log") 