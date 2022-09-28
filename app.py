import os
# import 
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, calculTransaction, getCashRemaining, getTrend


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # display user id
    user_id = session["user_id"]

    # get merged list of buy and sell orders for user
    shares_list = db.execute(
        "SELECT symbol, SUM(shares) AS shares, price FROM orders WHERE user_id = ? GROUP BY symbol HAVING  SUM(shares) > 0 ORDER BY symbol", user_id)

    # get cash remaining
    cash = getCashRemaining()

    # loop through the result from query
    shares_total = 0
    for share in shares_list:
        # access the lookup for this share and get today's price
        share_detail = lookup(share['symbol'])
        share['today_price'] = share_detail['price']
        # calculate price of total shares owned for this company
        total_price = share['shares'] * share['today_price']
        # add entry to dictionary
        share['total_price'] = total_price
        # calculate total of all shares all company combined (increment each loop)
        shares_total = shares_total + (share['shares'] * share['today_price'])

        # calculate trend of price
        share['trend'] = getTrend(share['price'], share['today_price'])
        # add company name in the list
        share['company_name'] = share_detail['name']

    # calcul total assets (shares + cash)
    total_assets = shares_total + cash
    cash_remaining = cash

    return render_template("index.html", user=user_id, shares_list=shares_list, cash_remaining=cash_remaining, total_assets=total_assets)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # get user data
        symbol = request.form.get("symbol")
        sharesnb = request.form.get("shares")
        # Ensure text was submitted in the search field
        if not symbol:
            return apology("must provide stock’s name", 403)
       # Ensure number of shares to buy was chosen and is digit
        if not sharesnb:
            return apology("must provide a quantity to buy", 403)
        if not sharesnb.isdigit():
            return apology("You cannot purchase partial shares.", 400)

        # get the stock detail for that symbol via the lookup function
        share_detail = lookup(symbol)
        if share_detail is None:
            return apology("Symbol not found", 400)

        # calculate the total price of the purchase
        purchase_price = calculTransaction(symbol, sharesnb)
        if purchase_price < 0:
            return apology("Invalid transaction", 403)

        # get cash remaining
        cash = getCashRemaining()

        # check if user has enough cash to buy
        cash_remaining = round((cash - purchase_price), 2)
        if (cash_remaining < 0):
            return apology("You don't have enough money to make this transaction!", 403)

        # total assets
        total_assets = (cash_remaining + purchase_price)
        flash('Your purchase is complete !')

        # record purchase into db

        # insert the stock bought in the stocks table
        # check if stock is alreay recorded in the db
        check_stock = db.execute("SELECT * FROM stocks WHERE symbol=?", share_detail['symbol'])
        # if the query return nothing for that symbol, we insert it as a new stock
        if not check_stock:
            db.execute("INSERT INTO stocks (company_name,price,symbol) VALUES(?,?,?)",
                       share_detail['name'], share_detail['price'], share_detail['symbol'])

        # insert the transaction in the buy table
        db.execute("INSERT INTO orders (user_id,symbol,shares,price,date,type) VALUES(?,?,?,?,CURRENT_TIMESTAMP,?) ",
                   session["user_id"], share_detail['symbol'], sharesnb, share_detail['price'], "buy")

        # update the buyer's wallet
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_remaining, session["user_id"])
        return render_template("bought.html", total_assets=usd(total_assets), cash_remaining=usd(cash_remaining), sharesnb=sharesnb, purchase_price=usd(purchase_price), share_detail=share_detail)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    # get list of buy and sell orders for user
    history_list = db.execute("SELECT symbol, shares, price, type, date FROM orders WHERE user_id = ? ORDER BY date", user_id)

    return render_template("history.html", history_list=history_list)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        print(session["user_id"])
        print(session["username"])
        print(rows[0]["username"])

        # flash a message to confirm
        flash('You were successfully logged in')
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # get user data from form
    share = []
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # Ensure text was submitted in the search field
        if not symbol:
            return apology("must provide share’s name", 400)
        # get the share detail for that symbol via the lookup function
        share = lookup(symbol)
        if share is None:
            return apology("Symbol not found", 400)

        return render_template("quote.html", share=share)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # get data from form and register user
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username was submitted and doesnt exist already
        if not username:
            return apology("must provide username", 400)
        # Ensure password was submitted
        if not password:
            return apology("must provide password", 400)

        # Ensure username doesnt exist already (if row > 0, then username already exist)
        if len(rows) != 0:
            return apology("username alreay used!", 400)

        # Ensure password is same as confirmation
        if password != confirmation:
            return apology("password is not same as confirmation", 400)
        else:
            # create hash of the password
            hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
            # insert username and hashed password into the db
            db.execute("INSERT INTO users (username,hash) VALUES(?,?) ", username, hash)

    else:
        # redirect to register form (GET method)
        return render_template("register.html")

    # once registered, login the user
    # Query database for username
    rows = db.execute("SELECT * FROM users WHERE username = ?", username)

    # Ensure username exists and password is correct
    if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
        return apology("invalid username and/or password", 403)

    # Remember which user has logged in
    session["user_id"] = rows[0]["id"]

    # confirm registration
    flash('Thank you '+username+'. You are now registered')

    # Redirect user to home page
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    shares_list = db.execute("SELECT symbol,shares FROM orders WHERE user_id = ? GROUP BY symbol", session["user_id"])

    if request.method == "POST":
        # get data from form
        share_nb_to_sell = request.form.get("shares")
        symbol_name_to_sell = request.form.get("symbol")
        # Ensure text was submitted in the search field
        if not symbol_name_to_sell:
            return apology("must provide stock’s name", 403)
       # Ensure number of shares to buy was chosen and is digit
        if not share_nb_to_sell:
            return apology("must provide a quantity to buy", 400)
        if not share_nb_to_sell.isdigit():
            return apology("You cannot purchase partial shares.", 400)

        # check if user has enough shares to sell
        for share in shares_list:

            if symbol_name_to_sell == share['symbol']:
                if int(share_nb_to_sell) > share['shares']:
                    return apology("You don't have enough "+share['symbol']+" to sell!", 400)

                else:
                    # record the sell
                    # calculate the total price of the purchase
                    purchase_price = calculTransaction(share['symbol'], share_nb_to_sell)

                    # access the lookup price for this share
                    share_detail = lookup(share['symbol'])
                    # get cash remaining
                    cash = getCashRemaining()
                    # update the buyer's wallet
                    cash_remaining = round((cash + purchase_price), 2)

                    # update database (update wallet + insert new order type sell)
                    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_remaining, session["user_id"])
                    db.execute("INSERT INTO orders (user_id,symbol,shares,price,date,type) VALUES(?,?,?,?,CURRENT_TIMESTAMP,?)",
                               session["user_id"], share['symbol'], -int(share_nb_to_sell), share_detail['price'], "sell")

                    # send user to homagepage with confirmation flash message
                    flash("You sold " + share_nb_to_sell + " shares of " +
                          share['symbol'] + " for a total of " + str(purchase_price) + "$")
        return redirect("/")
    # Redirect user to home page
    else:
        # get list of shares owned by user
        return render_template("sell.html", shares_list=shares_list)


@app.route('/get_number_shares', methods=['GET', 'POST'])
def get_number_shares():
    if request.method == "POST":
        # request symbol selection from form
        symbol_to_lookup = request.form['query']
        # look db for number of shares owned for that symbol
        dbquery = db.execute(
            "SELECT SUM(shares) as SHARENB FROM orders WHERE user_id = ? AND symbol = ?  GROUP BY symbol HAVING  SUM(shares) > 0 ", session["user_id"], symbol_to_lookup)

        # save first entry of dict as variable shares_number
        shares_number = None
        for share in dbquery:
            shares_number = share['SHARENB']

        # return jsonify data to client side
        return jsonify(shares_number)
    else:
        # Redirect user to sell page
        return redirect("/sell")