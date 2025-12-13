import csv
import io
import json
from datetime import datetime # Importação necessária para converter strings em data
from django.forms import formset_factory
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
import pandas as pd
from django.db.models import Q 

from functools import wraps
from itertools import chain
from operator import attrgetter
from webdriver.plataforma_brasil import PlataformaBrasilService
from .forms import (
    CadastroRelatorForm,
    DesignarRelatorForm, 
    ParecerForm, ParecerEmendaForm,
    ProjetoForm, EmendaForm,
)
from .models import Projeto, Pesquisador, Emenda, Parecer


# --- DECORATORS E AUXILIARES ---
def grupo_requerido(grupos):
    if isinstance(grupos, str): grupos = [grupos]
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated: return redirect('login')
            if request.user.is_superuser or request.user.groups.filter(name__in=grupos).exists():
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Você não tem permissão para acessar esta página.")
        return _wrapped_view
    return decorator

def is_grupo(user, nome_grupo): return user.groups.filter(name=nome_grupo).exists()
def is_gestor(user): return is_grupo(user, 'Gestores') or user.is_superuser
def is_relator(user): return is_grupo(user, 'Relatores')

def processar_csv(csv_file):
    try:
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string, delimiter=',')
        projetos_criados = 0
        for row in reader:
            email_pesq = row.get('EmailPesq')
            nome_pesq = row.get('NomePesq', 'Pesquisador Desconhecido')
            if email_pesq:
                pesquisador, created = Pesquisador.objects.get_or_create(
                    email=email_pesq, defaults={'nome': nome_pesq}
                )
                Projeto.objects.create(
                    titulo=row.get('Titulo', 'Sem Título'),
                    descricao=row.get('Descricao', ''),
                    caae=row.get('CAAE'),
                    pesquisador=pesquisador,
                    status='novo'
                )
                projetos_criados += 1
        return projetos_criados
    except Exception as e:
        print(f"Erro no CSV: {e}")
        return 0

def enviar_email_pendencia(projeto, motivo="Pendências identificadas pelo relator."):
    if projeto.pesquisador.email:
        assunto = f"Pendência no Projeto: {projeto.titulo}"
        mensagem = f"""
        Prezado(a) {projeto.pesquisador.nome},
        O seu projeto "{projeto.titulo}" (CAAE: {projeto.caae}) consta com PENDÊNCIAS.
        Observação: {motivo}
        Por favor, acesse a plataforma para regularizar.
        """
        try:
            send_mail(assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [projeto.pesquisador.email], fail_silently=True)
            print(f"📧 E-mail enviado para {projeto.pesquisador.email}")
        except Exception as e:
            print(f"❌ Erro ao enviar e-mail: {e}")

