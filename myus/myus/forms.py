from django import forms

from .models import Hunt, Puzzle, Team, User


class MarkdownTextarea(forms.Textarea):
    template_name = "widgets/markdown_textarea.html"


# Custom date-time field using a datetime-local input
# Implementation from StackOverflow: https://stackoverflow.com/a/69965027
class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class DateTimeLocalField(forms.DateTimeField):
    input_formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M",
    ]
    widget = DateTimeLocalInput(format="%Y-%m-%dT%H:%M")


# based on UserCreationForm from Django source
class RegisterForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username and
    password.
    """

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput,
        help_text="Enter the same password as above, for verification.",
    )
    email = forms.EmailField(
        label="Email address",
        required=False,
        help_text="Optional, but you'll get useful email notifications when we implement those.",
    )
    bio = forms.CharField(
        widget=MarkdownTextarea,
        required=False,
        help_text="(optional) Tell us about yourself. What kinds of puzzle genres or subject matter do you like?",
    )

    class Meta:
        model = User
        fields = ("username", "email", "display_name", "discord_username", "bio")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                "The two password fields didn't match.",
                code="password_mismatch",
            )
        return password2

    def save(self, commit=True):
        user = super(RegisterForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class NewHuntForm(forms.ModelForm):
    description = forms.CharField(widget=MarkdownTextarea, required=False)
    start_time = DateTimeLocalField(required=False, help_text="Date/time must be UTC")
    end_time = DateTimeLocalField(required=False, help_text="Date/time must be UTC")

    class Meta:
        model = Hunt
        fields = [
            "name",
            "slug",
            "description",
            "start_time",
            "end_time",
            "member_limit",
            "guess_limit",
            "leaderboard_style",
            "solution_style",
        ]


class EditHuntForm(forms.ModelForm):
    description = forms.CharField(widget=MarkdownTextarea, required=False)
    start_time = DateTimeLocalField(required=False, help_text="Date/time must be UTC")
    end_time = DateTimeLocalField(required=False, help_text="Date/time must be UTC")

    class Meta:
        model = Hunt
        fields = [
            "name",
            "slug",
            "description",
            "start_time",
            "end_time",
            "archive_after_end_date",
            "member_limit",
            "guess_limit",
            "leaderboard_style",
            "solution_style",
        ]


class GuessForm(forms.Form):
    guess = forms.CharField()


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name"]


class InviteMemberForm(forms.Form):
    username = forms.CharField()

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No such user!")

        cleaned_data["user"] = user
        return cleaned_data


class PuzzleForm(forms.ModelForm):
    content = forms.CharField(widget=MarkdownTextarea, required=False)

    class Meta:
        model = Puzzle
        fields = [
            "name",
            "slug",
            "content",
            "answer",
            "answer_response",
            "solution_url",
            "points",
            "order",
            "progress_points",
            "progress_threshold",
        ]
