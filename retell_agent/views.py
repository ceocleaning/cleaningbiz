from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from .models import RetellAgent, RetellLLM
import requests
import json
import os
import logging
from django.urls import reverse
from retell import Retell

logger = logging.getLogger(__name__)

BASE_URL = settings.RETELL_BASE_URL
API_KEY = settings.RETELL_API_KEY

@login_required
def setup_retell_agent(request):
    """
    View to display and handle the Retell agent setup form.
    """
    # Check if llm_id is provided in the URL parameters
    llm_id = request.GET.get('llm_id', '')
    
    # Get the user's business
    business = request.user.business_set.first()

    from usage_analytics.services.usage_service import UsageService
    check_limit = UsageService.check_active_agents_limit(business)
    if check_limit.get('exceeded'):
        messages.error(request, 'You have reached the maximum number of Retell agents allowed in your subscription plan.')
        return redirect('list_retell_agents')
    
    # Check if business has any existing LLMs (if llm_id not provided)
    existing_llm = None
    if not llm_id:
        existing_llm = RetellLLM.objects.filter(business=business).first()
        if existing_llm:
            llm_id = existing_llm.llm_id
            logger.info(f"Using existing LLM with ID {llm_id} for setup form")
    
    if request.method == 'POST':
        try:
            # Get the form data
            agent_name = request.POST.get('agent_name', '').strip()
            llm_id = request.POST.get('llm_id', '').strip()
            voice_id = request.POST.get('voice_id', '11labs-Adrian').strip()
            voice_model = request.POST.get('voice_model', 'eleven_turbo_v2').strip()
            
            if not agent_name or not llm_id:
                messages.error(request, "Agent name and LLM ID are required")
                return render(request, 'retell_agent/setup_agent.html', {'llm_id': llm_id, 'existing_llm': existing_llm})
            
            # Voice model compatibility mapping
            voice_model_compatibility = {
                # Elevenlabs voices
                "11labs-": {
                    "compatible_models": [
                        "eleven_turbo_v2", 
                        "eleven_flash_v2", 
                        "eleven_turbo_v2_5", 
                        "eleven_flash_v2_5", 
                        "eleven_multilingual_v2"
                    ],
                    "default_model": "eleven_turbo_v2"
                },
                # OpenAI voices
                "openai-": {
                    "compatible_models": ["openai_tts"],
                    "default_model": "openai_tts"
                },
                # Deepgram voices
                "deepgram-": {
                    "compatible_models": ["deepgram_aura"],
                    "default_model": "deepgram_aura"
                },
                # PlayHT voices
                "play-": {
                    "compatible_models": ["Play3.0-mini", "PlayDialog"],
                    "default_model": "Play3.0-mini"
                }
            }
            
            # Check voice model compatibility and adjust if needed
            voice_prefix = None
            for prefix in voice_model_compatibility:
                if voice_id.startswith(prefix):
                    voice_prefix = prefix
                    break
            
            if voice_prefix:
                compatible_models = voice_model_compatibility[voice_prefix]['compatible_models']
                if voice_model not in compatible_models:
                    # Use the default model for this voice provider
                    logger.warning(f"Voice model {voice_model} not compatible with voice {voice_id}. Using default model {voice_model_compatibility[voice_prefix]['default_model']} instead.")
                    voice_model = voice_model_compatibility[voice_prefix]['default_model']
            
            # Construct the payload directly
            payload = {
                "response_engine": {
                    "type": "retell-llm",
                    "llm_id": llm_id
                },
                "agent_name": agent_name,
                "voice_id": voice_id,
                "voice_model": voice_model,
                "fallback_voice_ids": ["openai-Alloy"],
                "voice_temperature": 1,
                "voice_speed": 1,
                "volume": 1,
                "responsiveness": 1,
                "interruption_sensitivity": 1,
                "enable_backchannel": True,
                "backchannel_frequency": 0.8,
                "backchannel_words": ["yeah", "uh-huh"],
                "language": "en-US",
                "enable_transcription_formatting": True,
                "normalize_for_speech": True
            }
            
            # Add your Retell API key
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            }
            
            # Make the API request to create the agent
            logger.info(f"Creating agent with payload: {json.dumps(payload)}")
            response = requests.post(
                f'{BASE_URL}/create-agent',
                json=payload,
                headers=headers
            )
            
            # Check if the request was successful (status code 200 or 201)
            if response.status_code in [200, 201]:
                response_data = response.json()
                
                # Log successful response
                logger.info(f"Agent created successfully: {response_data}")
                
                # Verify we have an agent_id
                if 'agent_id' not in response_data:
                    logger.error(f"Missing agent_id in response: {response_data}")
                    messages.error(request, f"Error creating agent: Missing agent_id in response")
                    return render(request, 'retell_agent/setup_agent.html', {'llm_id': llm_id, 'existing_llm': existing_llm})
                
                # Get the LLM record
                try:
                    llm = RetellLLM.objects.get(llm_id=llm_id)
                except RetellLLM.DoesNotExist:
                    # If LLM doesn't exist in our database, create a minimal record
                    llm = RetellLLM(
                        business=business,
                        llm_id=llm_id,
                        model="Unknown"  # We don't know the model type from agent creation
                    )
                    llm.save()
                
                # Save the agent to the database
                agent = RetellAgent(
                    business=business,
                    agent_id=response_data.get('agent_id'),
                    agent_name=response_data.get('agent_name'),
                    llm=llm,
                    voice_id=response_data.get('voice_id')
                )
                agent.save()
                
                # Track the active agent in usage metrics
                from usage_analytics.services.usage_service import UsageService
                UsageService.track_active_agent(business)
                
                messages.success(request, 'Retell Agent created successfully!')
                return redirect('list_retell_agents')  # Redirect to agent list
            else:
                error_msg = f"Error creating Retell Agent: {response.text}"
                logger.error(error_msg)
                messages.error(request, error_msg)
                return render(request, 'retell_agent/setup_agent.html', {'llm_id': llm_id, 'existing_llm': existing_llm})
                
        except Exception as e:
            logger.exception("Error creating Retell Agent")
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'retell_agent/setup_agent.html', {'llm_id': llm_id, 'existing_llm': existing_llm})
    
    # GET request - display the form
    # If we have an existing LLM, pass it to the template
    if not existing_llm and llm_id:
        try:
            existing_llm = RetellLLM.objects.get(llm_id=llm_id)
        except RetellLLM.DoesNotExist:
            pass
    
    return render(request, 'retell_agent/setup_agent.html', {
        'llm_id': llm_id, 
        'existing_llm': existing_llm
    })