@login_required
def dashboard(request):
    if is_gestor(request.user):
        itens_novos = list(Projeto.objects.filter(status='novo'))
        for i in itens_novos: i.tipo_item = 'P'

        projetos_analise = list(Projeto.objects.filter(status='em_analise'))
        for p in projetos_analise: p.tipo_item = 'P'
        emendas_analise = list(Emenda.objects.filter(status='pendente'))
        for e in emendas_analise: e.tipo_item = 'E'
        itens_em_analise = sorted(chain(projetos_analise, emendas_analise), key=attrgetter('data_submissao'), reverse=True)
        
        itens_pendentes = list(Projeto.objects.filter(status='pendente'))
        for p in itens_pendentes: p.tipo_item = 'P'

        projetos_concluidos = list(Projeto.objects.filter(status__in=['aprovado', 'reprovado']))
        for p in projetos_concluidos: p.tipo_item = 'P'
        emendas_concluidas = list(Emenda.objects.filter(status__in=['aprovada', 'reprovada']))
        for e in emendas_concluidas: e.tipo_item = 'E'
        itens_concluidos = sorted(chain(projetos_concluidos, emendas_concluidas), key=attrgetter('data_submissao'), reverse=True)

        relatores_stats = User.objects.filter(groups__name='Relatores').prefetch_related('projetos_designados')
        
        contexto = {
            'itens_novos': itens_novos,
            'itens_em_analise': itens_em_analise,
            'itens_pendentes': itens_pendentes,
            'itens_concluidos': itens_concluidos,
            'relatores_stats': relatores_stats,
        }
        return render(request, 'core/dashboard_gestor.html', contexto)

    elif is_relator(request.user):
        meus_projetos = list(Projeto.objects.filter(
            relator_designado=request.user, 
            status__in=['em_analise', 'pendente']
        ))
        for p in meus_projetos: p.tipo_item = 'P'

        minhas_emendas = list(Emenda.objects.filter(projeto__relator_designado=request.user, status='pendente'))
        for e in minhas_emendas: e.tipo_item = 'E'
        itens_para_analisar = sorted(chain(meus_projetos, minhas_emendas), key=attrgetter('data_submissao'), reverse=True)
        
        hist_p = list(Projeto.objects.filter(relator_designado=request.user).exclude(status__in=['novo', 'em_analise', 'pendente']))
        for p in hist_p: p.tipo_item = 'P'
        hist_e = list(Emenda.objects.filter(projeto__relator_designado=request.user).exclude(status='pendente'))
        for e in hist_e: e.tipo_item = 'E'
        itens_concluidos = sorted(chain(hist_p, hist_e), key=attrgetter('data_submissao'), reverse=True)
        
        contexto = {'projetos_para_analisar': itens_para_analisar, 'meus_projetos_concluidos': itens_concluidos}
        return render(request, 'core/dashboard_relator.html', contexto)
    else:
        return render(request, 'core/dashboard_generico.html', {'mensagem_erro': 'Usuário sem grupo definido.'})


