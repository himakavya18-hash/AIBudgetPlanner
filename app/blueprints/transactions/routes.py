from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.models import db, Transaction, Budget, RecurringExpense
from datetime import datetime, date
from sqlalchemy import func
from . import transactions_bp

def process_recurring_expenses(user_id):
    today = date.today()
    active_recurring = RecurringExpense.query.filter_by(user_id=user_id, is_active=True).all()
    for rec in active_recurring:
        last_month = rec.last_processed.strftime('%Y-%m') if rec.last_processed else None
        current_month = today.strftime('%Y-%m')
        
        # If not processed this month, and we have reached or passed the due day
        if (last_month != current_month) and (today.day >= rec.due_day):
            due_date = date(today.year, today.month, rec.due_day)
            t = Transaction(
                user_id=user_id,
                type='expense',
                amount=rec.amount,
                category=rec.category,
                description=f"Recurring: {rec.name}",
                date=due_date,
                is_recurring=True,
                recurring_expense_id=rec.id
            )
            rec.last_processed = today
            db.session.add(t)
    db.session.commit()

def check_budget_alert(user_id, category, amount_added, trans_date=None):
    if not trans_date:
        trans_date = date.today()
    month_str = trans_date.strftime('%Y-%m')
    
    # Check if budget exists for this category and month
    budget = Budget.query.filter_by(user_id=user_id, category=category, month=month_str).first()
    if not budget:
        return None
        
    # Calculate sum of expenses already recorded in this month
    already_spent = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.category == category,
        func.strftime('%Y-%m', Transaction.date) == month_str
    ).scalar() or 0.0
    
    total_spent_with_new = already_spent + amount_added
    if total_spent_with_new > budget.amount_limit:
        over_by = total_spent_with_new - budget.amount_limit
        # If it was already exceeded, we can still alert or only alert on transition
        return {
            'category': category,
            'limit': budget.amount_limit,
            'spent': total_spent_with_new,
            'over_by': over_by
        }
    return None

@transactions_bp.route('/')
@login_required
def index():
    # Process recurring expenses
    process_recurring_expenses(current_user.id)
    
    # Get filter and search parameters
    trans_type = request.args.get('type', '')
    category = request.args.get('category', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    search_query = request.args.get('search', '')
    
    # Base query
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    if trans_type:
        query = query.filter(Transaction.type == trans_type)
    if category:
        query = query.filter(Transaction.category == category)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            pass
    if search_query:
        query = query.filter(Transaction.description.ilike(f'%{search_query}%'))
        
    # Execute query, order by newest
    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    
    # Categories for filters
    categories = current_app.config['EXPENSE_CATEGORIES'] + current_app.config['INCOME_SOURCES']
    
    return render_template(
        'transactions/list.html',
        transactions=transactions,
        categories=categories,
        selected_type=trans_type,
        selected_category=category,
        start_date=start_date_str,
        end_date=end_date_str,
        search=search_query
    )

@transactions_bp.route('/add-income', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        description = request.form.get('description', '')
        date_str = request.form.get('date')
        
        if not amount or not category:
            flash('Amount and Category are required.', 'danger')
            return redirect(url_for('transactions.add_income'))
            
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash('Amount must be positive.', 'danger')
                return redirect(url_for('transactions.add_income'))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('transactions.add_income'))
            
        trans_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        
        t = Transaction(
            user_id=current_user.id,
            type='income',
            amount=amount_val,
            category=category,
            description=description,
            date=trans_date
        )
        db.session.add(t)
        db.session.commit()
        
        flash('Income added successfully!', 'success')
        return redirect(url_for('transactions.index'))
        
    sources = current_app.config['INCOME_SOURCES']
    return render_template('transactions/add_income.html', sources=sources, today=date.today().strftime('%Y-%m-%d'))

@transactions_bp.route('/add-expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        description = request.form.get('description', '')
        date_str = request.form.get('date')
        
        if not amount or not category:
            flash('Amount and Category are required.', 'danger')
            return redirect(url_for('transactions.add_expense'))
            
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash('Amount must be positive.', 'danger')
                return redirect(url_for('transactions.add_expense'))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('transactions.add_expense'))
            
        trans_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        
        # Check budget alert
        alert = check_budget_alert(current_user.id, category, amount_val, trans_date)
        if alert:
            flash(f"Alert: You exceeded your {alert['category']} budget by ₹{alert['over_by']:,.2f}! "
                  f"(Limit: ₹{alert['limit']:,.2f}, Spent: ₹{alert['spent']:,.2f})", 'warning')
        
        t = Transaction(
            user_id=current_user.id,
            type='expense',
            amount=amount_val,
            category=category,
            description=description,
            date=trans_date
        )
        db.session.add(t)
        db.session.commit()
        
        if not alert:
            flash('Expense added successfully!', 'success')
            
        return redirect(url_for('transactions.index'))
        
    categories = current_app.config['EXPENSE_CATEGORIES']
    return render_template('transactions/add_expense.html', categories=categories, today=date.today().strftime('%Y-%m-%d'))

@transactions_bp.route('/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit(transaction_id):
    t = Transaction.query.get_or_404(transaction_id)
    if t.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('transactions.index'))
        
    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        description = request.form.get('description', '')
        date_str = request.form.get('date')
        
        if not amount or not category:
            flash('Amount and Category are required.', 'danger')
            return redirect(url_for('transactions.edit', transaction_id=t.id))
            
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash('Amount must be positive.', 'danger')
                return redirect(url_for('transactions.edit', transaction_id=t.id))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('transactions.edit', transaction_id=t.id))
            
        trans_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        
        # Check budget alert if type is expense and category or amount changed
        if t.type == 'expense':
            # Temporary deduct old amount, calculate new limit check
            alert = check_budget_alert(current_user.id, category, amount_val - (t.amount if t.category == category else 0.0), trans_date)
            if alert:
                flash(f"Alert: You exceeded your {alert['category']} budget by ₹{alert['over_by']:,.2f}!", 'warning')
        
        t.amount = amount_val
        t.category = category
        t.description = description
        t.date = trans_date
        
        db.session.commit()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions.index'))
        
    categories = current_app.config['INCOME_SOURCES'] if t.type == 'income' else current_app.config['EXPENSE_CATEGORIES']
    return render_template('transactions/edit.html', transaction=t, categories=categories)