@login_required
def create_retell_llm(request):
    """
    View to automatically create a Retell LLM with default settings.
    """
    # Get the user's business
    business = request.user.business_set.first()
    
    # Check if business already has an LLM
    existing_llm = RetellLLM.objects.filter(business=business).first()
    if existing_llm:
        print(f"Business already has an LLM with ID {existing_llm.llm_id}")
        messages.info(request, "Using existing LLM configuration")
        return redirect(f'{reverse("setup_retell_agent")}?llm_id={existing_llm.llm_id}')
    
    try:
        from .prompt_and_tools import get_retell_prompt, get_retell_tools
        
        # Define default LLM configuration with custom tools included
        payload = {
            "model": "gpt-4o",
            "model_temperature": 0.7,
            "model_high_priority": False,
            "tool_call_strict_mode": True,
            "general_prompt": get_retell_prompt(business),
            "general_tools": get_retell_tools(business),
            "begin_message": "Hello, this is your cleaning service virtual assistant. How can I help you today?",
            "default_dynamic_variables": {
                "business_name": business.name if hasattr(business, 'name') else "Cleaning Service",
            }
        }
        
        # Add your Retell API key
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.RETELL_API_KEY}'
        }
        
        print(f"Creating auto-configured LLM with custom tools")
        
        # Make the API request to create the LLM
        response = requests.post(
            'https://api.retellai.com/create-retell-llm',
            json=payload,
            headers=headers,
            timeout=20
        )
        
        # Check the response
        if response.status_code in [200, 201, 202]:
            response_data = response.json()
            # Try both possible key names for LLM ID
            llm_id = response_data.get('retell_llm_id') or response_data.get('llm_id')
            
            if not llm_id:
                error_message = f"LLM ID not found in response: {response_data}"
                print(error_message)
                messages.error(request, error_message)
                return redirect('setup_retell_agent')
            
            print(f"Successfully created LLM with ID: {llm_id}")
            
            # Save the LLM to our database
            retell_llm = RetellLLM(
                llm_id=llm_id,
                business=business,
                model=payload['model'],
                general_prompt=payload['general_prompt']
            )
            retell_llm.save()
            
            messages.success(request, "LLM was created successfully")
            return redirect(f'{reverse("setup_retell_agent")}?llm_id={llm_id}')
        else:
            error_message = f"Failed to create LLM. Retell API responded with status code {response.status_code}: {response.text}"
            print(error_message)
            messages.error(request, error_message)
            return redirect('setup_retell_agent')
            
    except requests.exceptions.RequestException as e:
        print(f"Network error creating LLM: {str(e)}")
        messages.error(request, f"Network error: {str(e)}")
        return redirect('setup_retell_agent')
    except Exception as e:
        print(f"Error creating LLM: {str(e)}")
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('setup_retell_agent')

