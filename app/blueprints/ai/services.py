import re
import json
import requests
from flask import current_app

def call_mistral(system_prompt, user_prompt):
    api_key = current_app.config.get('MISTRAL_API_KEY')
    if not api_key:
        return None
        
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # We use open-mistral-7b as a general lightweight model
    payload = {
        "model": current_app.config.get('MISTRAL_MODEL', 'mistral-small-latest'),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            current_app.logger.warning(f"Mistral API returned status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        current_app.logger.error(f"Error calling Mistral API: {str(e)}")
        return None

# ==========================================
# Requirement 5: AI Expense Categorization
# ==========================================
def ai_categorize_expense(text, categories):
    system_prompt = (
        f"You are a financial helper. Categorize the given text into EXACTLY ONE of these categories: "
        f"{', '.join(categories)}. Respond with only the category name."
    )
    
    ai_response = call_mistral(system_prompt, text)
    if ai_response and ai_response in categories:
        return ai_response
        
    # Heuristics Fallback (Rule-Based matching)
    text_lower = text.lower()
    
    food_keywords = ['swiggy', 'zomato', 'food', 'restaurant', 'mcdonald', 'starbucks', 'grocery', 'groceries', 'dinner', 'lunch', 'breakfast', 'cafe', 'pizza']
    rent_keywords = ['rent', 'landlord', 'maintenance']
    utility_keywords = ['electricity', 'water', 'gas', 'bill', 'wifi', 'internet', 'phone', 'mobile recharge']
    shopping_keywords = ['amazon', 'flipkart', 'myntra', 'shopping', 'clothes', 'shoes', 'dress', 'mall', 'electronics', 'gift']
    transport_keywords = ['uber', 'ola', 'taxi', 'fuel', 'petrol', 'diesel', 'metro', 'bus', 'train', 'flight', 'cab']
    ent_keywords = ['netflix', 'spotify', 'movie', 'cinema', 'theatre', 'game', 'club', 'bar', 'concert', 'subscription']
    health_keywords = ['medicine', 'doctor', 'hospital', 'pharmacy', 'clinic', 'health', 'dental']
    edu_keywords = ['course', 'book', 'fees', 'college', 'school', 'tutor', 'stationary']
    travel_keywords = ['hotel', 'stay', 'trip', 'vacation', 'resort', 'booking']
    
    if any(k in text_lower for k in food_keywords):
        return 'Food'
    if any(k in text_lower for k in rent_keywords):
        return 'Rent'
    if any(k in text_lower for k in utility_keywords):
        return 'Utilities'
    if any(k in text_lower for k in shopping_keywords):
        return 'Shopping'
    if any(k in text_lower for k in transport_keywords):
        return 'Transportation'
    if any(k in text_lower for k in ent_keywords):
        return 'Entertainment'
    if any(k in text_lower for k in health_keywords):
        return 'Healthcare'
    if any(k in text_lower for k in edu_keywords):
        return 'Education'
    if any(k in text_lower for k in travel_keywords):
        return 'Travel'
        
    return 'Others'

# ==========================================
# Requirement 9: Voice Expense parsing
# ==========================================
def ai_parse_voice(text, categories):
    system_prompt = (
        f"Analyze the transcribed voice expense. Extract the amount (as integer or float), the category, and a description. "
        f"The category must be EXACTLY ONE of: {', '.join(categories)}. "
        f"Return ONLY a JSON object with keys: 'amount', 'category', 'description'. "
        f"Do not include markdown or backticks."
    )
    
    user_prompt = f"Voice text: \"{text}\""
    
    ai_response = call_mistral(system_prompt, user_prompt)
    if ai_response:
        try:
            # Strip potential markdown formatting if returned
            clean_res = ai_response.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_res)
            if 'amount' in data and 'category' in data:
                if data['category'] in categories:
                    return data
        except Exception:
            pass
            
    # Fallback parser
    amount = 0.0
    category = 'Others'
    description = text
    
    # Try to extract numbers
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    if numbers:
        amount = float(numbers[0])
        
    # Guess category using categorization function
    category = ai_categorize_expense(text, categories)
    
    # Guess description
    clean_desc = re.sub(r'\d+(?:\.\d+)?', '', text)
    clean_desc = clean_desc.replace('rupees', '').replace('rupee', '').replace('rs', '').replace('spent', '').replace('on', '').strip()
    description = clean_desc.capitalize() if clean_desc else "Voice Expense"
    
    return {
        'amount': amount,
        'category': category,
        'description': description
    }

# ==========================================
# Requirement 6: AI Budget Suggestions
# ==========================================
def ai_budget_suggestions(income, categories):
    system_prompt = (
        f"Suggest a monthly budget division based on the income ₹{income}. "
        f"For these categories: {', '.join(categories)}. "
        f"Provide suggestions in JSON format with category keys and suggested numeric amounts. "
        f"Do not include markdown or backticks."
    )
    
    ai_response = call_mistral(system_prompt, f"Income: {income}")
    if ai_response:
        try:
            clean_res = ai_response.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_res)
            return data
        except Exception:
            pass
            
    # Fallback based on 50/30/20 budget allocation
    # 50% Essentials: Rent (25%), Food (15%), Healthcare/Utilities (10%)
    # 30% Wants: Shopping (15%), Entertainment (10%), Travel (5%)
    # 20% Savings: Allocated directly
    suggestions = {
        'Rent': round(income * 0.20),
        'Utilities': round(income * 0.05),
        'Food': round(income * 0.15),
        'Shopping': round(income * 0.15),
        'Transportation': round(income * 0.05),
        'Entertainment': round(income * 0.10),
        'Healthcare': round(income * 0.05),
        'Education': round(income * 0.05),
        'Travel': round(income * 0.05),
        'Others': round(income * 0.05),
        'Savings': round(income * 0.20)
    }
    
    # Filter to match categories
    final_sug = {}
    for cat in categories:
        final_sug[cat] = suggestions.get(cat, round(income * 0.05))
    final_sug['Savings / Investment'] = suggestions.get('Savings', round(income * 0.20))
    
    return final_sug

