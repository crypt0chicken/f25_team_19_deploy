from django import forms

from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from django.core.exceptions import ValidationError

from ohq.models import Account, Queue

class EditAccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ('nickname',)

    def clean_nickname(self):
        data = self.cleaned_data['nickname']
        if len(data) == 0:
            raise ValidationError("Nickname cannot be empty")
        
        return data

class CreateQueueForm(forms.ModelForm):
    class Meta:
        model = Queue
        # Specify the fields to show on the form
        fields = [
            'queueName', 
            'courseNumber',
            'description', 
            'isPublic', 
            'freeze_timeout'
        ]

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        
        labels = {
            'queueName': 'Queue Name',
            'courseNumber': 'Course Number',
            'isPublic': 'Public Queue',
            'freeze_timeout': 'Auto-Unfreeze Timeout',
        }
        
        help_texts = {
            'freeze_timeout': (
                'Time in seconds a "frozen" student remains frozen before being '
                'automatically returned to the queue. '
                'Set to 0 to disable auto-unfreezing.'
            ),
        }
    def clean_courseNumber(self):
        data = self.cleaned_data['courseNumber']
        if not data.isdigit():
            raise ValidationError("Course number must be numerical")
        if not len(data) == 5:
            raise ValidationError("Course number has wrong number of digits")
        return data