@login_required
def list_retell_voices(request):
    """
    View to list available Retell voices.
    """
    try:
        # Add your Retell API key
        headers = {
            'Authorization': f'Bearer {API_KEY}'
        }
        
        # Make the API request to list voices
        response = requests.get(
            f'{BASE_URL}/list-voices',
            headers=headers
        )
        
        # Return the response as JSON
        return JsonResponse(response.json(), safe=False)
            
    except Exception as e:
        logger.exception("Error listing Retell voices")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def list_retell_agents(request):
    """
    View to display all Retell agents for the current business.
    """
    # Get the user's business
    business = request.user.business_set.first()
    agent_limit_reached = False

    from usage_analytics.services.usage_service import UsageService
    check_limit = UsageService.check_active_agents_limit(business)
    if check_limit.get('exceeded'):
        agent_limit_reached = True
    
    # Get all agents for this business
    agents = RetellAgent.objects.filter(business=business).order_by('-created_at')
    
    return render(request, 'retell_agent/list_agents.html', {
        'agents': agents,
        'agent_limit_reached': agent_limit_reached
    })

@login_required
def update_retell_agent(request, agent_id):
    """
    View to update a Retell agent and its associated LLM.
    """
    # Get the user's business
    business = request.user.business_set.first()
    
    # Get the agent
    try:
        agent = RetellAgent.objects.get(agent_id=agent_id, business=business)
    except RetellAgent.DoesNotExist:
        messages.error(request, "Agent not found")
        return redirect('list_retell_agents')
    
    # Initialize context
    context = {'agent': agent, 'loading': False}
    
    if request.method == 'POST':
        try:
            # Start database transaction
            with transaction.atomic():
                # Get form data - basic settings
                new_name = request.POST.get('agent_name', '').strip()
                language = request.POST.get('language', 'en-US').strip()
                webhook_url = request.POST.get('webhook_url', '').strip()
                
                # Validate required fields
                if not new_name:
                    messages.error(request, "Agent name is required")
                    return render(request, 'retell_agent/update_agent.html', context)
                
                # Get form data - voice settings
                voice_id = request.POST.get('voice_id', agent.voice_id).strip()
                voice_model = request.POST.get('voice_model', 'eleven_turbo_v2').strip()
                
                # Voice model compatibility mapping
                voice_model_compatibility = {
                    # Elevenlabs voices
                    "11labs-": {
                        "compatible_models": [
                            "eleven_turbo_v2", 
                            "eleven_flash_v2", 
                            "eleven_turbo_v2_5", 
                            "eleven_flash_v2_5", 
                            "eleven_multilingual_v2"
                        ],
                        "default_model": "eleven_turbo_v2"
                    },
                    # OpenAI voices
                    "openai-": {
                        "compatible_models": ["openai_tts"],
                        "default_model": "openai_tts"
                    },
                    # Deepgram voices
                    "deepgram-": {
                        "compatible_models": ["deepgram_aura"],
                        "default_model": "deepgram_aura"
                    },
                    # PlayHT voices
                    "play-": {
                        "compatible_models": ["Play3.0-mini", "PlayDialog"],
                        "default_model": "Play3.0-mini"
                    }
                }
                
                # Check voice model compatibility and adjust if needed
                voice_prefix = None
                for prefix in voice_model_compatibility:
                    if voice_id.startswith(prefix):
                        voice_prefix = prefix
                        break
                
                if voice_prefix:
                    compatible_models = voice_model_compatibility[voice_prefix]['compatible_models']
                    if voice_model not in compatible_models:
                        # Use the default model for this voice provider
                        logger.warning(f"Voice model {voice_model} not compatible with voice {voice_id}. Using default model {voice_model_compatibility[voice_prefix]['default_model']} instead.")
                        voice_model = voice_model_compatibility[voice_prefix]['default_model']
                
                # Process numeric values with error handling
                try:
                    voice_temperature = float(request.POST.get('voice_temperature', 1))
                except (ValueError, TypeError):
                    voice_temperature = 1.0
                    
                try:
                    voice_speed = float(request.POST.get('voice_speed', 1))
                except (ValueError, TypeError):
                    voice_speed = 1.0
                    
                try:
                    volume = float(request.POST.get('volume', 1))
                except (ValueError, TypeError):
                    volume = 1.0
                
                enable_backchannel = 'enable_backchannel' in request.POST
                
                try:
                    backchannel_frequency = float(request.POST.get('backchannel_frequency', 0.8))
                except (ValueError, TypeError):
                    backchannel_frequency = 0.8
                
                # Process lists
                backchannel_words_raw = request.POST.get('backchannel_words', '')
                backchannel_words = [word.strip() for word in backchannel_words_raw.split(',') if word.strip()]
                if not backchannel_words:
                    backchannel_words = ["yeah", "uh-huh"]
                    
                fallback_voice_ids_raw = request.POST.get('fallback_voice_ids', '')
                fallback_voice_ids = [voice.strip() for voice in fallback_voice_ids_raw.split(',') if voice.strip()]
                
                # Ambient sound settings
                ambient_sound = request.POST.get('ambient_sound', '').strip()
                
                # Validate ambient sound against allowed values
                valid_ambient_sounds = ["coffee-shop", "convention-hall", "summer-outdoor", 
                                         "mountain-outdoor", "static-noise", "call-center"]
                if ambient_sound and ambient_sound not in valid_ambient_sounds:
                    ambient_sound = ""  # Reset to empty if invalid
                
                try:
                    ambient_sound_volume = float(request.POST.get('ambient_sound_volume', 0.1))
                except (ValueError, TypeError):
                    ambient_sound_volume = 0.1
                
                # Convert string to int with fallback
                begin_message_delay_raw = request.POST.get('begin_message_delay_ms', '')
                try:
                    begin_message_delay_ms = int(begin_message_delay_raw) * 1000 if begin_message_delay_raw else 1000
                except (ValueError, TypeError):
                    begin_message_delay_ms = 1000
                
                # Get form data - LLM settings
                new_prompt = request.POST.get('llm_prompt', '').strip()
                begin_message = request.POST.get('begin_message', '').strip()
                
                try:
                    model_temperature = float(request.POST.get('model_temperature', 0.7))
                except (ValueError, TypeError):
                    model_temperature = 0.7
                
                # Get form data - advanced settings
                try:
                    responsiveness = float(request.POST.get('responsiveness', 1))
                except (ValueError, TypeError):
                    responsiveness = 1.0
                    
                try:
                    interruption_sensitivity = float(request.POST.get('interruption_sensitivity', 1))
                except (ValueError, TypeError):
                    interruption_sensitivity = 1.0
                
                normalize_for_speech = 'normalize_for_speech' in request.POST
                enable_transcription_formatting = 'enable_transcription_formatting' in request.POST
                opt_out_sensitive_data_storage = 'opt_out_sensitive_data_storage' in request.POST
                
                # Process keywords
                boosted_keywords_raw = request.POST.get('boosted_keywords', '')
                boosted_keywords = [keyword.strip() for keyword in boosted_keywords_raw.split(',') if keyword.strip()]
                
                # Handle time-based settings
                max_call_duration_raw = request.POST.get('max_call_duration_ms', '')
                try:
                    max_call_duration_ms = int(max_call_duration_raw) * 60000 if max_call_duration_raw else 3600000
                except (ValueError, TypeError):
                    max_call_duration_ms = 3600000  # Default 60 minutes
                
                end_call_after_silence_raw = request.POST.get('end_call_after_silence_ms', '')
                try:
                    end_call_after_silence_ms = int(end_call_after_silence_raw) * 1000 if end_call_after_silence_raw else 600000
                except (ValueError, TypeError):
                    end_call_after_silence_ms = 600000  # Default 10 minutes
                
                ring_duration_raw = request.POST.get('ring_duration_ms', '')
                try:
                    ring_duration_ms = int(ring_duration_raw) * 1000 if ring_duration_raw else 30000
                except (ValueError, TypeError):
                    ring_duration_ms = 30000  # Default 30 seconds
                
                reminder_trigger_raw = request.POST.get('reminder_trigger_ms', '')
                try:
                    reminder_trigger_ms = int(reminder_trigger_raw) * 1000 if reminder_trigger_raw else 10000
                except (ValueError, TypeError):
                    reminder_trigger_ms = 10000  # Default 10 seconds
                
                reminder_max_count_raw = request.POST.get('reminder_max_count', '')
                try:
                    reminder_max_count = int(reminder_max_count_raw) if reminder_max_count_raw else 2
                except (ValueError, TypeError):
                    reminder_max_count = 2
                
                # Voicemail settings
                enable_voicemail_detection = 'enable_voicemail_detection' in request.POST
                
                voicemail_detection_timeout_raw = request.POST.get('voicemail_detection_timeout_ms', '')
                try:
                    voicemail_detection_timeout_ms = int(voicemail_detection_timeout_raw) * 1000 if voicemail_detection_timeout_raw else 30000
                except (ValueError, TypeError):
                    voicemail_detection_timeout_ms = 30000  # Default 30 seconds
                
                voicemail_message = request.POST.get('voicemail_message', 'Hi, please give us a callback.').strip()
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {settings.RETELL_API_KEY}'
                }
                
                # 1. Update LLM if applicable
                if agent.llm and new_prompt:
                    logger.info(f"Preparing to update LLM {agent.llm.llm_id}")
                    
                    # We only need to update the fields we're changing
                    llm_update_data = {
                        'general_prompt': new_prompt
                    }
                    
                    # Add optional fields only if they have values
                    if begin_message:
                        llm_update_data['begin_message'] = begin_message
                        
                    # Always include model_temperature
                    llm_update_data['model_temperature'] = model_temperature
                    
                    # Make the update request
                    logger.info(f"Updating LLM {agent.llm.llm_id} with PATCH")
                    try:
                        llm_update_response = requests.patch(
                            f'{BASE_URL}/update-retell-llm/{agent.llm.llm_id}',
                            json=llm_update_data,
                            headers=headers,
                            timeout=10  # Add timeout
                        )
                        
                        if llm_update_response.status_code in [200, 201, 204]:
                            logger.info(f"LLM {agent.llm.llm_id} updated successfully")
                            # Update the local database
                            agent.llm.general_prompt = new_prompt
                            agent.llm.save()
                        else:
                            error_msg = f"Error updating LLM: {llm_update_response.text}"
                            logger.error(error_msg)
                            messages.warning(request, error_msg)
                            
                    except requests.exceptions.RequestException as e:
                        error_msg = f"Network error updating LLM: {str(e)}"
                        logger.error(error_msg)
                        messages.warning(request, error_msg)
                
                # 2. Update the agent
                # Prepare agent update data with only fields we're changing
                agent_update_data = {
                    'agent_name': new_name,
                    'voice_id': voice_id,
                    'voice_model': voice_model,
                    'voice_temperature': voice_temperature,
                    'voice_speed': voice_speed,
                    'volume': volume,
                    'enable_backchannel': enable_backchannel,
                    'backchannel_frequency': backchannel_frequency,
                    'backchannel_words': backchannel_words,
                    'language': language,
                    'responsiveness': responsiveness,
                    'interruption_sensitivity': interruption_sensitivity,
                    'normalize_for_speech': normalize_for_speech,
                    'enable_transcription_formatting': enable_transcription_formatting,
                    'max_call_duration_ms': max_call_duration_ms,
                    'end_call_after_silence_ms': end_call_after_silence_ms,
                    'opt_out_sensitive_data_storage': opt_out_sensitive_data_storage,
                    'begin_message_delay_ms': begin_message_delay_ms,
                    'ring_duration_ms': ring_duration_ms,
                    'reminder_trigger_ms': reminder_trigger_ms,
                    'reminder_max_count': reminder_max_count,
                    'enable_voicemail_detection': enable_voicemail_detection,
                    'voicemail_detection_timeout_ms': voicemail_detection_timeout_ms,
                    'voicemail_message': voicemail_message
                }
                
                # Optional fields (only include if they have values)
                if fallback_voice_ids:
                    agent_update_data['fallback_voice_ids'] = fallback_voice_ids
                    
                # Only include ambient sound if it's a valid non-empty value
                if ambient_sound:
                    agent_update_data['ambient_sound'] = ambient_sound
                    agent_update_data['ambient_sound_volume'] = ambient_sound_volume
                    
                if boosted_keywords:
                    agent_update_data['boosted_keywords'] = boosted_keywords
                    
                if webhook_url:
                    agent_update_data['webhook_url'] = webhook_url
                
                # Make the update request
                logger.info(f"Updating agent {agent_id} with PATCH")
                try:
                    update_response = requests.patch(
                        f'{BASE_URL}/update-agent/{agent_id}',
                        json=agent_update_data,
                        headers=headers,
                        timeout=10  # Add timeout
                    )
                    
                    if update_response.status_code in [200, 201, 204]:
                        # Update local DB with essential fields
                        agent.agent_name = new_name
                        agent.voice_id = voice_id
                        agent.save()
                        
                        logger.info(f"Agent {agent_id} updated successfully")
                        messages.success(request, "Agent updated successfully with all settings")
                        return redirect('list_retell_agents')
                    else:
                        error_msg = f"Error updating agent: {update_response.text}"
                        logger.error(error_msg)
                        messages.error(request, error_msg)
                        context['agent'] = agent  # Refresh with updated data
                        return render(request, 'retell_agent/update_agent.html', context)
                
                except requests.exceptions.RequestException as e:
                    error_msg = f"Network error updating agent: {str(e)}"
                    logger.error(error_msg)
                    messages.error(request, error_msg)
                    return render(request, 'retell_agent/update_agent.html', context)
                
        except Exception as e:
            logger.exception("Error updating Retell Agent")
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'retell_agent/update_agent.html', context)
    
    # GET request - fetch latest data from API
    context['loading'] = True
    
    try:
        # Fetch agent details from Retell API
        headers = {
            'Authorization': f'Bearer {settings.RETELL_API_KEY}'
        }
        
        logger.info(f"Fetching agent details from Retell API for agent {agent_id}")
        try:
            agent_response = requests.get(
                f'{BASE_URL}/get-agent/{agent_id}',
                headers=headers,
                timeout=10  # Add timeout
            )
            
            if agent_response.status_code == 200:
                agent_data = agent_response.json()
                
                # Update local agent data with fresh API data
                agent.agent_name = agent_data.get('agent_name', agent.agent_name)
                agent.voice_id = agent_data.get('voice_id', agent.voice_id)
                
                # Also fetch LLM details if available
                llm_id = agent_data.get('response_engine', {}).get('llm_id')
                
                if llm_id:
                    logger.info(f"Fetching LLM details from Retell API for LLM {llm_id}")
                    try:
                        llm_response = requests.get(
                            f'{BASE_URL}/get-retell-llm/{llm_id}',
                            headers=headers,
                            timeout=10  # Add timeout
                        )
                        
                        if llm_response.status_code == 200:
                            llm_data = llm_response.json()
                            
                            # Update or create the LLM record
                            if agent.llm and agent.llm.llm_id == llm_id:
                                agent.llm.model = llm_data.get('model', agent.llm.model)
                                agent.llm.general_prompt = llm_data.get('general_prompt', agent.llm.general_prompt)
                                agent.llm.save()
                            else:
                                # LLM ID changed or doesn't exist, create/update
                                try:
                                    llm = RetellLLM.objects.get(llm_id=llm_id)
                                except RetellLLM.DoesNotExist:
                                    llm = RetellLLM(
                                        business=business,
                                        llm_id=llm_id,
                                        model=llm_data.get('model', 'Unknown'),
                                        general_prompt=llm_data.get('general_prompt', '')
                                    )
                                    llm.save()
                                
                                agent.llm = llm
                                agent.save()
                            
                            # Add agent and LLM details to context
                            context['llm_data'] = llm_data
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Network error fetching LLM: {str(e)}")
                        messages.warning(request, f"Could not retrieve latest LLM details: {str(e)}")
                
                # Add complete agent data to context
                context['agent_data'] = agent_data
            else:
                logger.warning(f"Error fetching agent details: {agent_response.text}")
                messages.warning(request, f"Using cached agent data, could not fetch latest from Retell")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error fetching agent: {str(e)}")
            messages.warning(request, f"Using cached agent data, network error: {str(e)}")
            
    except Exception as e:
        logger.exception("Error fetching Retell data")
        messages.warning(request, f"Using cached data. Could not connect to Retell API: {str(e)}")
    
    # Display the form with the agent data
    context['loading'] = False
    return render(request, 'retell_agent/update_agent.html', context)

