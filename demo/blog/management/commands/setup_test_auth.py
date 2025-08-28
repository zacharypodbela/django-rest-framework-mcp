"""Management command to set up test authentication for the demo app."""

import base64

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = "Sets up authentication for testing MCP with existing or new users"

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            type=str,
            help="Username for the test user",
        )
        parser.add_argument(
            "password",
            type=str,
            help="Password for the test user",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]

        # Try to get existing user first
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f"Found existing user: {username}"))
            user_created = False

            # Verify the provided password is correct
            if not user.check_password(password):
                raise CommandError(
                    f"Password incorrect for existing user '{username}'. "
                    f"Please provide the correct password or use a different username."
                )
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=username,
                password=password,
                email=f"{username}@example.com",
                first_name="Test",
                last_name="User",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created new user: {username} (password: {password})")
            )
            user_created = True

        # Create or get token
        token, token_created = Token.objects.get_or_create(user=user)

        if token_created:
            self.stdout.write(self.style.SUCCESS(f"Created new token: {token.key}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Using existing token: {token.key}"))

        # Print usage instructions
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("MCP Authentication Test Instructions"))
        self.stdout.write("=" * 70)

        self.stdout.write(f"\n📋 User: {username}")
        if user_created:
            self.stdout.write(f"🔑 Password: {password}")
        else:
            self.stdout.write("🔑 Password: (using existing user - password unchanged)")
        self.stdout.write(f"🎫 Token: {token.key}")

        self.stdout.write("\n1️⃣ Token Authentication:")
        self.stdout.write(f'   headers={{"Authorization": "Token {token.key}"}}')

        self.stdout.write("\n2️⃣ Basic Authentication:")
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self.stdout.write(f'   headers={{"Authorization": "Basic {credentials}"}}')

        self.stdout.write("\n3️⃣ Session Authentication:")
        self.stdout.write("   First login at http://localhost:8000/admin/")
        self.stdout.write("   Then use the sessionid cookie in your requests")

        self.stdout.write("\n4️⃣ Test with MCPClient:")
        self.stdout.write("   ```python")
        self.stdout.write("   from djangorestframework_mcp.test import MCPClient")
        self.stdout.write("   client = MCPClient()")
        self.stdout.write(
            f'   result = client.call_tool("list_posts", HTTP_AUTHORIZATION="Token {token.key}")'
        )
        self.stdout.write("   ```")

        self.stdout.write("\n5️⃣ Test with curl:")
        self.stdout.write("   ```bash")
        self.stdout.write("   curl -X POST http://localhost:8000/mcp/ \\")
        self.stdout.write('     -H "Content-Type: application/json" \\')
        self.stdout.write(f'     -H "Authorization: Token {token.key}" \\')
        self.stdout.write('     -d \'{"jsonrpc": "2.0", "method": "tools/call", \\')
        self.stdout.write('          "params": {"name": "list_posts", "arguments": {}}, \\')
        self.stdout.write('          "id": 1}\'')
        self.stdout.write("   ```")

        self.stdout.write("\n" + "=" * 70)

        # Add user creation instructions
        self.stdout.write("\n💡 Need to create users? Use Django's built-in commands:")
        self.stdout.write("   # Create a superuser (can access Django admin)")
        self.stdout.write("   python manage.py createsuperuser")
        self.stdout.write("")
        self.stdout.write("   # Create a regular user programmatically")
        self.stdout.write("   python manage.py shell")
        self.stdout.write("   >>> from django.contrib.auth.models import User")
        self.stdout.write("   >>> User.objects.create_user('username', 'email@example.com', 'password')")
        self.stdout.write("\n" + "=" * 70)