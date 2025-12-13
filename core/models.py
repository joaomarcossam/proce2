# core/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PlataformaBrasilService:
    @staticmethod
    def receber_credenciais(email, senha):
        print(f"--- [MOCK] PLATAFORMA BRASIL ---")
        print(f"E-mail: {email}")
        print(f"Senha: {senha}")
        return True

class Pesquisador(models.Model):
    """
    Cadastros dos pesquisadores (quem submete os projetos).
    """
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.nome} ({self.email})"

    class Meta:
        verbose_name = "Pesquisador"
        verbose_name_plural = "Pesquisadores"


class Projeto(models.Model):
    STATUS_CHOICES = (
        ('novo', 'Novo'),
        ('em_analise', 'Em Análise'),
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
    )

    titulo = models.CharField("Título do Projeto", max_length=255)
    descricao = models.TextField("Descrição")
    caae = models.CharField("CAAE", max_length=254, unique=True, help_text="Certificado de Apresentação para Apreciação Ética")
    protocolo = models.CharField("Protocolo", max_length=254, null=True, blank=True)
    
    arquivo_pdf = models.FileField(
        "Arquivo do Projeto (PDF)", 
        upload_to='projetos/pdfs/', 
        null=True, 
        blank=True
    )

    
    pesquisador = models.ForeignKey(
        Pesquisador, 
        on_delete=models.PROTECT, 
        verbose_name="Pesquisador Responsável",
        related_name="projetos"
    )

    data_submissao = models.DateTimeField(default=timezone.now, verbose_name="Data de Submissão")
    data_aprovacao = models.DateField("Data de Aprovação", null=True, blank=True, help_text="Preenchido automaticamente ao aprovar.")
    
    relator_designado = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='projetos_designados',
        verbose_name="Relator do Conselho"
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='novo')

    rel_final = models.BooleanField("Relatório Final Recebido", default=False)
    rel_parc = models.BooleanField("Relatório Parcial Recebido", default=False)

    def __str__(self):
        return f"{self.titulo} ({self.caae})"

class Emenda(models.Model):
    STATUS_EMENDA_CHOICES = (
        ('pendente', 'Pendente'),
        ('aprovada', 'Aprovada'),
        ('reprovada', 'Reprovada'),
    )

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='emendas')
    titulo = models.CharField("Título da Emenda", max_length=255)
    descricao = models.TextField("Descrição das Alterações")
    data_submissao = models.DateTimeField(auto_now_add=True)
    
    arquivo_pdf = models.FileField(
        "Arquivo da Emenda (PDF)", 
        upload_to='emendas/pdfs/', 
        null=True, 
        blank=True
    )
    
    status = models.CharField(
        "Status da Emenda", 
        max_length=20, 
        choices=STATUS_EMENDA_CHOICES, 
        default='pendente'
    )

    relator_parecer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='emendas_avaliadas')
    data_parecer = models.DateTimeField(null=True, blank=True)
    justificativa = models.TextField("Justificativa do Parecer", null=True, blank=True)

    def __str__(self):
        return f"Emenda: {self.titulo} -> {self.projeto.titulo} ({self.get_status_display()})"



class Parecer(models.Model):
    DECISAO_CHOICES = (
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
    )

    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='pareceres')
    
    relator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pareceres_dados')
    data_parecer = models.DateTimeField(default=timezone.now, verbose_name="Data do Parecer")
    decisao = models.CharField(max_length=20, choices=DECISAO_CHOICES)
    justificativa = models.TextField()

    arquivo_parecer = models.FileField(
        "Anexo do Parecer (PDF)", 
        upload_to='pareceres/pdfs/', 
        null=True, 
        blank=True
    )

    def __str__(self):
        return f"Parecer de {self.relator.username} para {self.projeto.titulo}"