@login_required
def delete_retell_agent(request, agent_id):
    """
    View to delete a Retell agent and its associated LLM.
    """
    # Get the user's business
    business = request.user.business_set.first()
    
    # Get the agent
    try:
        agent = RetellAgent.objects.get(agent_id=agent_id, business=business)
    except RetellAgent.DoesNotExist:
        messages.error(request, "Agent not found")
        return redirect('list_retell_agents')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Store info for logging
                agent_name = agent.agent_name
                
                # Store the LLM ID if it exists
                llm_id = None
                llm_other_agents_count = 0
                
                if agent.llm:
                    llm_id = agent.llm.llm_id
                    # Check if any other agents are using this LLM
                    llm_other_agents_count = RetellAgent.objects.filter(
                        llm=agent.llm
                    ).exclude(agent_id=agent_id).count()
                
                # Initialize Retell SDK client
                client = Retell(api_key=settings.RETELL_API_KEY)
                
                print(f"Sending delete request for agent {agent_id}")
                try:
                    # Delete agent using SDK
                    client.agent.delete(agent_id)
                    print(f"Agent {agent_id} successfully deleted from Retell API")
                    agent_deletion_success = True
                except Exception as e:
                    agent_deletion_success = False
                    warning_msg = f"Error deleting agent from Retell API: {str(e)}"
                    print(warning_msg)
                    messages.warning(request, warning_msg)
                
                # Delete agent from database
                agent.delete()
                print(f"Deleted agent {agent_id} ({agent_name}) from local database")
                
                # If LLM exists and no other agents are using it, delete it from Retell and DB
                if llm_id and llm_other_agents_count == 0:
                    print(f"Sending delete request for LLM {llm_id}")
                    try:
                        # Delete LLM using SDK
                        client.llm.delete(llm_id)
                        print(f"LLM {llm_id} successfully deleted from Retell API")
                        llm_deletion_success = True
                    except Exception as e:
                        llm_deletion_success = False
                        warning_msg = f"Error deleting LLM from Retell API: {str(e)}"
                        print(warning_msg)
                        messages.warning(request, warning_msg)
                    
                    # Delete the LLM from our database
                    RetellLLM.objects.filter(llm_id=llm_id).delete()
                    print(f"Deleted LLM {llm_id} from local database")
                
                # Create appropriate success message
                if llm_id and llm_other_agents_count == 0:
                    if agent_deletion_success and llm_deletion_success:
                        messages.success(request, f"Agent '{agent_name}' and its associated LLM were deleted successfully")
                    elif agent_deletion_success:
                        messages.success(request, f"Agent '{agent_name}' was deleted successfully, but there was an issue deleting the LLM")
                    else:
                        messages.success(request, f"Agent '{agent_name}' was deleted from the database, but there were issues with the Retell API")
                else:
                    if agent_deletion_success:
                        messages.success(request, f"Agent '{agent_name}' was deleted successfully")
                    else:
                        messages.success(request, f"Agent '{agent_name}' was deleted from the database, but there was an issue with the Retell API")
            
            return redirect('list_retell_agents')
                
        except Exception as e:
            print(f"Error deleting Retell Agent and LLM: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('list_retell_agents')
    
    # GET request - confirm deletion
    # Check if this is the only agent using its LLM
    llm_other_agents_count = 0
    if agent.llm:
        llm_other_agents_count = RetellAgent.objects.filter(
            llm=agent.llm
        ).exclude(agent_id=agent_id).count()
    
    return render(request, 'retell_agent/delete_agent.html', {
        'agent': agent,
        'will_delete_llm': llm_other_agents_count == 0 and agent.llm is not None
    })

@login_required
def assign_phone_number(request):
    """
    View to assign a phone number to a Retell agent.
    """
    if request.method != 'POST':
        return redirect('list_retell_agents')
    
    agent_id = request.POST.get('agent_id')
    phone_number = request.POST.get('phone_number')
    
    if not agent_id or not phone_number:
        messages.error(request, 'Agent ID and phone number are required')
        return redirect('list_retell_agents')
    
    # Format phone number with leading +
    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"
    
    try:
        # Get the agent
        agent = RetellAgent.objects.get(agent_id=agent_id)
        
        # Update the agent's phone number
        agent.agent_number = phone_number
        agent.save()
        
        messages.success(request, f'Phone number {phone_number} assigned to {agent.agent_name}')
    except RetellAgent.DoesNotExist:
        messages.error(request, f'Agent with ID {agent_id} not found')
    except Exception as e:
        messages.error(request, f'Error assigning phone number: {str(e)}')
    
    return redirect('list_retell_agents')

@login_required
def voice_conversations(request):
    """
    View to display voice call transcripts in a messaging platform style.
    """
    business = request.user.business_set.first()
    
    # Get date range from request parameters or use default (last 30 days)
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    end_date = request.GET.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.GET.get('start_date', (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    # Convert to datetime objects
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)  # End of the day
    
    # Get call data from Retell API
    from usage_analytics.services.retell_api_service import RetellAPIService
    calls = RetellAPIService.list_calls(business, start_date=start_date_obj, end_date=end_date_obj)
    call_details = RetellAPIService.get_call_details(calls)
    
    # Process call transcripts into message format
    for call in call_details:
        messages = []
        if call.get('transcript'):
            # Parse the transcript and create message objects
            transcript_lines = call['transcript'].split('\n')
            
            # Track message start time based on call start time
            call_start_time = datetime.strptime(call['start_time'], '%b %d, %Y %I:%M %p')
            message_time = call_start_time
            message_increment = timedelta(seconds=30)  # Approximate time between messages
            
            for line in transcript_lines:
                if line.strip():
                    # Check if line starts with "Agent:" or "User:"
                    if line.startswith('Agent:'):
                        role = 'agent'
                        content = line[6:].strip()
                    elif line.startswith('User:'):
                        role = 'user'
                        content = line[5:].strip()
                    else:
                        # If no prefix, continue the previous message
                        if messages:
                            messages[-1]['content'] += ' ' + line.strip()
                        continue
                    
                    # Format the timestamp
                    timestamp = message_time.strftime('%I:%M %p')
                    
                    # Add the message
                    messages.append({
                        'role': role,
                        'content': content,
                        'timestamp': timestamp
                    })
                    
                    # Increment the message time for the next message
                    message_time += message_increment
        
        call['messages'] = messages
    
    context = {
        'call_details': call_details,
        'start_date': start_date_obj,
        'end_date': end_date_obj,
    }
    
    return render(request, 'retell_agent/voice_conversations.html', context)
