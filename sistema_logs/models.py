from django.db import models
from django.utils import timezone

class Logs(models.Model):
    # Informações do processo
    nome_log = models.CharField(max_length=255)
    processo = models.CharField(max_length=255)
    # Informações gerais
    parametros_usados = models.JSONField(default=dict, null=True)
    horario = models.DateTimeField(default=timezone.now)
    # Informações de conclusão
    concluiu = models.BooleanField(default=False)
    msgErro = models.TextField(blank=True, null=True)
    # Relacionamentos
    projeto = models.ForeignKey('core.Projeto', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if not self.concluiu:
            mensagemErro = f"Causa: {self.msgErro}|"
        else:
            mensagemErro = "|"
        return f"|ID: {self.id}|Nome: {self.nome_log}|Processo: {self.processo}|Data: {self.horario}|Concluiu: {self.concluiu}|{mensagemErro}"