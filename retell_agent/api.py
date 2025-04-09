import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = 'https://api.retellai.com/'

class RetellAgentAPI:
    """
    API service class for interacting with Retell Agent API
    """
    
    @staticmethod
    def get_headers():
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.RETELL_API_KEY}'
        }
    
    @classmethod
    def get_agent(cls, agent_id):
        """
        Fetch agent details from Retell API
        """
        try:
            response = requests.get(
                f'{BASE_URL}/get-agent/{agent_id}',
                headers=cls.get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Error fetching agent details: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error fetching agent: {str(e)}")
            return None
    
    @classmethod
    def get_llm(cls, llm_id):
        """
        Fetch LLM details from Retell API
        """
        try:
            response = requests.get(
                f'{BASE_URL}/get-retell-llm/{llm_id}',
                headers=cls.get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Error fetching LLM details: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error fetching LLM: {str(e)}")
            return None
    
    @classmethod
    def update_agent(cls, agent_id, agent_data):
        """
        Update agent details via Retell API
        """
        try:
            response = requests.patch(
                f'{BASE_URL}/update-agent/{agent_id}',
                json=agent_data,
                headers=cls.get_headers(),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                return True, "Agent updated successfully"
            else:
                error_msg = f"Error updating agent: {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error updating agent: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    @classmethod
    def update_llm(cls, llm_id, llm_data):
        """
        Update LLM details via Retell API
        """
        try:
            response = requests.patch(
                f'{BASE_URL}/update-retell-llm/{llm_id}',
                json=llm_data,
                headers=cls.get_headers(),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                return True, "LLM updated successfully"
            else:
                error_msg = f"Error updating LLM: {response.text}"
                logger.error(error_msg)
                return False, error_msg
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error updating LLM: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
