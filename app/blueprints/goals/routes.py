from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, SavingsGoal
from datetime import datetime
from . import goals_bp

@goals_bp.route('/')
@login_required
def index():
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.created_at.desc()).all()
    return render_template('goals/list.html', goals=goals)

@goals_bp.route('/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name')
    target_amount = request.form.get('target_amount')
    current_amount = request.form.get('current_amount', 0.0)
    target_date_str = request.form.get('target_date')
    
    if not name or not target_amount:
        flash('Name and Target Amount are required.', 'danger')
        return redirect(url_for('goals.index'))
        
    try:
        target_val = float(target_amount)
        current_val = float(current_amount) if current_amount else 0.0
        if target_val <= 0 or current_val < 0:
            flash('Amounts must be valid positive numbers.', 'danger')
            return redirect(url_for('goals.index'))
    except ValueError:
        flash('Invalid numeric inputs.', 'danger')
        return redirect(url_for('goals.index'))
        
    target_date = None
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    goal = SavingsGoal(
        user_id=current_user.id,
        name=name,
        target_amount=target_val,
        current_amount=current_val,
        target_date=target_date
    )
    db.session.add(goal)
    db.session.commit()
    flash('Savings goal created successfully!', 'success')
    return redirect(url_for('goals.index'))

@goals_bp.route('/add-funds/<int:goal_id>', methods=['POST'])
@login_required
def add_funds(goal_id):
    goal = SavingsGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('goals.index'))
        
    amount = request.form.get('amount')
    if not amount:
        flash('Amount is required.', 'danger')
        return redirect(url_for('goals.index'))
        
    try:
        amount_val = float(amount)
        if amount_val <= 0:
            flash('Amount must be positive.', 'danger')
            return redirect(url_for('goals.index'))
    except ValueError:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('goals.index'))
        
    goal.current_amount += amount_val
    # Bound to target amount
    if goal.current_amount > goal.target_amount:
        goal.current_amount = goal.target_amount
        flash(f'Congratulations! You have fully funded your goal: {goal.name}!', 'success')
    else:
        flash(f'Added ₹{amount_val:,.2f} to {goal.name}.', 'success')
        
    db.session.commit()
    return redirect(url_for('goals.index'))

@goals_bp.route('/edit/<int:goal_id>', methods=['GET', 'POST'])
@login_required
def edit(goal_id):
    goal = SavingsGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('goals.index'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        target_amount = request.form.get('target_amount')
        current_amount = request.form.get('current_amount')
        target_date_str = request.form.get('target_date')
        
        if not name or not target_amount or not current_amount:
            flash('Name, Target Amount, and Current Amount are required.', 'danger')
            return redirect(url_for('goals.edit', goal_id=goal.id))
            
        try:
            target_val = float(target_amount)
            current_val = float(current_amount)
            if target_val <= 0 or current_val < 0:
                flash('Amounts must be positive.', 'danger')
                return redirect(url_for('goals.edit', goal_id=goal.id))
        except ValueError:
            flash('Invalid numeric inputs.', 'danger')
            return redirect(url_for('goals.edit', goal_id=goal.id))
            
        target_date = None
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
                
        goal.name = name
        goal.target_amount = target_val
        goal.current_amount = current_val
        goal.target_date = target_date
        
        db.session.commit()
        flash('Savings goal updated successfully!', 'success')
        return redirect(url_for('goals.index'))
        
    return render_template('goals/edit.html', goal=goal)

@goals_bp.route('/delete/<int:goal_id>', methods=['POST'])
@login_required
def delete(goal_id):
    goal = SavingsGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('goals.index'))
        
    db.session.delete(goal)
    db.session.commit()
    flash('Savings goal deleted.', 'success')
    return redirect(url_for('goals.index'))
