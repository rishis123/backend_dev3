import sqlite3
import json
from datetime import datetime

# From: https://goo.gl/YzypOI
def singleton(cls):
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance



class DatabaseDriver(object):
    """
    Database driver for the Task app.
    Handles with reading and writing data with the database.
    """

    """
    Initializes Database driver, makes connection to a file called users.db and loads it
    """
    def __init__(self):
        self.conn = sqlite3.connect("users.db", check_same_thread=False)
        self.create_users_table()
        self.create_transac_table()


    """
    Creates the table of users, with columns for id, name and username (which are non-optional, hence NOT NULL), and optional balance (default value of 0)
    """
    def create_users_table(self):
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    username TEXT NOT NULL,
                    balance INTEGER
                );
            """)
        except Exception as e:
            print("Error creating users table", e)


    """
    Creates the table of transactions, with columns for id and non-null sender/receiver Foreign keys
    """
    def create_transac_table(self):
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS txn (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    accepted BOOLEAN,
                    message TEXT NOT NULL,
                    FOREIGN KEY (receiver_id) REFERENCES users(id),
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                );
            """)
        except Exception as e:
            print("Error creating users table", e)
    

    """
    Reset tables, to ensure graders receive same empty database for postman.
    """
    def reset_tables(self):
        self.conn.execute("DROP TABLE IF EXISTS users;")
        self.conn.execute("DROP TABLE IF EXISTS txn;")
        self.create_users_table() #Removes existing table, and resets ID numbering by making new table
        self.create_transac_table() #Removes existing table, and resets ID numbering by making new table
        self.conn.commit()  

    """
    Returns id, name, and username (but not balance) for each user in users database
    """
    def query_all_users(self):
        cursor = self.conn.execute("SELECT id, name, username FROM users;")
        user_list = []

        for row in cursor: 
            user_list.append({"id": row[0], "name": row[1], "username": row[2]})

        return user_list
    
    """
    Inserts user with name, username, balance parameters. Default value of balance is 0 if unspecified.
    Note name and username input validation (i.e., failure response if not present) will be handled in create_user method in app.py
    """
    def insert_user_table(self, name, username, balance=0):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO users (name, username, balance) VALUES (?, ?, ?);", 
            (name, username, balance))
        self.conn.commit()
        return cursor.lastrowid

    """
    Creates a transaction for specified receiver and spender ids.
    """
    def insert_user_txn(self, sender_id, receiver_id, amount, message, accepted):
        timestamp = datetime.now().isoformat() # returning error that datetime in json doesn't work - we return as string
        cursor = self.conn.cursor()

        cursor.execute("INSERT INTO txn (timestamp, sender_id, receiver_id, amount, message, accepted) VALUES (?, ?, ?, ? , ? , ?);", 
            (timestamp, sender_id, receiver_id, amount, message, accepted))
        self.conn.commit()

        neat_transac = cursor.lastrowid #all you need is the id field in txn, everything else is supplied above
        transac_dict = {
                "id": neat_transac,
                "timestamp": timestamp,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "amount": amount,
                "accepted": accepted,
                "message": message
            }
        return transac_dict
        



    """
    Returns the ID, name, username, and balance of a specified (by ID) user from users table
    """
    def query_user_by_id(self, id):
        cursor = self.conn.execute("SELECT * FROM users WHERE ID = ?", (id,))
        user = cursor.fetchone()  # Fetch the first row matching the query, represented as a tuple here

        if user: # return tuple in dictionary form
            return {"id": user[0], "name": user[1], "username": user[2], "balance": user[3]}
        else:
            return None
    
    """
    Removes user with specified id from users and txn table
    """
    def remove_user(self, id):
        self.conn.execute("""
        DELETE FROM users
        WHERE id = ?;        
        """, (id,))

        self.conn.execute("""
        DELETE FROM txn
        WHERE sender_id = ? OR receiver_id = ?;
        """, (id,id,)) # need two ids to replace both ?s
        self.conn.commit()


    """
    Adds the amount specified to user with specified id in users table (note: call -amount in app.py to remove money, 
    and validation of amount handled there as well).
    """
    def update_user(self, id, amount):
        self.conn.execute("""
            UPDATE users 
            SET balance = balance + ?
            WHERE id = ?;
        """, (amount,id))
        self.conn.commit()

    """
    Helper method to send_money in app.py, gets the balance of sender's account
    """
    def query_user_balance(self, id): 
        cursor = self.conn.execute("SELECT balance FROM users WHERE ID = ?", (id,))

        for row in cursor:
            return row[0] #returns balance of the sole user with that id.
        return None
    
    """
    Query the transaction with specified transaction id
    """
    def query_txn_for_spec_transac(self, id):
        cursor = self.conn.execute("SELECT * FROM txn WHERE ID = ?", (id,))

        transactions = cursor.fetchone() # only expect a single transaction
        return transactions
    
    """
    Query txn for all transactions a user with id user_id is involved in, returns them as a list of labeled dictionaries
    """
    def query_txn_for_spec_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, sender_id, receiver_id, amount, accepted, message
            FROM txn
            WHERE sender_id = ? OR receiver_id = ?;
        """, (user_id, user_id))
        transactions = cursor.fetchall()

        transac_list = []
        for row in transactions: # every single transaction of that user, yield in nice dictionary form
            transac_dict = {
                "id": row[0],
                "timestamp": row[1],
                "sender_id": row[2],
                "receiver_id": row[3],
                "amount": row[4],
                "accepted": row[5],
                "message": row[6]
            }
            transac_list.append(transac_dict)
        return transac_list
    
    """
    Changes a transaction based on new accepted state
    """
    def update_transaction_status(self, txn_id, new_accepted):
        cursor = self.conn.cursor()
        timestamp = datetime.now()

        cursor.execute("""
            UPDATE txn
            SET accepted = ?,
                timestamp = ?
            WHERE id = ?;
        """, (new_accepted, timestamp, txn_id))

        self.conn.commit()
            
            


# Only <=1 instance of the database driver
# exists within the app at all times
DatabaseDriver = singleton(DatabaseDriver)
