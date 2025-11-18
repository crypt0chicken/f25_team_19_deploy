from django import forms

from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from ohq.models import Account, Queue

class EditAccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ('nickname',)

class CreateQueueForm(forms.ModelForm):
    class Meta:
        model = Queue
        # Specify the fields to show on the form
        fields = [
            'queueName', 
            'courseNumber',
            'description', 
            'isPublic', 
            'isOpen', 
            'freeze_timeout'
        ]

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
        labels = {
            'queueName': 'Queue Name',
            'courseNumber': 'Course Number',
            'isPublic': 'Make this queue public',
            'isOpen': 'Open this queue immediately',
            'freeze_timeout': 'Auto-Unfreeze Timeout (in seconds)',
        }
        
        help_texts = {
            'freeze_timeout': (
                'Time in seconds a "frozen" student remains frozen before being '
                'automatically returned to the queue. '
                'Set to 0 to disable auto-unfreezing.'
            ),
        }
