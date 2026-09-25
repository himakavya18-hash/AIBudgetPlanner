from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
from . import auth_bp

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))
            
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username is already taken.', 'danger')
            return redirect(url_for('auth.register'))
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email is already registered.', 'danger')
            return redirect(url_for('auth.register'))
            
        # Create user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.username}!', 'success')
        
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        monthly_income_goal = request.form.get('monthly_income_goal')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate unique username/email
        if username != current_user.username:
            existing = User.query.filter_by(username=username).first()
            if existing:
                flash('Username already exists.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.username = username
            
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash('Email already registered.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.email = email
            
        if monthly_income_goal:
            try:
                current_user.monthly_income_goal = float(monthly_income_goal)
            except ValueError:
                flash('Invalid monthly income goal value.', 'danger')
                return redirect(url_for('auth.profile'))
                
        if new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_password)
            
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('No account with that email found.', 'danger')
            return redirect(url_for('auth.reset_password'))
            
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.reset_password'))
            
        user.set_password(new_password)
        db.session.commit()
        flash('Password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')