@login_required
def cadastrar_projeto(request):
    if not is_gestor(request.user):
        return HttpResponseForbidden("Apenas gestores podem cadastrar projetos.")

    ProjetoFormSet = formset_factory(ProjetoForm, extra=0)
    form = ProjetoForm()
    formset = None
    mensagem = None
    aba_ativa = 'manual'

    if request.method == 'POST':
        if 'arquivo_importacao' in request.FILES:
            arquivo = request.FILES['arquivo_importacao']
            try:
                if arquivo.name.endswith('.csv'):
                    df = pd.read_csv(arquivo)
                else:
                    try: df = pd.read_excel(arquivo, engine='openpyxl')
                    except: 
                        try: df = pd.read_excel(arquivo, engine='xlrd')
                        except: df = pd.read_excel(arquivo)

                df.columns = df.columns.str.strip()
                dados_iniciais = []
                
                for index, row in df.iterrows():
                    caae = str(row.get('CAAE', '')).strip()
                    if caae == 'nan': caae = ''
                    titulo = str(row.get('Titulo') or row.get('Título do Projeto') or f'Projeto Importado {caae}').strip()
                    nome_pesq = str(row.get('Nome Pesquisador') or row.get('Pesquisador') or '').strip()
                    if nome_pesq == 'nan': nome_pesq = ''
                    email_pesq = str(row.get('Email') or '').strip()
                    if email_pesq == 'nan': email_pesq = ''
                    
                    relator_texto = str(row.get('RELATOR') or row.get('Relator') or '').strip()
                    if relator_texto == 'nan': relator_texto = ''
                    
                    relator_id = None
                    if relator_texto:
                        primeiro_nome = relator_texto.split()[0]
                        user_relator = User.objects.filter(
                            Q(first_name__icontains=primeiro_nome) | 
                            Q(username__icontains=primeiro_nome),
                            groups__name='Relatores'
                        ).first()
                        if user_relator:
                            relator_id = user_relator.id

                    descricao = str(row.get('Descricao') or row.get('Descrição') or 'Importado via planilha.').strip()
                    if descricao == 'nan': descricao = ''

                    status_detectado = 'novo'
                    data_parecer_detectada = None
                    cols_reuniao = [c for c in df.columns if 'Reunião' in str(c)]
                    
                    for col in cols_reuniao:
                        val = str(row.get(col, '')).strip().upper()
                        
                        # ---LÓGICA DE EXTRAÇÃO DE DATA ---
                        # Tenta extrair a data do cabeçalho da coluna (ex: "Reunião:01/09")
                        # Se não conseguir, usa data de hoje 
                        data_extraida = timezone.now().date()
                        try:
                            # Divide por ':' ou espaço para pegar "01/09"
                            if ':' in col:
                                str_data = col.split(':')[-1].strip()
                            else:
                                str_data = col.split()[-1].strip()
                            
                            # Tenta converter dd/mm para data com ano atual
                            dia, mes = str_data.split('/')
                            ano_atual = timezone.now().year
                            data_extraida = datetime(ano_atual, int(mes), int(dia)).date()
                        except:
                            # Se der erro no parse (ex: formato diferente), mantém a data de hoje
                            pass

                        if 'PENDENCIA' in val or 'PENDÊNCIA' in val:
                            status_detectado = 'pendente'
                            data_parecer_detectada = data_extraida
                        elif 'APROVADO' in val:
                            status_detectado = 'aprovado'
                            data_parecer_detectada = data_extraida
                        elif 'REPROVADO' in val:
                            status_detectado = 'reprovado'
                            data_parecer_detectada = data_extraida

                    if relator_id and status_detectado == 'novo':
                        status_detectado = 'em_analise'

                    dados_iniciais.append({
                        'caae': caae,
                        'titulo': titulo,
                        'descricao': descricao,
                        'pesquisador_nome': nome_pesq,
                        'pesquisador_email': email_pesq,
                        'status_inicial': status_detectado,
                        'relator_nome_texto': relator_texto,
                        'relator_designado': relator_id,
                        'data_parecer_manual': data_parecer_detectada if status_detectado != 'novo' else None,
                    })
                
                formset = ProjetoFormSet(initial=dados_iniciais)
                aba_ativa = 'csv'
                mensagem = "Planilha lida! Por favor, PREENCHA OS E-MAILS FALTANTES e verifique os Relatores na tabela abaixo."

            except Exception as e:
                mensagem = f"Erro crítico ao ler arquivo: {str(e)}. Verifique se é um Excel válido."
                aba_ativa = 'csv'

        elif 'form-TOTAL_FORMS' in request.POST:
            formset = ProjetoFormSet(request.POST)
            aba_ativa = 'csv'
            if formset.is_valid():
                salvos = 0
                for f in formset:
                    if f.cleaned_data.get('caae'):
                        projeto = f.save(commit=False)
                        status = f.cleaned_data.get('status_inicial')
                        projeto.status = status
                        
                        if status == 'aprovado':
                            projeto.data_aprovacao = f.cleaned_data.get('data_parecer_manual') or timezone.now().date()
                        
                        projeto.save() 
                        
                        data_hist = f.cleaned_data.get('data_parecer_manual')
                        
                        if status == 'pendente':
                             enviar_email_pendencia(projeto, "Pendência identificada na importação inicial.")
                             if data_hist:
                                Parecer.objects.create(
                                    projeto=projeto,
                                    relator=projeto.relator_designado if projeto.relator_designado else request.user,
                                    decisao='pendente',
                                    justificativa="Importação de histórico: Pendência.",
                                    data_parecer=data_hist
                                )
                        elif status == 'aprovado' and data_hist:
                             Parecer.objects.create(
                                projeto=projeto,
                                relator=projeto.relator_designado if projeto.relator_designado else request.user,
                                decisao='aprovado',
                                justificativa="Importação de histórico: Aprovado.",
                                data_parecer=data_hist
                             )
                        elif status == 'reprovado' and data_hist:
                             Parecer.objects.create(
                                projeto=projeto,
                                relator=projeto.relator_designado if projeto.relator_designado else request.user,
                                decisao='reprovado',
                                justificativa="Importação de histórico: Reprovado.",
                                data_parecer=data_hist
                             )

                        salvos += 1
                return redirect('dashboard')
            else:
                mensagem = "Existem erros no formulário. Verifique os campos em vermelho."

        else:
            form = ProjetoForm(request.POST, request.FILES)
            if form.is_valid():
                projeto = form.save(commit=False)
                status = form.cleaned_data.get('status_inicial')
                projeto.status = status
                
                if projeto.relator_designado and status == 'novo':
                    projeto.status = 'em_analise'
                
                if status == 'pendente':
                    enviar_email_pendencia(projeto, "Pendência cadastrada manualmente.")
                if status == 'aprovado' and not projeto.data_aprovacao:
                     projeto.data_aprovacao = timezone.now().date()
                
                projeto.save()
                
                data_hist = form.cleaned_data.get('data_parecer_manual')
                if data_hist:
                    Parecer.objects.create(
                        projeto=projeto,
                        relator=projeto.relator_designado if projeto.relator_designado else request.user, 
                        decisao=status if status in ['aprovado', 'reprovado', 'pendente'] else 'pendente',
                        justificativa="Importação de histórico manual.",
                        data_parecer=data_hist
                    )
                
                return redirect('dashboard')

    return render(request, 'core/cadastrar_projeto.html', {
        'form': form, 
        'formset': formset, 
        'mensagem': mensagem, 
        'aba_ativa': aba_ativa
    })

