from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decouple import config
from django.core import mail
from unittest.mock import patch

from emails.gerenciadorEmails import GerenciadorEmails, TipoRelatorio
from emails.management.commands.verificar_rotinas_diarias import Command
from core.models import Projeto, Pesquisador, Parecer, User

class RotinaDiariaTest(TestCase):
    def setUp(self):
        hoje = timezone.now()

        self.pesq = Pesquisador.objects.create(
            nome="Teste",
            email="Teste@Teste.com",
            telefone="0000",
        )

        # Projeto para relatório parcial (180 dias)
        self.projeto_180 = Projeto.objects.create(
            titulo="P180",
            pesquisador=self.pesq,
            data_submissao=hoje - timedelta(days=180),
            data_aprovacao=hoje - timedelta(days=180),
            status="aprovado",
            rel_parc=False,
            caae=180
        )

        # Projeto para relatório final (365 dias)
        self.projeto_365 = Projeto.objects.create(
            titulo="P365",
            pesquisador=self.pesq,
            data_submissao=hoje - timedelta(days=365),
            data_aprovacao=hoje - timedelta(days=365),
            status="aprovado",
            rel_final=False,
            caae=365
        )

        # Projeto pendente com parecer de 26 dias atrás (vai avisar)
        self.projeto_pend = Projeto.objects.create(
            titulo="Pend",
            pesquisador=self.pesq,
            data_submissao=hoje,
            status="pendente"
        )

        self.relator = User.objects.create(username="relator")

        Parecer.objects.create(
            projeto=self.projeto_pend,
            relator=self.relator,
            decisao="pendente",
            justificativa="Um teste",
            data_parecer=hoje - timedelta(days=26)
        )

    def test_rotina(self):
        with patch("emails.gerenciadorEmails.GerenciadorEmails.notificacao_relatorio_aprovado") as mock_aprovado, \
             patch("emails.gerenciadorEmails.GerenciadorEmails.notificacao_relatorio_pendente") as mock_pendente:

            Command().handle()

            # Assert para projetos aprovados
            self.assertTrue(mock_aprovado.called)

            # Assert para pendentes
            self.assertTrue(mock_pendente.called)

    def test_envio(self):
            GerenciadorEmails.notificacao_relatorio_aprovado(self.pesq.nome, self.projeto_180.titulo, self.pesq.email, 185, TipoRelatorio.PARCIAL)
            GerenciadorEmails.notificacao_relatorio_pendente(self.pesq.nome, self.projeto_pend.titulo, self.pesq.email, 4)

            # Assert para verificar o número de emails enviados
            self.assertEqual(len(mail.outbox), 2)
