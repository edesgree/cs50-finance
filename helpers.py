import os
import requests
import urllib.parse
from cs50 import SQL

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

def calculTransaction(symbol, share_nb):
    """Calculate price for x shares of y symbol"""
    # get the stock detail for that symbol via the lookup function
    share_detail = lookup(symbol)

    # calculate the total price of the purchase
    transaction_price = share_detail['price'] * float(share_nb)
    return transaction_price


def getCashRemaining():
    db = SQL("sqlite:///finance.db")
    # query the db for the amount of cash this user has (return a list[])
    cash_data = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    # get cash value as a number from the list
    cash = cash_data[0].get("cash")
    return cash

def getTrend(buying_price,today_price):
    result = today_price - buying_price
    if result < 0:
        return 'down'
    return 'up'