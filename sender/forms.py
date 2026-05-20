from django import forms
from .models import Recipient, Message, MailingList, RecipientsListUpload


class RecipientForm(forms.ModelForm):
    class Meta:
        model = Recipient
        fields = ["email", "title", "comment"]

        def __init__(self):
            super(RecipientForm, self).__init__()
            self.fields["email"].widget.attrs.update(
                {"class": "form-control", "placeholder": "Email"}
            )
            self.fields["title"].widgets.attrs.update(
                {"class": "form-control", "placeholder": "Название"}
            )
            self.fields["comment"].widgets.attrs.update(
                {"class": "form-control", "placeholder": "Комментарий"}
            )


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["title", "body"]

        def __init__(self):
            super(RecipientForm, self).__init__()
            self.fields["title"].widget.attrs.update(
                {"class": "form-control", "placeholder": "Title"}
            )
            self.fields["body"].widgets.attrs.update(
                {"class": "form-control", "placeholder": "Text"}
            )


class MailingListForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=Recipient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Получатели"
    )
    class Meta:
        model = MailingList
        fields = ["message", "recipients"]


class UploadFileForm(forms.Form):
    file = forms.FileField(
        label='JSON-файл',
        help_text='Формат: список объектов с полями "email", "name", "checko_api"'
    )