@login_required
def cadastrar_relator(request):
    if not is_gestor(request.user): return HttpResponseForbidden("Apenas gestores.")
    if request.method == 'POST':
        form = CadastroRelatorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else: form = CadastroRelatorForm()
    return render(request, 'core/cadastrar_relator.html', {'form': form})

@login_required
@grupo_requerido('Gestores')
def designar_relator(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.method == 'POST':
        form = DesignarRelatorForm(request.POST, instance=projeto)
        if form.is_valid():
            projeto = form.save(commit=False)
            projeto.status = 'em_analise'
            projeto.save()
            return redirect('dashboard')
    else: form = DesignarRelatorForm(instance=projeto)
    return render(request, 'core/designar_relator.html', {'form': form, 'projeto': projeto})

@login_required
@grupo_requerido(['Relatores', 'Gestores'])
def dar_parecer(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if not is_gestor(request.user) and request.user != projeto.relator_designado:
        return HttpResponseForbidden("Você não é o relator designado.")
        
    if request.method == 'POST':
        form = ParecerForm(request.POST, request.FILES)
        if form.is_valid():
            parecer = form.save(commit=False)
            parecer.projeto = projeto
            
            if projeto.relator_designado:
                parecer.relator = projeto.relator_designado
            else:
                parecer.relator = request.user 
            
            parecer.save()
            projeto.status = parecer.decisao 
            
            if parecer.decisao == 'pendente':
                enviar_email_pendencia(projeto, parecer.justificativa)
                projeto.data_aprovacao = None
            elif parecer.decisao == 'aprovado':
                projeto.data_aprovacao = timezone.now().date()
            
            projeto.save()
            return redirect('dashboard')
    else: form = ParecerForm()
    return render(request, 'core/dar_parecer.html', {'form': form, 'projeto': projeto})

@login_required
def cadastrar_emenda(request, projeto_id):
    projeto = get_object_or_404(Projeto, pk=projeto_id)
    if not is_gestor(request.user):
        return HttpResponseForbidden("Apenas gestores podem cadastrar emendas.")
    if request.method == 'POST':
        form = EmendaForm(request.POST, request.FILES)
        if form.is_valid():
            emenda = form.save(commit=False)
            emenda.projeto = projeto
            emenda.save()
            return redirect('detalhe_projeto', pk=projeto.id)
    else: form = EmendaForm()
    return render(request, 'core/cadastrar_emenda.html', {'form': form, 'projeto': projeto})

@login_required
def detalhe_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk) 
    pareceres = projeto.pareceres.all().order_by('-data_parecer')
    is_gestor_user = is_gestor(request.user)
    return render(request, 'core/detalhe_projeto.html', {
        'projeto': projeto, 
        'pareceres': pareceres,
        'is_gestor': is_gestor_user
    })

@csrf_exempt
def receber_credenciais_pb(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            senha = data.get('senha')
            pb_service = PlataformaBrasilService(user_email=email, user_password=senha, headless=True)
            pb_service.login()
            if pb_service.logged: pb_service.fetch_projects_form_table()
            return JsonResponse({'status': 'ok', 'msg': 'Credenciais recebidas com sucesso!'})
        except Exception as e: return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)

@login_required
def exportar_relatores(request):
    if not is_gestor(request.user): return HttpResponseForbidden("Apenas gestores.")
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatores_projetos.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nome do Relator', 'E-mail', 'Projeto', 'CAAE', 'Status', 'Data Submissão'])
    relatores = User.objects.filter(groups__name='Relatores').prefetch_related('projetos_designados')
    for relator in relatores:
        projetos = relator.projetos_designados.all()
        if projetos:
            for projeto in projetos:
                writer.writerow([relator.first_name or relator.username, relator.email, projeto.titulo, projeto.caae, projeto.get_status_display(), projeto.data_submissao.strftime("%d/%m/%Y")])
        else: writer.writerow([relator.first_name or relator.username, relator.email, "Nenhum projeto designado", "-", "-", "-"])
    return response

@login_required
@grupo_requerido(['Relatores', 'Gestores'])
def dar_parecer_emenda(request, pk):
    emenda = get_object_or_404(Emenda, pk=pk)
    if not is_gestor(request.user):
        if request.user != emenda.projeto.relator_designado: return HttpResponseForbidden("Você não é o relator.")
    if request.method == 'POST':
        form = ParecerEmendaForm(request.POST, instance=emenda)
        if form.is_valid():
            emenda = form.save(commit=False)
            if emenda.projeto.relator_designado:
                emenda.relator_parecer = emenda.projeto.relator_designado
            else:
                emenda.relator_parecer = request.user
            emenda.data_parecer = timezone.now()
            emenda.save()
            return redirect('dashboard')
    else: form = ParecerEmendaForm(instance=emenda)
    return render(request, 'core/dar_parecer_emenda.html', {'form': form, 'emenda': emenda})

@login_required
def detalhe_emenda(request, pk):
    emenda = get_object_or_404(Emenda, pk=pk)
    if is_relator(request.user) and not is_gestor(request.user):
        if emenda.projeto.relator_designado != request.user: return HttpResponseForbidden()
    return render(request, 'core/detalhe_emenda.html', {'emenda': emenda})

@login_required
def editar_projeto(request, pk):
    if not is_gestor(request.user): return HttpResponseForbidden("Apenas gestores.")
    projeto = get_object_or_404(Projeto, pk=pk)
    if request.method == 'POST':
        form = ProjetoForm(request.POST, request.FILES, instance=projeto)
        if form.is_valid():
            projeto = form.save(commit=False)
            novo_status = form.cleaned_data.get('status_inicial')
            if novo_status:
                projeto.status = novo_status
                if novo_status == 'pendente':
                    enviar_email_pendencia(projeto, "Status alterado para PENDENTE via edição.")
            projeto.save()
            return redirect('detalhe_projeto', pk=projeto.id)
    else:
        initial = {
            'status_inicial': projeto.status,
            'pesquisador_nome': projeto.pesquisador.nome,
            'pesquisador_email': projeto.pesquisador.email,
            'pesquisador_telefone': projeto.pesquisador.telefone,
            'data_aprovacao': projeto.data_aprovacao,
            'relator_designado': projeto.relator_designado
        }
        form = ProjetoForm(instance=projeto, initial=initial)
    return render(request, 'core/editar_projeto.html', {'form': form, 'projeto': projeto})