# ==========================================
# Requirement 7: AI Spending Analysis & Insights
# ==========================================
def ai_spending_analysis(income, expense_by_cat, last_month_expense, goals_info):
    system_prompt = (
        "You are a financial advisor. Analyze the monthly expenses compared to income and savings goals. "
        "Write a brief, friendly paragraph (2-3 sentences) detailing saving advice and highlights."
    )
    
    user_prompt = (
        f"Monthly Income: ₹{income}. Expenses by category: {json.dumps(expense_by_cat)}. "
        f"Last month's total expense: ₹{last_month_expense}. Savings Goals status: {goals_info}."
    )
    
    ai_response = call_mistral(system_prompt, user_prompt)
    if ai_response:
        return ai_response
        
    # Heuristics Fallback
    total_expense = sum(expense_by_cat.values())
    if income > 0:
        savings_rate = (income - total_expense) / income
    else:
        savings_rate = -1.0
        
    high_category = max(expense_by_cat, key=expense_by_cat.get) if expense_by_cat else 'None'
    high_amount = expense_by_cat.get(high_category, 0)
    
    analysis = ""
    if savings_rate < 0.2:
        analysis = (
            f"You spent a total of ₹{total_expense:,.2f} this month. "
            f"Your savings rate is lower than the recommended 20%. "
            f"Your highest spending category is {high_category} (₹{high_amount:,.2f}). "
            f"Reducing expense in {high_category} by ₹2,000 could help you secure your emergency funds and hit your saving goals."
        )
    else:
        analysis = (
            f"Great job! You saved ₹{income - total_expense:,.2f} ({(savings_rate*100):.1f}% of income) this month. "
            f"Your highest spending was in {high_category} (₹{high_amount:,.2f}). "
            f"Keep up this habit to fund your savings goal faster!"
        )
        
    return analysis

# ==========================================
# Requirement 17: AI Saving Tips
# ==========================================
def ai_saving_tips(income, expense_by_cat):
    system_prompt = (
        "Provide 3 short, highly actionable bullet-pointed saving tips tailored to the highest spending category."
    )
    
    user_prompt = f"Monthly Income: ₹{income}. Spending: {json.dumps(expense_by_cat)}"
    
    ai_response = call_mistral(system_prompt, user_prompt)
    if ai_response:
        # Convert response into a list of tips
        tips = [t.strip().lstrip('-*').strip() for t in ai_response.split('\n') if t.strip()]
        return tips[:3]
        
    # Fallback tips
    high_category = max(expense_by_cat, key=expense_by_cat.get) if expense_by_cat else 'Others'
    
    category_tips = {
        'Food': [
            "Order food less frequently: meal prepping lunch on Sundays could save up to ₹2,500/month.",
            "Make coffee at home instead of buying premium takeaway drinks daily.",
            "Buy bulk items for non-perishable pantry staples."
        ],
        'Rent': [
            "Review your rent agreement before renewal and negotiate a fair increase.",
            "Keep a dedicated rent fund so the monthly payment is always ready.",
            "Consider shared housing costs if it suits your lifestyle."
        ],
        'Utilities': [
            "Turn off lights and unplug heavy appliances when not in use to reduce electric bills.",
            "Compare Wi-Fi plans or call your service provider to negotiate a loyalty discount.",
            "Ensure air conditioners are set to 24°C to optimize energy usage."
        ],
        'Shopping': [
            "Wait 48 hours before purchasing anything in your shopping cart to check if it's an impulse buy.",
            "Unsubscribe from promotional emails and retail newsletters to reduce temptation.",
            "Look for secondhand alternatives for furniture, books, or electronics."
        ],
        'Transportation': [
            "Carpool or use public transit like trains and metros instead of private taxis.",
            "Maintain proper tire pressure and drive at steady speeds to increase fuel economy.",
            "Walk or cycle for short distances under 2 kilometers."
        ],
        'Entertainment': [
            "Review your streaming subscriptions and cancel any you haven't watched in the last month.",
            "Look for free local events, museums, or community parks for weekend activities.",
            "Host potluck dinners at home instead of dining at expensive lounges/bars."
        ]
    }
    
    return category_tips.get(high_category, [
        "Create an emergency savings account with automatic transfers on payday.",
        "Track all transactions immediately to create mindfulness around small habits.",
        "Categorize and check budget limits before making discretionary purchases."
    ])

