from django import forms
from django.contrib.auth.models import User, Group
from .models import Projeto, Pesquisador, Emenda, Parecer
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.utils import timezone

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
    data_parecer = forms.DateTimeField(
        label="Data e Horário do Parecer",
        required=True,
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        )
    )

    class Meta:
        model = Parecer
        fields = ['decisao', 'justificativa', 'data_parecer', 'arquivo_parecer']
        widgets = {
            'decisao': forms.RadioSelect(choices=Parecer.DECISAO_CHOICES), 
            'justificativa': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'arquivo_parecer': forms.FileInput(attrs={'class': 'form-control'}) # Widget para upload
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['justificativa'].required = True
        if not self.initial.get('data_parecer'):
            self.initial['data_parecer'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')

class ProjetoForm(forms.ModelForm):
    pesquisador_nome = forms.CharField(label="Nome Pesquisador", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    pesquisador_email = forms.EmailField(label="E-mail (Obrigatório)", required=True, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Preencha se faltar no Excel'}))
    pesquisador_telefone = forms.CharField(label="Telefone", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    status_inicial = forms.ChoiceField(
        label="Status",
        choices=[
            ('novo', 'Novo (----)'),
            ('pendente', 'Pendente'),
            ('aprovado', 'Aprovado'),
            ('reprovado', 'Reprovado'),
            ('em_analise', 'Em Análise')
        ],
        required=False,
        initial='novo',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    relator_designado = forms.ModelChoiceField(
        queryset=None, 
        label="Relator", 
        required=False, 
        empty_label="-- Sem Relator --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    data_parecer_manual = forms.DateField(
        label="Data Parecer", 
        required=False, 
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    relator_nome_texto = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Projeto
        fields = ['titulo', 'descricao', 'caae', 'arquivo_pdf', 'data_aprovacao', 'relator_designado']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
            'caae': forms.TextInput(attrs={'class': 'form-control'}),
            'arquivo_pdf': forms.FileInput(attrs={'class': 'form-control'}),
            'data_aprovacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            grupo = Group.objects.get(name='Relatores')
            self.fields['relator_designado'].queryset = grupo.user_set.all()
        except Group.DoesNotExist:
            self.fields['relator_designado'].queryset = User.objects.none()

    def save(self, commit=True):
        nome = self.cleaned_data['pesquisador_nome']
        email = self.cleaned_data['pesquisador_email']
        tel = self.cleaned_data.get('pesquisador_telefone')
        pesq, created = Pesquisador.objects.get_or_create(email=email, defaults={'nome': nome, 'telefone': tel})
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

class ParecerEmendaForm(forms.ModelForm):
    class Meta:
        model = Emenda
        fields = ['status', 'justificativa']
        widgets = {
            'status': forms.RadioSelect(choices=[('aprovada', 'Aprovada'), ('reprovada', 'Reprovada')]),
            'justificativa': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }
        labels = {
            'status': 'Decisão da Emenda',
            'justificativa': 'Justificativa do Parecer'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['justificativa'].required = True

class CadastroRelatorForm(forms.ModelForm):
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
        user.set_unusable_password() 
        if commit:
            user.save()
            grupo_relatores, _ = Group.objects.get_or_create(name='Relatores')
            user.groups.add(grupo_relatores)
        return user
    

class CustomPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()
        active_users = UserModel._default_manager.filter(
            **{
                '%s__iexact' % email_field_name: email,
                'is_active': True,
            }
        )
        return iter(active_users)