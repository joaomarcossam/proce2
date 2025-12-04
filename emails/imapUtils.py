from imapclient import IMAPClient
from decouple import config
from email import message_from_bytes
from django.core.files.base import ContentFile
from django.db import transaction
from email.header import decode_header, make_header
from emails.models import Email, AnexoEmail
import re
import time

def conectar_email_IMAP(mailbox: str):
    host = config("IMAP_HOST")
    user = config("EMAIL_HOST_USER")
    pwd = config("EMAIL_HOST_PASSWORD")

    clienteEmail = IMAPClient(host, ssl=True)
    clienteEmail.login(user, pwd)
    clienteEmail.select_folder(mailbox, readonly=False)
    return clienteEmail

def buscar_email_original(msg):
    in_reply = msg.get('In-Reply-To')
    if not in_reply:
        return None

    try:
        decoded = str(make_header(decode_header(in_reply)))
    except:
        decoded = in_reply

    return Email.objects.filter(email_id=decoded).first()

def extrair_corpo(msg):
    body = None

    if msg.is_multipart():
        for part in msg.walk():
            tipo = part.get_content_type()
            disposicao = part.get_content_disposition()

            if disposicao == 'attachment':
                continue
            if tipo == 'text/plain':
                body = part
                break
            if tipo == 'text/html' and body is None:
                body = part

    else:
        body = msg
    if not body:
        return ""

    charset = body.get_content_charset() or 'utf-8'
    try:
        return body.get_payload(decode=True).decode(charset, errors='ignore').strip()
    except:
        return body.get_payload().decode(errors='ignore').strip()

def salvar_email(msg, email_original, corpo):
    def decode_addr(header_value):
        if not header_value:
            return ""
        hdr = str(make_header(decode_header(header_value)))
        if '<' in hdr and '>' in hdr:
            return hdr
        return hdr

    remetente = decode_addr(msg.get('From'))
    destinatario = decode_addr(msg.get('To'))

    assunto = msg.get('Subject', "")
    assunto = str(make_header(decode_header(assunto)))

    message_id = msg.get('Message-ID')
    if message_id:
        message_id = str(make_header(decode_header(message_id)))

    return Email.objects.create(
        email_original=email_original,
        remetente=remetente,
        destinatario=destinatario,
        assunto=assunto or "",
        mensagem=corpo,
        email_id=message_id,
    )

def salvar_anexos(msg, email_obj, uid):
    for part in msg.walk():
        cdisp = part.get_content_disposition()

        # aceitar inline se for arquivo
        if cdisp not in ("attachment", "inline"):
            continue

        filename = part.get_filename()
        if not filename:
            # sem filename? provavelmente não é um anexo de verdade
            continue

        filename = str(make_header(decode_header(filename)))

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        safe_name = f"{int(time.time())}_{uid}_{filename}"

        anexo = AnexoEmail(email=email_obj, caminhoArquivo=filename)
        anexo.arquivo.save(safe_name, ContentFile(payload), save=False)
        anexo.tamanho = getattr(anexo.arquivo, 'size', None)
        anexo.save()

def processar_email_unico(clienteEmail, uid, dados):
    emailBruto = dados.get(b'RFC822')
    if not emailBruto:
        return False

    msg = message_from_bytes(emailBruto)

    email_original = buscar_email_original(msg)
    corpo = extrair_corpo(msg)

    with transaction.atomic():
        novo_email = salvar_email(msg, email_original, corpo)
        salvar_anexos(msg, novo_email, uid)

    clienteEmail.add_flags(uid, [b'\\Seen'])
    return True

def processar_emails(clienteEmail, emails_fetch):
    novas = 0
    for uid, dados in emails_fetch.items():
        if processar_email_unico(clienteEmail, uid, dados):
            novas += 1
    return novas

def tem_caractere_especial(texto:str) -> bool:
    return bool(re.search(r"[^A-Za-z0-9\s.,!?]", texto))

def buscar_id_email(assunto_busca:str, email_destinatario:str) -> str | None:
    from email import message_from_bytes

    clienteEmail = conectar_email_IMAP("[Gmail]/Sent Mail")
    if tem_caractere_especial(assunto_busca):
        mensagens = clienteEmail.search(['HEADER', 'To', email_destinatario])
    else:    
        mensagens = clienteEmail.search(['HEADER', 'Subject', assunto_busca])

    if not mensagens:
        print("Nenhum e-mail com esse assunto.")
        return None

    uid = mensagens[-1]
    dados = clienteEmail.fetch(uid, ['RFC822'])
    raw_email = dados[uid][b'RFC822']

    msg = message_from_bytes(raw_email)
    msgid = msg.get('Message-ID')

    if msgid:
        return str(make_header(decode_header(msgid)))

    return None