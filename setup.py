import os
import django

# Configura o ambiente do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proce.settings')
django.setup()

from django.contrib.auth.models import User, Group

def criar_dados_iniciais():
    print("--- Iniciando configuração ---")

    # 1. Criar Grupos
    grupo_gestores, created = Group.objects.get_or_create(name='Gestores')
    if created:
        print("Grupo 'Gestores' criado.")
    
    grupo_relatores, created = Group.objects.get_or_create(name='Relatores')
    if created:
        print("Grupo 'Relatores' criado.")

    # 2. Criar Superusuário (Admin)
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@exemplo.com', '123')
        print("Superusuário 'admin' criado (senha: 123).")

    # 3. Criar Usuário Gestor
    if not User.objects.filter(username='gestor').exists():
        u_gestor = User.objects.create_user('gestor', 'gestor@exemplo.com', '123')
        grupo_gestores.user_set.add(u_gestor)
        print("Usuário 'gestor' criado (senha: 123).")

    # 4. Criar Usuário Relator
    if not User.objects.filter(username='relator').exists():
        u_relator = User.objects.create_user('relator', 'relator@exemplo.com', '123')
        grupo_relatores.user_set.add(u_relator)
        print("Usuário 'relator' criado (senha: 123).")

    print("--- Configuração concluída com sucesso! ---")

if __name__ == '__main__':
    criar_dados_iniciais()