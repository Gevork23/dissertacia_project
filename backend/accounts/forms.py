from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(
            attrs={"placeholder": "Введите логин", "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"placeholder": "Введите пароль", "autocomplete": "current-password"}
        ),
    )


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "Придумайте логин",
            "first_name": "Имя",
            "last_name": "Фамилия",
            "email": "name@example.com",
            "password1": "Пароль",
            "password2": "Повторите пароль",
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("placeholder", placeholders.get(name, ""))

