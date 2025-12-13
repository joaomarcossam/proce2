from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .forms import CustomPasswordResetForm 

from . import views

urlpatterns = [
    # --- Autenticação ---
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # --- Dashboard Principal ---
    path('', views.dashboard, name='dashboard'),

    # --- Cadastros ---
    path('cadastrar/', views.cadastrar_projeto, name='cadastrar_projeto'),
    path('cadastrar-relator/', views.cadastrar_relator, name='cadastrar_relator'),
    path('projeto/<int:projeto_id>/nova-emenda/', views.cadastrar_emenda, name='cadastrar_emenda'),
    
    # --- Fluxo de Análise ---
    path('projeto/<int:pk>/', views.detalhe_projeto, name='detalhe_projeto'),
    path('projeto/<int:pk>/designar/', views.designar_relator, name='designar_relator'),
    path('projeto/<int:pk>/parecer/', views.dar_parecer, name='dar_parecer'),

    # --- API ---
    path('api/pb-login/', views.receber_credenciais_pb, name='receber_credenciais_pb'),

    # --- EXPORTAÇÃO  ---
    path('exportar-relatores/', views.exportar_relatores, name='exportar_relatores'),
    
     # --- RECUPERAÇÃO DE SENHA ---
    path('reset_password/', 
         auth_views.PasswordResetView.as_view(
             template_name="registration/password_reset_form.html",
             form_class=CustomPasswordResetForm, 
             from_email="santosjulialuiza@gmail.com" 
         ), 
         name="password_reset"
    ),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name="password_reset_complete"),


    path('emenda/<int:pk>/parecer/', views.dar_parecer_emenda, name='dar_parecer_emenda'),
    path('emenda/<int:pk>/', views.detalhe_emenda, name='detalhe_emenda'),

    path('projeto/<int:pk>/editar/', views.editar_projeto, name='editar_projeto'),


]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)