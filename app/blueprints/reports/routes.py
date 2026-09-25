import io
import csv
from datetime import datetime, date, timedelta
from flask import render_template, Response, make_response, current_app, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import db, Transaction, Budget
from . import reports_bp

# Import reportlab components safely
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def get_last_6_months_data(user_id):
    today = date.today()
    monthly_data = []
    
    # We will build list of last 6 months including current
    for i in range(5, -1, -1):
        # Navigate back i months
        temp_date = today
        for _ in range(i):
            temp_date = temp_date.replace(day=1) - timedelta(days=1)
            
        month_str = temp_date.strftime('%Y-%m')
        label = temp_date.strftime('%b %Y')
        
        inc = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'income',
            func.strftime('%Y-%m', Transaction.date) == month_str
        ).scalar() or 0.0
        
        exp = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            func.strftime('%Y-%m', Transaction.date) == month_str
        ).scalar() or 0.0
        
        monthly_data.append({
            'month': month_str,
            'label': label,
            'income': inc,
            'expense': exp,
            'savings': inc - exp
        })
        
    return monthly_data

@reports_bp.route('/')
@login_required
def index():
    current_month_str = date.today().strftime('%Y-%m')
    
    # Monthly summaries
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
    
    # Top spending categories
    top_categories = db.session.query(
        Transaction.category, func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).limit(3).all()
    
    return render_template(
        'reports/report.html',
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        savings=savings,
        top_categories=top_categories,
        current_month=datetime.utcnow().strftime('%B %Y')
    )

# --- CHART API ENDPOINTS ---

@reports_bp.route('/data/expenses-by-category')
@login_required
def expenses_by_category():
    current_month_str = date.today().strftime('%Y-%m')
    results = db.session.query(
        Transaction.category, func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).group_by(Transaction.category).all()
    
    labels = [r[0] for r in results]
    values = [r[1] for r in results]
    
    return jsonify({
        'labels': labels,
        'values': values
    })

@reports_bp.route('/data/monthly-analytics')
@login_required
def monthly_analytics():
    data = get_last_6_months_data(current_user.id)
    
    labels = [d['label'] for d in data]
    income_vals = [d['income'] for d in data]
    expense_vals = [d['expense'] for d in data]
    savings_vals = [d['savings'] for d in data]
    
    return jsonify({
        'labels': labels,
        'income': income_vals,
        'expense': expense_vals,
        'savings': savings_vals
    })

# --- EXPORT ENDPOINTS ---

@reports_bp.route('/export/csv')
@login_required
def export_csv():
    # Fetch all transactions
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Date', 'Type', 'Category', 'Description', 'Amount (INR)', 'Is Recurring'])
    
    for t in transactions:
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.type.capitalize(), t.category, t.description or '', t.amount, 'Yes' if t.is_recurring else 'No'])
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=financial_report.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@reports_bp.route('/export/pdf')
@login_required
def export_pdf():
    current_month_str = date.today().strftime('%Y-%m')
    
    # Financial statistics
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
    
    # Fetch recent transactions
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).limit(15).all()
    
    if not REPORTLAB_AVAILABLE:
        # Fallback to HTML print template or raw text in case reportlab is missing
        return f"""
        <h1>AI Budget Planner - Monthly Report ({datetime.utcnow().strftime('%B %Y')})</h1>
        <p>User: {current_user.username}</p>
        <p>Total Income: INR {monthly_income}</p>
        <p>Total Expenses: INR {monthly_expense}</p>
        <p>Net Savings: INR {savings}</p>
        <hr>
        <h3>Recent Transactions</h3>
        <ul>
            {"".join([f"<li>{t.date} | {t.type.upper()} | {t.category} | {t.description or ''} | INR {t.amount}</li>" for t in transactions])}
        </ul>
        <script>window.print();</script>
        """
        
    # Build proper PDF using ReportLab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        textColor=colors.HexColor('#2c3e50'),
        fontSize=24,
        leading=28,
        spaceAfter=15
    )
    section_style = ParagraphStyle(
        'DocSection',
        parent=styles['Heading2'],
        textColor=colors.HexColor('#34495e'),
        fontSize=16,
        leading=20,
        spaceBefore=15,
        spaceAfter=10
    )
    body_style = styles['Normal']
    
    # Title
    story.append(Paragraph(f"AI Budget Planner - Financial Report", title_style))
    story.append(Paragraph(f"Generated for: <b>{current_user.username}</b> ({current_user.email})", body_style))
    story.append(Paragraph(f"Reporting Month: <b>{datetime.utcnow().strftime('%B %Y')}</b>", body_style))
    story.append(Paragraph(f"Date Generated: {date.today().strftime('%Y-%m-%d')}", body_style))
    story.append(Spacer(1, 15))
    
    # Summary Grid Table
    data = [
        ['Metric', 'Amount (INR)'],
        ['Total Income', f"INR {monthly_income:,.2f}"],
        ['Total Expenses', f"INR {monthly_expense:,.2f}"],
        ['Monthly Net Savings', f"INR {savings:,.2f}"]
    ]
    t = Table(data, colWidths=[200, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
    ]))
    story.append(Paragraph("Monthly Summary Statistics", section_style))
    story.append(t)
    story.append(Spacer(1, 20))
    
    # Transactions Table
    trans_data = [['Date', 'Type', 'Category', 'Description', 'Amount (INR)']]
    for tr in transactions:
        trans_data.append([
            tr.date.strftime('%Y-%m-%d'),
            tr.type.capitalize(),
            tr.category,
            tr.description or '',
            f"INR {tr.amount:,.2f}"
        ])
        
    t_trans = Table(trans_data, colWidths=[80, 60, 100, 150, 100])
    t_trans.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e9ecef')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(Paragraph("Recent Transactions Record (Up to 15)", section_style))
    story.append(t_trans)
    
    # Build Document
    doc.build(story)
    
    response = make_response(buffer.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=financial_report_{current_month_str}.pdf"
    response.headers["Content-type"] = "application/pdf"
    return response
