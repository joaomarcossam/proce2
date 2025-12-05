from django import forms
from django.contrib.auth.models import User, Group
from .models import Projeto, Pesquisador, Emenda, Parecer

class DesignarRelatorForm(forms.ModelForm):
    relator_designado = forms.ModelChoiceField(
        queryset=None, label="Selecione o Relator", empty_label="-- Nenhum --", widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = Projeto
        fields = ['relator_designado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            grupo = Group.objects.get(name='Relatores')
            self.fields['relator_designado'].queryset = grupo.user_set.all()
        except Group.DoesNotExist:
            self.fields['relator_designado'].queryset = User.objects.none()

class ParecerForm(forms.ModelForm):
    class Meta:
        model = Parecer
        fields = ['decisao', 'justificativa']
        widgets = {'decisao': forms.RadioSelect(choices=Parecer.DECISAO_CHOICES), 'justificativa': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['justificativa'].required = True

class ProjetoForm(forms.ModelForm):
    pesquisador_nome = forms.CharField(label="Nome do Pesquisador", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    pesquisador_email = forms.EmailField(label="E-mail", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    pesquisador_telefone = forms.CharField(label="Telefone", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Projeto
        fields = ['titulo', 'descricao', 'caae', 'arquivo_pdf']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'caae': forms.TextInput(attrs={'class': 'form-control'}),
            'arquivo_pdf': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        nome = self.cleaned_data['pesquisador_nome']
        email = self.cleaned_data['pesquisador_email']
        tel = self.cleaned_data.get('pesquisador_telefone')
        pesq, _ = Pesquisador.objects.get_or_create(email=email, defaults={'nome': nome, 'telefone': tel})
        self.instance.pesquisador = pesq
        return super().save(commit=commit)

class EmendaForm(forms.ModelForm):
    class Meta:
        model = Emenda
        fields = ['titulo', 'descricao', 'arquivo_pdf']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'arquivo_pdf': forms.FileInput(attrs={'class': 'form-control'}),
        }

class CadastroRelatorForm(forms.ModelForm):
    """
    Formulário para o Gestor cadastrar um novo Relator.
    Pede apenas Nome e E-mail.
    """
    first_name = forms.CharField(label="Nome Completo", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label="E-mail", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['first_name', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Já existe um usuário cadastrado com este e-mail.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        
        user.username = self.cleaned_data['email']
        
        user.set_password('123456') 
        
        if commit:
            user.save()
            grupo_relatores, _ = Group.objects.get_or_create(name='Relatores')
            user.groups.add(grupo_relatores)
        return user