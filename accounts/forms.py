# /srv/radar_site_prod/accounts/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
# from .models import Profile # Not strictly needed in the form itself if Profile is handled in view

User = get_user_model()

class UserSignUpForm(UserCreationForm): # <<< Make sure this class name is exact
    email = forms.EmailField(max_length=254, required=True, help_text='Required. A valid email address.')
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    town = forms.CharField(max_length=100, required=False, help_text='Optional: Your town or city.')
    state = forms.CharField(max_length=50, required=False, help_text='Optional: Your state or province (e.g., OK, Texas).')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email', 'first_name', 'last_name',)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email')
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        if commit:
            user.save()
        return user


class FamilyInvitationForm(forms.Form):
    """
    A simple form to capture the email address for a family invitation.
    """
    email = forms.EmailField(
        label="Member's Email Address",
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'name@example.com'
        })
    )