@transactions_bp.route('/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete(transaction_id):
    t = Transaction.query.get_or_404(transaction_id)
    if t.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('transactions.index'))
        
    db.session.delete(t)
    db.session.commit()
    flash('Transaction deleted successfully.', 'success')
    return redirect(url_for('transactions.index'))

@transactions_bp.route('/recurring')
@login_required
def recurring_list():
    recurrings = RecurringExpense.query.filter_by(user_id=current_user.id).all()
    categories = current_app.config['EXPENSE_CATEGORIES']
    return render_template('transactions/recurring.html', recurrings=recurrings, categories=categories)

@transactions_bp.route('/recurring/add', methods=['POST'])
@login_required
def add_recurring():
    name = request.form.get('name')
    amount = request.form.get('amount')
    category = request.form.get('category')
    due_day = request.form.get('due_day')
    
    if not name or not amount or not category or not due_day:
        flash('All fields are required.', 'danger')
        return redirect(url_for('transactions.recurring_list'))
        
    try:
        amount_val = float(amount)
        due_day_val = int(due_day)
        if amount_val <= 0 or due_day_val < 1 or due_day_val > 31:
            flash('Invalid amount or due day.', 'danger')
            return redirect(url_for('transactions.recurring_list'))
    except ValueError:
        flash('Invalid numeric inputs.', 'danger')
        return redirect(url_for('transactions.recurring_list'))
        
    rec = RecurringExpense(
        user_id=current_user.id,
        name=name,
        amount=amount_val,
        category=category,
        due_day=due_day_val
    )
    db.session.add(rec)
    db.session.commit()
    
    # Process it immediately in case today is past the due date and it's active
    process_recurring_expenses(current_user.id)
    
    flash('Recurring expense added successfully!', 'success')
    return redirect(url_for('transactions.recurring_list'))

@transactions_bp.route('/recurring/delete/<int:recurring_id>', methods=['POST'])
@login_required
def delete_recurring(recurring_id):
    rec = RecurringExpense.query.get_or_404(recurring_id)
    if rec.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('transactions.recurring_list'))
        
    db.session.delete(rec)
    db.session.commit()
    flash('Recurring expense deleted.', 'success')
    return redirect(url_for('transactions.recurring_list'))

@transactions_bp.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    current_month_str = date.today().strftime('%Y-%m')
    
    if request.method == 'POST':
        category = request.form.get('category')
        amount_limit = request.form.get('amount_limit')
        month_str = request.form.get('month', current_month_str)
        
        if not category or not amount_limit:
            flash('Category and limit are required.', 'danger')
            return redirect(url_for('transactions.budgets'))
            
        try:
            limit_val = float(amount_limit)
            if limit_val <= 0:
                flash('Limit must be positive.', 'danger')
                return redirect(url_for('transactions.budgets'))
        except ValueError:
            flash('Invalid limit.', 'danger')
            return redirect(url_for('transactions.budgets'))
            
        # Update if exists, else create
        budget = Budget.query.filter_by(user_id=current_user.id, category=category, month=month_str).first()
        if budget:
            budget.amount_limit = limit_val
        else:
            budget = Budget(
                user_id=current_user.id,
                category=category,
                amount_limit=limit_val,
                month=month_str
            )
            db.session.add(budget)
            
        db.session.commit()
        flash(f'Budget for {category} updated!', 'success')
        return redirect(url_for('transactions.budgets'))
        
    # Get current budgets
    budgets = Budget.query.filter_by(user_id=current_user.id, month=current_month_str).all()
    categories = current_app.config['EXPENSE_CATEGORIES']
    
    return render_template('transactions/budgets.html', budgets=budgets, categories=categories, current_month=current_month_str)
