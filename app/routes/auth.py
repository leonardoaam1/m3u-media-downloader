from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.users import User, UserRole
from app.services.logging_service import LoggingService
from app import db
import bcrypt

auth_bp = Blueprint('auth', __name__)
logger = LoggingService()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Conta desativada. Entre em contato com o administrador.', 'error')
                return render_template('auth/login.html')
            
            login_user(user)
            from datetime import datetime
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # logger.log_user_activity(
            #     user.id,
            #     'login',
            #     {'ip': request.remote_addr, 'user_agent': request.headers.get('User-Agent')}
            # )
            
            flash(f'Bem-vindo, {user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated:
        logger.log_user_activity(
            current_user.id,
            'logout',
            {'ip': request.remote_addr}
        )
    
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('auth/change_password.html')
        
        if not current_user.check_password(current_password):
            flash('Senha atual incorreta.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres.', 'error')
            return render_template('auth/change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        
        logger.log_user_activity(
            current_user.id,
            'change_password',
            {'ip': request.remote_addr}
        )
        
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Por favor, informe seu email.', 'error')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # TODO: Implement email sending for password reset
            flash('Um email foi enviado com instruções para redefinir sua senha.', 'info')
        else:
            flash('Email não encontrado.', 'error')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')








