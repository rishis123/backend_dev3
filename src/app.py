from flask import Flask, request

import json
import db

DB = db.DatabaseDriver()

app = Flask(__name__)

def success_response(body, code=200):
    return json.dumps(body), code

def failure_response(message, code=404):
    return json.dumps({'error': message}), code

def create_tables():
    DB.create_all()

@app.route("/")
def hello_world():
    return "Hello world!"


# your routes here

"""
Returns every user (i.e., every item in users table) and success code 200.
"""
@app.route("/api/users/")
def get_all_users():
    return success_response(DB.query_all_users())

"""
Creates a user with name, username, and balance specified in body (default of 0). If name and/or username are empty, then returns 400 status code, 
else a 201 success code along with new user's full information
"""
@app.route("/api/users/", methods = ["POST"])
def create_user():
    body = json.loads(request.data) 
    username = body["username"]
    if username is None:
        return failure_response("No username provided!", 400)
    name = body["name"]
    if name is None:
        return failure_response("No name provided!", 400)
    #if this far -- then both are provided
    balance = body["balance"]
    users_id = DB.insert_user_table(name, username, balance)
    user = DB.query_user_by_id(users_id)
    if user is None:
        return failure_response("Something went wrong while creating user!", 500)
    response_data = {
        "id": users_id,
        "name": name,
        "username": username,
        "balance": balance,
        "transactions": []  # Assuming no transactions initially
    }
    return success_response(response_data, 201) # note -- not success response function since this is 201

"""
Returns a user of specified id from url. 404 status code if user not found, else 200 status code.
"""
@app.route("/api/user/<int:user_id>/")
def get_user(user_id):
    user = DB.query_user_by_id(user_id)
    if user is None:
        return failure_response("User not found!")
    transactions = DB.query_txn_for_spec_user(user_id) #all transactions for this user
    if transactions is None:
        transactions = []
    
    response_data = {
        "id": user['id'],
        "name": user['name'],
        "username": user['username'],
        "balance": user['balance'],
        "transactions": transactions
    }
    return success_response(response_data)

"""
Deletes user of specified id from users and txn tables, 404 status code if user not found, else 200 status code
"""
@app.route("/api/user/<int:user_id>/", methods=["DELETE"])
def delete_user(user_id):
    user = DB.query_user_by_id(user_id)
    if user is None:
        return failure_response("User not found!")
    transactions = DB.query_txn_for_spec_user(user_id) #all transactions for this user
    if transactions is None:
        transactions = []

    response_data = {
        "id": user['id'],
        "name": user['name'],
        "username": user['username'],
        "balance": user['balance'],
        "transactions": transactions
    }    
    DB.remove_user(user_id)
    return success_response(response_data)

'''
Creates a transaction to send or request money
'''
@app.route("/api/transactions/", methods = ["POST"])
def send_or_request():
    body = json.loads(request.data)
    sender_id = body["sender_id"]
    if sender_id is None or DB.query_user_by_id(sender_id) is None:
        return failure_response("Sender not found!")
    receiver_id = body["receiver_id"]
    if receiver_id is None or DB.query_user_by_id(receiver_id) is None:
        return failure_response("Receiver not found!")
    amount = body["amount"]
    if amount is None:
        return failure_response("No amount!")
    message = body["message"]
    if receiver_id is None:
        return failure_response("No message!")
    accepted = body["accepted"]
    if accepted is None: #same as SQL null. Want to update txn database without changing balances
        return success_response(DB.insert_user_txn(sender_id, receiver_id, amount, message, accepted), 201)
    elif accepted is True:
        if DB.query_user_balance(sender_id) < amount:
            return failure_response("Insufficient funds", 403)
        else:
            DB.update_user(sender_id, -amount) #deducted from sender
            DB.update_user(receiver_id, amount) #added to receiver
            return success_response(DB.insert_user_txn(sender_id, receiver_id, amount, message, accepted), 201)
    else:
        return failure_response("Invalid accepted value")
        




"""
Accept or deny a payment request. Cannot change "accepted" field failure response if accepted is already true/false.
Otherwise, if true, then sends the money per the initial request. If false, then denies the request. Both ways, returns the new transaction.
"""
@app.route("/api/transactions/<int:id>/", methods = ["POST"])
def accept_deny_request(id):
    desired_transac = DB.query_txn_for_spec_transac(id)
    if desired_transac is None:
        return failure_response("Transaction not found", 404)
    
    if desired_transac[5] is not None:
        return failure_response("Cannot change 'accepted' field for accepted or denied transactions", 403)
    
    body = request.get_json()
    if 'accepted' not in body:
        return failure_response("Missing 'accepted' field in request body", 400)

    change_accepted = body['accepted']
    if change_accepted is True:
        # Check if the user has enough balance to accept the transaction
        sender_id = desired_transac[2]
        receiver_id = desired_transac[3]
        amount = desired_transac[4]
        sender_balance = DB.query_user_balance(sender_id)
        
        if sender_balance is None or sender_balance < amount:
            return failure_response("Insufficient balance to accept the transaction", 403)
        else:
            # Update the transaction status to accepted and update balances
            DB.update_transaction_status(id, change_accepted)
            DB.update_user(sender_id, -amount)  # Deduct amount from sender's balance
            DB.update_user(receiver_id, amount)  # Add amount to receiver's balance
            
            fixed_transac = DB.query_txn_for_spec_transac(id)
            transac_dict = {
                "id": fixed_transac[0],
                "timestamp": fixed_transac[1],
                "sender_id": fixed_transac[2],
                "receiver_id": fixed_transac[3],
                "amount": fixed_transac[4],
                "accepted": fixed_transac[5],
                "message": fixed_transac[6]
            }

            return success_response(transac_dict)

    elif change_accepted is False:
        # Update the transaction status to denied
        DB.update_transaction_status(id, change_accepted)
        fixed_transac = DB.query_txn_for_spec_transac(id)
        transac_dict = {
            "id": fixed_transac[0],
            "timestamp": fixed_transac[1],
            "sender_id": fixed_transac[2],
            "receiver_id": fixed_transac[3],
            "amount": fixed_transac[4],
            "accepted": fixed_transac[5],
            "message": fixed_transac[6]
        }
        return success_response(transac_dict)

    else:
        return failure_response("Invalid value for 'accepted' field", 400)
            
    
    



"""
Resets tables to empty value for graders' postman evaluation.
"""
@app.route("/api/reset/", methods=["POST"])
def reset_tables():
    DB.reset_tables()  # Call the reset_tables() method from your DatabaseDriver class
    return "Tables reset successfully", 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
