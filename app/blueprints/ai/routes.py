from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Transaction, Budget, SavingsGoal
from datetime import datetime, date, timedelta
from sqlalchemy import func
from . import ai_bp
from .services import (
    ai_categorize_expense,
    ai_parse_voice,
    ai_budget_suggestions,
    ai_spending_analysis,
    ai_saving_tips,
    ai_predict_expenses,
    ai_chatbot_response
)

def get_user_summary_data(user_id):
    current_date = datetime.utcnow()
    current_month_str = current_date.strftime('%Y-%m')
    
    # 1. Income & Expenses this month
    monthly_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).scalar() or 0.0
    
    monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).scalar() or 0.0
    
    # Total net balance (all time)
    total_inc = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0.0
    total_exp = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0.0
    total_balance = total_inc - total_exp
    
    # 2. Expenses grouped by category (current month)
    category_expenses = db.session.query(
        Transaction.category, func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).group_by(Transaction.category).all()
    
    expense_by_cat = {cat: amt for cat, amt in category_expenses}
    
    # 3. Previous Month's Expenses
    first_day_of_month = date.today().replace(day=1)
    last_day_of_prev_month = first_day_of_month - timedelta(days=1)
    prev_month_str = last_day_of_prev_month.strftime('%Y-%m')
    
    prev_monthly_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == prev_month_str
    ).scalar() or 0.0
    
    # 4. Savings Goals
    goals = SavingsGoal.query.filter_by(user_id=user_id).all()
    goals_info = ", ".join([f"{g.name}: {g.progress_percentage}% achieved" for g in goals]) if goals else "None"
    
    # 5. Saving Tips
    tips = ai_saving_tips(monthly_income, expense_by_cat)
    
    # Calculate savings rate
    savings_rate = 0.0
    if monthly_income > 0:
        savings_rate = ((monthly_income - monthly_expense) / monthly_income) * 100
        
    return {
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'total_balance': total_balance,
        'expenses_by_category': expense_by_cat,
        'prev_monthly_expense': prev_monthly_expense,
        'goals_info': goals_info,
        'saving_tips': tips,
        'savings_rate': savings_rate
    }

@ai_bp.route('/categorize', methods=['POST'])
@login_required
def categorize():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Missing text field'}), 400
        
    text = data['text']
    categories = current_app.config['EXPENSE_CATEGORIES']
    category = ai_categorize_expense(text, categories)
    return jsonify({'success': True, 'category': category})

@ai_bp.route('/parse-voice', methods=['POST'])
@login_required
def parse_voice():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Missing text field'}), 400
        
    text = data['text']
    categories = current_app.config['EXPENSE_CATEGORIES']
    parsed = ai_parse_voice(text, categories)
    return jsonify({'success': True, 'parsed': parsed})

@ai_bp.route('/suggestions', methods=['GET', 'POST'])
@login_required
def suggestions():
    income = current_user.monthly_income_goal
    if income <= 0:
        # Check if they have a recorded salary / income this month
        current_month_str = date.today().strftime('%Y-%m')
        income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'income',
            func.strftime('%Y-%m', Transaction.date) == current_month_str
        ).scalar() or 0.0
        
    # If still 0, default to standard fallback base
    if income <= 0:
        income = 50000.0  # Default reference income
        
    categories = current_app.config['EXPENSE_CATEGORIES']
    suggested_budget = ai_budget_suggestions(income, categories)
    
    # Handle applying suggested budgets
    if request.method == 'POST':
        month_str = date.today().strftime('%Y-%m')
        
        # Clear existing budgets for current month
        Budget.query.filter_by(user_id=current_user.id, month=month_str).delete()
        
        # Apply suggestions
        for cat, limit in suggested_budget.items():
            if cat in categories:
                b = Budget(
                    user_id=current_user.id,
                    category=cat,
                    amount_limit=float(limit),
                    month=month_str
                )
                db.session.add(b)
        db.session.commit()
        flash('AI suggested budgets applied successfully!', 'success')
        return redirect(url_for('transactions.budgets'))
        
    return render_template('ai/suggestions.html', suggestions=suggested_budget, income=income)

@ai_bp.route('/analysis')
@login_required
def analysis():
    summary = get_user_summary_data(current_user.id)
    
    # Spending Analysis Text
    spending_text = ai_spending_analysis(
        summary['monthly_income'],
        summary['expenses_by_category'],
        summary['prev_monthly_expense'],
        summary['goals_info']
    )
    
    # Predictions for next month
    # Fetch all user expenses for history
    transactions = Transaction.query.filter_by(user_id=current_user.id, type='expense').all()
    history = [{'amount': t.amount, 'category': t.category, 'type': t.type} for t in transactions]
    categories = current_app.config['EXPENSE_CATEGORIES']
    predictions = ai_predict_expenses(history, categories)
    
    return render_template(
        'ai/analysis.html',
        spending_text=spending_text,
        tips=summary['saving_tips'],
        predictions=predictions
    )

@ai_bp.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'success': False, 'error': 'Missing message field'}), 400
            
        message = data['message']
        summary = get_user_summary_data(current_user.id)
        
        # Inject standard profile details
        summary['username'] = current_user.username
        
        response = ai_chatbot_response(message, summary)
        return jsonify({'success': True, 'response': response})
        
    return render_template('ai/chatbot.html')
