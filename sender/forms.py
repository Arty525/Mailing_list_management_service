from django import forms
from .models import Recipient, Message, MailingList, RecipientsListUpload


class RecipientForm(forms.ModelForm):
    class Meta:
        model = Recipient
        fields = ["email", "title", "comment"]

    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Email"}
        )
        self.fields["title"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Название"}
        )
        self.fields["comment"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Комментарий"}
        )


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["title", "body", "logo", "logo_url"]

    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update(
            {"class": "form-control"}
        )
        self.fields["body"].widget.attrs.update(
            {"class": "form-control"}
        )
        self.fields["logo"].widget.attrs.update({"class": "form-control"})
        self.fields["logo_url"].widget.attrs.update({"class": "form-control"})

    def clean(self):
        cleaned_data = super().clean()
        logo = cleaned_data.get('logo')
        logo_url = cleaned_data.get('logo_url')

        # Если загружен и файл, и URL – приоритет у файла (очищаем URL)
        if logo and logo_url:
            cleaned_data['logo_url'] = ''
        # Если нет файла, но есть URL – оставляем URL
        # Если нет ни того, ни другого – логотип не будет отображаться
        return cleaned_data

class MailingListForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=Recipient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Получатели"
    )
    class Meta:
        model = MailingList
        fields = ["message", "recipients"]

    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields["message"].widget.attrs.update({"class": "form-control"})
        self.fields["recipients"].widget.attrs.update({"class": "checkbox"})


class UploadFileForm(forms.Form):
    file = forms.FileField(
        label='JSON-файл',
        help_text='Формат: список объектов с полями "email", "name", "checko_api"'
    )
