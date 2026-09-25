from flask import render_template
from flask_login import login_required, current_user
from app.models import db, Transaction, Budget, SavingsGoal
from datetime import datetime
from sqlalchemy import func
from . import dashboard_bp

def calculate_financial_health(income, expenses, goals):
    # Base starting points
    score = 0
    
    # 1. Savings Rate (40 points max)
    # Savings Rate = (Income - Expenses) / Income
    if income > 0:
        savings = income - expenses
        savings_rate = savings / income
        if savings_rate >= 0.3:  # 30% or more savings rate is excellent
            score += 40
        elif savings_rate > 0:
            score += int(savings_rate * (40 / 0.3))
    else:
        # No income recorded this month
        score += 0
        
    # 2. Expense control (30 points max)
    if income > 0:
        expense_ratio = expenses / income
        if expense_ratio <= 0.5:  # 50% or less goes to expenses
            score += 30
        elif expense_ratio <= 0.8:  # 80% or less
            score += 15
    else:
        score += 0
        
    # 3. Savings Goals progress (30 points max)
    if goals:
        total_progress = sum([g.progress_percentage for g in goals])
        avg_progress = total_progress / len(goals)
        score += int(avg_progress * (30 / 100))
    else:
        # No goals set, give a baseline 15 points for potential goals
        score += 15
        
    # Ensure score is within 0-100
    score = max(0, min(100, score))
    
    # Status text
    if score >= 80:
        status = 'Excellent'
        class_name = 'success'
    elif score >= 60:
        status = 'Good'
        class_name = 'info'
    elif score >= 40:
        status = 'Average'
        class_name = 'warning'
    else:
        status = 'Needs Attention'
        class_name = 'danger'
        
    return score, status, class_name

@dashboard_bp.route('/')
@login_required
def index():
    # Current month string (YYYY-MM)
    current_date = datetime.utcnow()
    current_month_str = current_date.strftime('%Y-%m')
    
    # 1. Transactions calculations
    # Total Balance (all time)
    total_income_all = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'income'
    ).scalar() or 0.0
    
    total_expense_all = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id, Transaction.type == 'expense'
    ).scalar() or 0.0
    
    total_balance = total_income_all - total_expense_all
    
    # Monthly Income & Expenses
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'income',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).scalar() or 0.0
    
    monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).scalar() or 0.0
    
    savings = monthly_income - monthly_expense
    
    # 2. Budgets calculation
    # Total Budget Limits set for this month
    total_budget_limit = db.session.query(func.sum(Budget.amount_limit)).filter(
        Budget.user_id == current_user.id,
        Budget.month == current_month_str
    ).scalar() or 0.0
    
    budget_remaining = 0.0
    if total_budget_limit > 0:
        budget_remaining = total_budget_limit - monthly_expense
    else:
        # Fallback to monthly income goal if budget is not set
        budget_remaining = max(0.0, current_user.monthly_income_goal - monthly_expense)
    
    # 3. Savings Goals
    goals = SavingsGoal.query.filter_by(user_id=current_user.id).all()
    
    # 4. Recent Transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(
        Transaction.date.desc(), Transaction.id.desc()
    ).limit(5).all()
    
    # 5. Financial Health Score
    health_score, health_status, health_class = calculate_financial_health(monthly_income, monthly_expense, goals)
    
    return render_template(
        'dashboard/index.html',
        total_balance=total_balance,
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        savings=savings,
        budget_limit=total_budget_limit,
        budget_remaining=budget_remaining,
        recent_transactions=recent_transactions,
        health_score=health_score,
        health_status=health_status,
        health_class=health_class,
        current_month=current_date.strftime('%B %Y')
    )
