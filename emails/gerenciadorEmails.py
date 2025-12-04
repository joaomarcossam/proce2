from enum import Enum
from django.core.mail import EmailMessage
from decouple import config
from django.core.files import File
from typing import List, Optional
import os

from emails.models import Email, AnexoEmail
from core.models import Projeto
from emails.imapUtils import conectar_email_IMAP, processar_emails, buscar_id_email

class TipoRelatorio(Enum):
        PARCIAL = "parcial"
        FINAL = "final"
        QUALQUER = "final ou parcial"

class GerenciadorEmails:
    @staticmethod
    def envia_email(email_destinatario: str, 
                    assuntoEmail: str, 
                    mensagemEmail: str, 
                    caminhoArquivos: Optional[List[str]] = None, 
                    projeto: Optional[Projeto] = None, 
                    remetenteEmail = None):
        
        # Se remetenteEmail for None, usa o padrão do settings .env
        if not remetenteEmail:
            remetenteEmail = config("EMAIL_HOST_USER")

        email = EmailMessage(subject=assuntoEmail, body=mensagemEmail, from_email=remetenteEmail, to=[email_destinatario])
        if caminhoArquivos:
            for caminhos in caminhoArquivos:
                email.attach_file(caminhos)
        email.send(fail_silently=False)
        id_email = buscar_id_email(assuntoEmail, email_destinatario)
        print(f"Enviado por {remetenteEmail}")

        email = Email.objects.create(
                    remetente=remetenteEmail,
                    destinatario=email_destinatario,
                    assunto=assuntoEmail,
                    mensagem=mensagemEmail,
                    email_id=id_email,
                    projeto=projeto
        )
        if caminhoArquivos:
            for caminho in caminhoArquivos:
                nome = os.path.basename(caminho)
                with open(caminho, "rb") as arquivo:
                    anexo = AnexoEmail(
                        email=email,
                        nomeArquivo=nome,
                        tamanho=os.path.getsize(caminho),
                    )
                    anexo.arquivo.save(nome, File(arquivo), save=True)
    
    @staticmethod
    def notificacao_relatorio_aprovado(nome_pesquisador: str, nome_pesquisa: str, email_destinatario: str, dias_restantes: int, tipo_relatorio: TipoRelatorio):
        titulo = f"Solicitação de envio do relatório {tipo_relatorio}"
        
        mensagem = (
            f"Prezado(a) {nome_pesquisador},\n\n"
            f"Conforme os registros da pesquisa '{nome_pesquisa}', solicitamos o envio do relatório {tipo_relatorio}. "
            f"O prazo para submissão é de {dias_restantes} dias.\n\n"
            "Pedimos que encaminhe o relatório dentro do período estipulado, "
            "a fim de garantir a conformidade com as normas do Comitê de Ética.\n\n"
            "Atenciosamente,\n"
            "Comitê de Ética"
        )
        
        GerenciadorEmails.envia_email(email_destinatario, titulo, mensagem)

    @staticmethod
    def notificacao_relatorio_pendente(nome_pesquisador: str, nome_pesquisa: str, email_destinatario: str, dias_restantes: int):
        titulo = f"Aviso sobre pendência na pesquisa '{nome_pesquisa}'"
        
        if dias_restantes > 0:
            acao = (
                f"O prazo para envio das respostas às diligências é de {dias_restantes} dias. "
                "Solicitamos que submeta as respostas ou, se necessário, uma notificação solicitando a retirada do projeto."
            )
        else:
            acao = (
                "O prazo para atendimento das diligências expirou. "
                "É necessário submeter uma notificação solicitando a retirada do projeto com a devida justificativa."
            )
        
        mensagem = (
            f"Prezado(a) {nome_pesquisador},\n\n"
            f"Conforme análise do Comitê de Ética, o parecer da pesquisa '{nome_pesquisa}' encontra-se pendente. "
            f"{acao}\n\n"
            "Pedimos que regularize a situação o quanto antes para garantir conformidade com as normas do Comitê.\n\n"
            "Atenciosamente,\n"
            "Comitê de Ética"
        )
        
        GerenciadorEmails.envia_email(email_destinatario, titulo, mensagem, None)

    @staticmethod
    def ler_respostas_emails(mailbox="INBOX"):
        clienteEmail = conectar_email_IMAP(mailbox)
        uids = clienteEmail.search(['UNSEEN'])
        if not uids:
            return 0

        emails = clienteEmail.fetch(uids, ['RFC822', 'ENVELOPE', 'FLAGS'])
        novas_respostas = processar_emails(clienteEmail, emails)
        clienteEmail.logout()
        return novas_respostas