# ==========================================
# Requirement 11: Expense Prediction (AI)
# ==========================================
def ai_predict_expenses(transactions_history, categories):
    system_prompt = (
        "Based on the transaction history, predict next month's spending per category. "
        "Return a JSON mapping of categories to predicted numeric amounts. "
        "Do not include markdown or backticks."
    )
    
    user_prompt = f"History: {json.dumps(transactions_history)}"
    
    ai_response = call_mistral(system_prompt, user_prompt)
    if ai_response:
        try:
            clean_res = ai_response.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_res)
            return data
        except Exception:
            pass
            
    # Fallback: simple prediction based on average category expenses
    # Calculate sum and counts per category
    category_totals = {}
    for t in transactions_history:
        if t['type'] == 'expense':
            category_totals[t['category']] = category_totals.get(t['category'], 0.0) + t['amount']
            
    predictions = {}
    for cat in categories:
        # Predict average expense + slight variance
        base = category_totals.get(cat, 0.0)
        # Assume history covers 1 month for simplicity, or scale as needed.
        # We can add a slight trend factor (e.g. 5% inflation or random fluctuation)
        predictions[cat] = round(base * 1.03) if base > 0 else 0
        
    return predictions

# ==========================================
# Requirement 8: AI Financial Chatbot
# ==========================================
def ai_chatbot_response(user_query, financial_summary):
    system_prompt = (
        "You are an friendly financial AI assistant. The user will ask you a question. "
        "Using the provided financial summary data of the user, answer their question accurately. "
        "Keep your response concise and structured."
    )
    
    user_prompt = f"User Query: \"{user_query}\"\nUser Data Summary: {json.dumps(financial_summary)}"
    
    ai_response = call_mistral(system_prompt, user_prompt)
    if ai_response:
        return ai_response
        
    # Heuristics Fallback Chatbot
    q = user_query.lower()
    
    # 1. Highest spending
    if 'most money' in q or 'highest spend' in q or 'where did i spend' in q or 'most expense' in q:
        expenses = financial_summary.get('expenses_by_category', {})
        if expenses:
            high_cat = max(expenses, key=expenses.get)
            high_amt = expenses[high_cat]
            return f"You spent the most money in the **{high_cat}** category with **₹{high_amt:,.2f}**."
        return "You have not recorded any expenses yet."
        
    # 2. Total savings
    if 'saving' in q or 'how much did i save' in q:
        sav = financial_summary.get('monthly_savings', 0.0)
        rate = financial_summary.get('savings_rate', 0.0)
        if sav > 0:
            return f"Your savings for this month is **₹{sav:,.2f}** which is a savings rate of **{rate:.1f}%** of your income."
        return f"You don't have any savings this month. Your net savings is **₹{sav:,.2f}**."
        
    # 3. Balance
    if 'balance' in q or 'how much money do i have' in q:
        bal = financial_summary.get('total_balance', 0.0)
        return f"Your current net balance is **₹{bal:,.2f}**."
        
    # 4. Income
    if 'income' in q or 'salary' in q or 'earn' in q:
        inc = financial_summary.get('monthly_income', 0.0)
        return f"Your recorded income for this month is **₹{inc:,.2f}**."
        
    # 5. Tips
    if 'tip' in q or 'advice' in q or 'help' in q or 'suggest' in q:
        tips = financial_summary.get('saving_tips', [])
        tips_str = "\n".join([f"- {t}" for t in tips])
        return f"Here are some saving suggestions tailored for you:\n{tips_str}"
        
    return (
        "I can help you analyze your budget! Try asking:\n"
        "- *Where did I spend the most money this month?*\n"
        "- *How much did I save?*\n"
        "- *What is my net balance?*\n"
        "- *Give me some saving tips.*"
    )
