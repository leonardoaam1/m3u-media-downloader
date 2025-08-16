#!/usr/bin/env python3
from app import create_app, db
from app.models.users import User, UserRole

app = create_app()

with app.app_context():
    admin_user = User.query.filter_by(username='admin').first()
    
    if admin_user:
        print('Usuário admin já existe!')
        print(f'Username: {admin_user.username}')
        print(f'Email: {admin_user.email}')
        print(f'Role: {admin_user.role}')
    else:
        admin_user = User(
            username='admin',
            email='admin@mediadown.com',
            password='admin123',
            role=UserRole.ADMIN
        )
        
        db.session.add(admin_user)
        db.session.commit()
        
        print('✅ Usuário administrador criado com sucesso!')
        print('Username: admin')
        print('Senha: admin123')
        print('Email: admin@mediadown.com')
        print('Role: ADMIN')
