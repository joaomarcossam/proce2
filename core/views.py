from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
import json
import csv
import io
from functools import wraps
from .models import Projeto, Pesquisador, Emenda, PlataformaBrasilService, Parecer
from .forms import DesignarRelatorForm, ParecerForm, ProjetoForm, EmendaForm, CadastroRelatorForm

# --- DECORATORS E AUXILIARES ---
def grupo_requerido(nome_grupo):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not request.user.groups.filter(name=nome_grupo).exists():
                return HttpResponseForbidden("Você não tem permissão para acessar esta página.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def is_grupo(user, nome_grupo):
    return user.groups.filter(name=nome_grupo).exists()

def is_gestor(user):
    return is_grupo(user, 'Gestores') or user.is_superuser

def is_relator(user):
    return is_grupo(user, 'Relatores')

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
                    email=email_pesq,
                    defaults={'nome': nome_pesq}
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

# --- VIEWS PRINCIPAIS ---

@login_required
def dashboard(request):
    """
    Página inicial (Dashboard) que muda conforme o grupo do usuário.
    """
    
    # 1. VISÃO DO GESTOR
    if is_gestor(request.user):
        projetos_novos_query = Projeto.objects.filter(status='novo').order_by('-data_submissao')
        projetos_em_analise = Projeto.objects.filter(status='em_analise').order_by('-data_submissao')
        projetos_concluidos = Projeto.objects.filter(status__in=['aprovado', 'reprovado']).order_by('-data_submissao')
        
        # Busca Relatores e seus projetos
        relatores_stats = User.objects.filter(groups__name='Relatores').prefetch_related('projetos_designados')
        
        contexto = {
            'projetos_para_designar': projetos_novos_query, 
            'projetos_em_analise': projetos_em_analise,
            'projetos_concluidos': projetos_concluidos,
            'relatores_stats': relatores_stats,
        }
        return render(request, 'core/dashboard_gestor.html', contexto)

    # 2. VISÃO DO RELATOR
    elif is_relator(request.user):
        projetos_para_analisar = Projeto.objects.filter(
            relator_designado=request.user, 
            status='em_analise'
        )
        meus_projetos_concluidos = Projeto.objects.filter(
            relator_designado=request.user
        ).exclude(status__in=['novo', 'em_analise'])

        contexto = {
            'projetos_para_analisar': projetos_para_analisar,
            'meus_projetos_concluidos': meus_projetos_concluidos,
        }
        return render(request, 'core/dashboard_relator.html', contexto)
    
    # 3. SEM GRUPO
    else:
        return render(request, 'core/dashboard_generico.html', {'mensagem_erro': 'Usuário sem grupo definido.'})

@login_required
def cadastrar_projeto(request):
    if not is_gestor(request.user):
        return HttpResponseForbidden("Apenas gestores podem cadastrar projetos.")

    form = ProjetoForm()
    mensagem = None

    if request.method == 'POST':
        if 'csv_file' in request.FILES:
            qtd = processar_csv(request.FILES['csv_file'])
            return redirect('dashboard')
        else:
            form = ProjetoForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                return redirect('dashboard')

    return render(request, 'core/cadastrar_projeto.html', {'form': form, 'mensagem': mensagem})

@login_required
def cadastrar_relator(request):
    if not is_gestor(request.user):
        return HttpResponseForbidden("Apenas gestores podem cadastrar relatores.")

    if request.method == 'POST':
        form = CadastroRelatorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = CadastroRelatorForm()

    return render(request, 'core/cadastrar_relator.html', {'form': form})

@login_required
@grupo_requerido('Gestores')
def designar_relator(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    if projeto.status in ['aprovado', 'reprovado']:
        return HttpResponseForbidden("Não é possível alterar o relator de um projeto já concluído.")

    if request.method == 'POST':
        form = DesignarRelatorForm(request.POST, instance=projeto)
        if form.is_valid():
            projeto = form.save(commit=False)
            projeto.status = 'em_analise'
            projeto.save()
            return redirect('dashboard')
    else:
        form = DesignarRelatorForm(instance=projeto)

    return render(request, 'core/designar_relator.html', {'form': form, 'projeto': projeto})

@login_required
@grupo_requerido('Relatores')
def dar_parecer(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)

    if request.user != projeto.relator_designado:
        return HttpResponseForbidden("Você não é o relator deste projeto.")

    if request.method == 'POST':
        form = ParecerForm(request.POST)
        if form.is_valid():
            parecer = form.save(commit=False)
            parecer.projeto = projeto
            parecer.relator = request.user
            parecer.save()

            projeto.status = parecer.decisao 
            if parecer.decisao == 'aprovado':
                projeto.data_aprovacao = timezone.now().date()
            projeto.save()
            
            return redirect('dashboard')
    else:
        form = ParecerForm()

    return render(request, 'core/dar_parecer.html', {'form': form, 'projeto': projeto})

@login_required
def cadastrar_emenda(request, projeto_id):
    projeto = get_object_or_404(Projeto, pk=projeto_id)
    
    if request.method == 'POST':
        form = EmendaForm(request.POST, request.FILES)
        if form.is_valid():
            emenda = form.save(commit=False)
            emenda.projeto = projeto
            emenda.save()
            return redirect('detalhe_projeto', pk=projeto.id)
    else:
        form = EmendaForm()
    
    return render(request, 'core/cadastrar_emenda.html', {'form': form, 'projeto': projeto})

@login_required
def detalhe_projeto(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    
    if is_relator(request.user) and not is_gestor(request.user):
        if projeto.relator_designado != request.user:
            return HttpResponseForbidden()

    pareceres = projeto.pareceres.all().order_by('-data_parecer')

    return render(request, 'core/detalhe_projeto.html', {'projeto': projeto, 'pareceres': pareceres})

@csrf_exempt
def receber_credenciais_pb(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            senha = data.get('senha')
            PlataformaBrasilService.receber_credenciais(email, senha)
            return JsonResponse({'status': 'ok', 'msg': 'Credenciais recebidas com sucesso!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)
    return JsonResponse({'status': 'error'}, status=400)

# --- FUNÇÃO DE EXPORTAÇÃO DE CSV---
@login_required
def exportar_relatores(request):
    if not is_gestor(request.user):
        return HttpResponseForbidden("Apenas gestores podem exportar dados.")
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatores_projetos.csv"'
  
    writer = csv.writer(response)
    # Cabeçalho do arquivo
    writer.writerow(['Nome do Relator', 'E-mail', 'Projeto', 'CAAE', 'Status', 'Data Submissão'])
    
    # Busca dados
    relatores = User.objects.filter(groups__name='Relatores').prefetch_related('projetos_designados')
    
    for relator in relatores:
        projetos = relator.projetos_designados.all()
        if projetos:
            for projeto in projetos:
                writer.writerow([
                    relator.first_name or relator.username,
                    relator.email,
                    projeto.titulo,
                    projeto.caae,
                    projeto.get_status_display(),
                    projeto.data_submissao.strftime("%d/%m/%Y")
                ])
        else:
            # Se o relator não tiver projetos, cria uma linha indicando isso
             writer.writerow([
                relator.first_name or relator.username,
                relator.email,
                "Nenhum projeto designado",
                "-",
                "-",
                "-"
            ])
            
    return response