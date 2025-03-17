import os
import sys
import django
from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management import execute_from_command_line

class RunServerSSLCommand(RunserverCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--cert', 
            dest='cert',
            help='Path to the SSL certificate file',
            default='./localhost.crt'
        )
        parser.add_argument(
            '--key', 
            dest='key',
            help='Path to the SSL key file',
            default='./localhost.key'
        )

    def handle(self, *args, **options):
        # Check if certificate and key files exist
        if not os.path.exists(options['cert']) or not os.path.exists(options['key']):
            self.stdout.write(self.style.ERROR(
                f"SSL certificate or key file not found. Please generate them using:\n"
                f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
                f"-keyout {options['key']} -out {options['cert']} -subj '/CN=localhost'"
            ))
            return

        self.https_port = options.get('addrport', '').split(':')[-1]
        self.cert_file = options['cert']
        self.key_file = options['key']
        
        super().handle(*args, **options)

    def inner_run(self, *args, **options):
        # Set the SSL certificate and key file paths
        options['ssl_certificate'] = self.cert_file
        options['ssl_certificate_key'] = self.key_file
        
        self.stdout.write(self.style.SUCCESS(
            f"Starting HTTPS development server at https://127.0.0.1:{self.https_port}/\n"
            f"Using SSL certificate: {self.cert_file}\n"
            f"Using SSL key: {self.key_file}\n"
            f"Quit the server with CTRL-BREAK."
        ))
        
        super().inner_run(*args, **options)

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leadsAutomation.settings')
    django.setup()
    
    # Replace the runserver command with our custom SSL command
    from django.core.management.commands.runserver import Command
    Command = RunServerSSLCommand
    
    execute_from_command_line(sys.argv)
