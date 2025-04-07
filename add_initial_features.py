import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leadsAutomation.settings')
django.setup()

from subscription.models import Feature, SubscriptionPlan

def create_features():
    # Define categories and features
    features_data = [
        # Analytics features
        {
            'name': 'basic_analytics',
            'display_name': 'Basic Analytics',
            'description': 'View basic usage statistics and reports',
            'category': 'Analytics',
        },
        {
            'name': 'advanced_analytics',
            'display_name': 'Advanced Analytics',
            'description': 'Access detailed analytics with custom reports and insights',
            'category': 'Analytics',
        },
        {
            'name': 'export_reports',
            'display_name': 'Export Reports',
            'description': 'Export analytics reports in various formats',
            'category': 'Analytics',
        },
        
        # Support features
        {
            'name': 'email_support',
            'display_name': 'Email Support',
            'description': 'Get support via email with 24-hour response time',
            'category': 'Support',
        },
        {
            'name': 'priority_support',
            'display_name': 'Priority Support',
            'description': 'Priority email and chat support with 4-hour response time',
            'category': 'Support',
        },
        {
            'name': 'dedicated_account_manager',
            'display_name': 'Dedicated Account Manager',
            'description': 'Get a dedicated account manager for personalized support',
            'category': 'Support',
        },
        
        # Integration features
        {
            'name': 'api_access',
            'display_name': 'API Access',
            'description': 'Access our API for custom integrations',
            'category': 'Integrations',
        },
        {
            'name': 'custom_integrations',
            'display_name': 'Custom Integrations',
            'description': 'Connect with popular third-party services',
            'category': 'Integrations',
        },
        {
            'name': 'webhooks',
            'display_name': 'Webhooks',
            'description': 'Set up webhooks for real-time data updates',
            'category': 'Integrations',
        },
        
        # Customization features
        {
            'name': 'white_labeling',
            'display_name': 'White Labeling',
            'description': 'Remove our branding and add your own',
            'category': 'Customization',
        },
        {
            'name': 'custom_domain',
            'display_name': 'Custom Domain',
            'description': 'Use your own domain for the service',
            'category': 'Customization',
        },
        {
            'name': 'custom_branding',
            'display_name': 'Custom Branding',
            'description': 'Customize colors, logos, and styles',
            'category': 'Customization',
        },
        
        # Management features
        {
            'name': 'bulk_operations',
            'display_name': 'Bulk Operations',
            'description': 'Perform actions on multiple items at once',
            'category': 'Management',
        },
        {
            'name': 'team_management',
            'display_name': 'Team Management',
            'description': 'Add and manage team members with different roles',
            'category': 'Management',
        },
        {
            'name': 'advanced_permissions',
            'display_name': 'Advanced Permissions',
            'description': 'Set granular permissions for team members',
            'category': 'Management',
        },
    ]
    
    # Create features
    created_features = []
    for feature_data in features_data:
        feature, created = Feature.objects.get_or_create(
            name=feature_data['name'],
            defaults={
                'display_name': feature_data['display_name'],
                'description': feature_data['description'],
                'category': feature_data['category'],
            }
        )
        created_features.append(feature)
        if created:
            print(f"Created feature: {feature.display_name}")
        else:
            print(f"Feature already exists: {feature.display_name}")
    
    # Assign features to plans
    starter_plan = SubscriptionPlan.objects.filter(name__icontains='Starter').first()
    professional_plan = SubscriptionPlan.objects.filter(name__icontains='Professional').first()
    enterprise_plan = SubscriptionPlan.objects.filter(name__icontains='Enterprise').first()
    
    if starter_plan:
        # Basic features for Starter plan
        starter_features = [
            'basic_analytics',
            'email_support',
            'api_access',
        ]
        for feature_name in starter_features:
            feature = Feature.objects.get(name=feature_name)
            starter_plan.features.add(feature)
        print(f"Added features to {starter_plan.name} plan")
    
    if professional_plan:
        # More features for Professional plan
        professional_features = [
            'basic_analytics',
            'advanced_analytics',
            'export_reports',
            'email_support',
            'priority_support',
            'api_access',
            'custom_integrations',
            'webhooks',
            'bulk_operations',
            'team_management',
        ]
        for feature_name in professional_features:
            feature = Feature.objects.get(name=feature_name)
            professional_plan.features.add(feature)
        print(f"Added features to {professional_plan.name} plan")
    
    if enterprise_plan:
        # All features for Enterprise plan
        for feature in created_features:
            enterprise_plan.features.add(feature)
        print(f"Added all features to {enterprise_plan.name} plan")

if __name__ == '__main__':
    create_features()
    print("Initial features created and assigned to plans successfully!")
