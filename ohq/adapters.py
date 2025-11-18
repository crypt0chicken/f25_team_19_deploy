from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages # Import messages

class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request, sociallogin=None):
        """
        This hook is called by django-allauth when a user signs up,
        specifically when using a social account.
        """

        return True
        
        # Following logic unnecessary; Google Auth is configured to only allow andrew.cmu.edu logins

        if not sociallogin:
            messages.error(request, "Sign up is only permitted via your Google account.")
            return False

        # Get the email from the social login data
        email = ""
        
        # The email_addresses list is the most reliable place
        if sociallogin.email_addresses:
            try:
                # Find the email that is primary and verified
                primary_email = next(item for item in sociallogin.email_addresses if item.primary and item.verified)
                email = primary_email.email
            except StopIteration:
                # If no primary/verified email, try to get any email
                if sociallogin.email_addresses:
                    email = sociallogin.email_addresses[0].email
        
        # Fallback to extra_data if not found in email_addresses
        if not email and 'email' in sociallogin.account.extra_data:
            email = sociallogin.account.extra_data['email']

        # If we still can't find an email, block the signup
        if not email:
            messages.error(request, "Could not determine your email from Google. Please try again.")
            return False

        if not email.endswith('@andrew.cmu.edu'):
            messages.error(request, 'Access Denied: You must sign up with an @andrew.cmu.edu email address.')
            return False
        
        # If email is valid, allow the signup
        return True