from django.db import models

class Email(models.Model):
    # Informações do email
    remetente = models.EmailField()
    destinatario = models.EmailField()
    assunto = models.CharField(max_length=255)
    mensagem = models.TextField()
    enviado_em = models.DateTimeField(auto_now_add=True)
    email_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Relacionamentos
    projeto = models.ForeignKey('core.Projeto', on_delete=models.SET_NULL, null=True, blank=True)
    email_original = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='respostas')

    def __str__(self):
        if self.email_original:
            return f"Resposta de {self.remetente} para {self.email_original.assunto}"
        return f"{self.assunto} para {self.destinatario}"

def anexos_email_upload_to(instance, filename):
    return f"email_attachments/{instance.email.id}/{filename}"

class AnexoEmail(models.Model):
    email = models.ForeignKey('Email', related_name='anexos', on_delete=models.CASCADE)

    arquivo = models.FileField(upload_to=anexos_email_upload_to)
    caminhoArquivo = models.CharField(max_length=255)
    tamanho = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.caminhoArquivo