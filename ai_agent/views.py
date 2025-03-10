from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .chatbot import get_dynamic_system_prompt

from accounts.models import Business
from .models import AgentConfiguration

# Create your views here.



@login_required
def agent_config_detail(request):
    """View to see details of a specific agent configuration"""
    config = AgentConfiguration.objects.filter(business__user=request.user).first()
    
    return render(request, 'ai_agent/agent_config_detail.html', {
        'config': config
    })

@login_required
def agent_config_create(request):
    """View to create a new agent configuration"""
    # Get businesses the user owns
    business = request.user.business_set.first()
    
    if not business:
        messages.error(request, "You need to have a business registered before creating an AI Agent configuration.")
        return redirect('ai_agent:agent_config_list')
    
    # Check if configuration already exists for this business
    if AgentConfiguration.objects.filter(business=business).exists():
        messages.info(request, f"A configuration already exists for {business.businessName}. Redirecting to edit page.")
        return redirect('ai_agent:agent_config_edit', config_id=business.businessId)
    
    if request.method == 'POST':
        # Create new configuration
        config = AgentConfiguration.objects.create(
            business=business,
            agent_name=request.POST.get('agent_name', 'Sarah'),
            agent_role=request.POST.get('agent_role', 'virtual customer support and sales representative'),
            business_description=request.POST.get('business_description', ''),
            business_mission=request.POST.get('business_mission', ''),
            services=request.POST.get('services', ''),
            custom_instructions=request.POST.get('custom_instructions', ''),
            script=request.POST.get('script', '')
        )
        
        messages.success(request, f"Configuration for {business.businessName} created successfully.")
        return redirect('ai_agent:agent_config_detail', config_id=business.businessId)
    
    return render(request, 'ai_agent/agent_config_form.html', {
        'mode': 'create',
        'business': business
    })

@login_required
def agent_config_edit(request, config_id):
    """View to edit an existing agent configuration"""
    business = get_object_or_404(Business, businessId=config_id)
    
    # Check if user owns this business
    if business.user != request.user:
        messages.error(request, "You don't have permission to edit this configuration.")
        return redirect('ai_agent:agent_config')

    try:
        config = AgentConfiguration.objects.get(business=business)
    except AgentConfiguration.DoesNotExist:
        messages.error(request, "Configuration not found.")
        return redirect('ai_agent:agent_config')
    
    if request.method == 'POST':
        # Update configuration
        config.agent_name = request.POST.get('agent_name', config.agent_name)
        config.agent_role = request.POST.get('agent_role', config.agent_role)
        config.business_description = request.POST.get('business_description', config.business_description)
        config.business_mission = request.POST.get('business_mission', config.business_mission)
        config.services = request.POST.get('services', config.services)
        config.custom_instructions = request.POST.get('custom_instructions', config.custom_instructions)
        config.script = request.POST.get('script', config.script)
        config.save()
        
        messages.success(request, f"Configuration for {business.businessName} updated successfully.")
        return redirect('ai_agent:agent_config')
    
    return render(request, 'ai_agent/agent_config_form.html', {
        'config': config,
        'mode': 'edit'
    })

@login_required
@require_POST
def agent_config_delete(request, config_id):
    """View to delete an agent configuration"""
    business = get_object_or_404(Business, businessId=config_id)
    
    # Check if user owns this business
    if business.user != request.user:
        messages.error(request, "You don't have permission to delete this configuration.")
        return redirect('ai_agent:agent_config')
    
    # Get the configuration for this business
    config = AgentConfiguration.objects.filter(business=business).first()
    
    if config:
        business_name = business.businessName
        config.delete()
        messages.success(request, f"Configuration for {business_name} deleted successfully.")
    else:
        messages.warning(request, "No configuration found to delete.")
    
    return redirect('ai_agent:agent_config')

@login_required
def agent_config_preview(request):
    """View to preview the system prompt generated from a configuration"""
    config = AgentConfiguration.objects.filter(business__user=request.user).first()
    
    # Check if user owns this business
    if not config:
        messages.error(request, "You don't have a configuration to preview.")
        return redirect('ai_agent:agent_config')
    
    # Generate the system prompt
    system_prompt = get_dynamic_system_prompt(config.business.businessId)
   
    
    return render(request, 'ai_agent/agent_config_preview.html', {
        'config': config,
        'system_prompt': system_prompt
    })
