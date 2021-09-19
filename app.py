# required imports# the sqlite3 library allows us to communicate with the sqlite database
import sqlite3
# we are adding the import 'g' which will be used for the database
from flask import Flask, render_template, request, g, session, redirect, url_for, escape, flash
from datetime import datetime

# the database file we are going to communicate with
DATABASE = './assignment3.db'

global_user = ''

# connects to the database
def get_db():
    # if there is a database, use it
    db = getattr(g, '_database', None)
    if db is None:
        # otherwise, create a database to use
        db = g._database = sqlite3.connect(DATABASE)
    return db

# given a query, executes and returns the result
def query_db(query, args=(), one=False): #function taken from lecture code, hope that's ok
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv    

# converts the tuples from get_db() into dictionaries
def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))

def time():
    return datetime.now().strftime("%Y/%m/%d, %H:%M:%S") #time formatted like shown in string

items = {}
filled = 0
instructor_items = {}
inst_filled = 0

def fill_items():
    db = get_db()
    items['student'] = query_db('select * from Students where Username=%s' % global_user)[0] #current student
    items['instructors'] = [i[0] for i in query_db('select Username from Users where Type="Instructor"')] #uesrname of instructors, 0th index because they're tuples
    items['users'] = [i[0] for i in query_db('select Username from Users')] #same idea as above but for *all* usernames
    db.close()
    global filled
    filled = 1

def fill_inst():
    db = get_db()
    db.row_factory = make_dicts
    instructor_items['students'] = [i for i in query_db('select * from Students')] #list of students
    instructor_items['regrades'] = [i for i in query_db('select * from Regrades where Status!="Finished";')] #list of regrades
    instructor_items['feedbacks'] = [i for i in query_db('select * from Feedback where Instructor=%s' % global_user)] #list of feedback
    db.close()
    global inst_filled
    inst_filled = 1

# tells Flask that "this" is the current running app
app = Flask(__name__)

# secret key for the session.
app.secret_key='John Wick' #with a pencil!

# this function gets called when the Flask app shuts down
# tears down the database connection
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        # close the database if we are connected to it
        db.close()

def render_student_html(flashed_message=''):
    if not filled: fill_items() #fill_items fills up a globally defined dict, so only fill it once
    return render_template('student.html', student=items['student'], instructors=items['instructors'], users=items['users'], flashed_message=flashed_message) #renders student.html with these variables

def render_instructor_html():
    if not inst_filled: fill_inst() #same ideas as render_student_html
    return render_template('instructor.html', student=instructor_items['students'], regrades=instructor_items['regrades'], feedbacks=instructor_items['feedbacks'])

@app.route('/',methods=['GET','POST'])
def login():
    if request.method=='POST':
        sql = "SELECT *FROM Users"
        results = query_db(sql, args=(), one=False)
        for result in results:
            #If the username-password pair is found in the database...
            if result[2]==request.form['username']:
                if result[3]==request.form['password']:
                    session['username']=request.form['username']
                    #Take the user to the website.
                    global global_user
                    global_user = "'" + session['username'] + "'"
                    account_type = query_db('select Type from Users where Username=%s' % global_user)[0][0]
                    return render_instructor_html() if account_type == 'Instructor' else render_student_html()
        flash("Incorrect username/password!! Please try again.")
        return render_template("login.html")
    elif global_user != '':
        #If user is already logged in, take them to the website.
        #global global_user
        #global_user = "'" + session['username'] + "'"
        account_type = query_db('select Type from Users where Username=%s' % global_user)[0][0]
        return render_instructor_html() if account_type == 'Instructor' else render_student_html()
    else:
        #Else, take them to the login page.
        return render_template("login.html")

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        #If username has whitespace...
        if not request.form['username'].isalnum():
            #Tell user to change the username.
            flash("Username shouldn't have any whitespaces!!")
            return render_template("register.html")
        
        #If confirm password is not same as password...
        if request.form['password1']!=request.form['password2']:
            #Tell user to check password.
            flash("Please enter the same password!!")
            return render_template("register.html")
        
        sql = "SELECT *FROM Users"
        results = query_db(sql, args=(), one=False)
        for result in results:
            #If the username is found in the database...
            if result[2]==request.form['username']:
                #Tell user to choose some other username.
                flash("Username taken. Choose a different username.")
                return render_template("register.html")

        #If all fields are ok, add account type, username, and password to the database.
        db = get_db()
        db.row_factory = make_dicts
        # make a new cursor from the database connection
        cur = db.cursor()

        # get the post body
        new_user = request.form

        # insert the new user into the database
        cur.execute("INSERT into Users (Type, Name, Username, Password) values (?, ?, ?, ?)", [
            new_user['account_type'],
            new_user['name'],
            new_user['username'],
            new_user['password1']
        ])
        if new_user['account_type'] == 'Student': #initialize grades as 0 if new student
            cur.execute('insert into Students (Name, Username, A1, A2, A3, A4, TT1, TT2, TT3, TT4, Final) values (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)', (new_user['name'], new_user['username']))
        
        # commit the the change to the database
        db.commit()
        # close the cursor
        cur.close()
        return redirect(url_for('login'))
    else:
        #Else, take them to the registration page.
        return render_template("register.html")
               
@app.route('/logout')
def logout():
    global global_user #changes value of global var
    global_user = '' #resets user
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/feedback')
def submit_feedback():
    con = sqlite3.connect(DATABASE)
    c = con.cursor()
    instructor = request.args.get('feedback_instructor') #instructor to receive feedback
    text = request.args.get('feedback_text') #the feedback the user wrote
    c.execute("INSERT INTO Feedback (Time, Instructor, Text) VALUES (?, ?, ?)", (time(), instructor, text)) #insert to db
    con.commit() #commit to db
    flash('Feedback submitted successfully!') #show success message
    return render_student_html()

@app.route('/regrade')
def submit_regrade():
    con = sqlite3.connect(DATABASE)
    c = con.cursor()
    all_regrades = query_db('select Username, Assessment from Regrades') #all regrade requests as tuples
    assignment = request.args.get('regrade_assignment')
    text = request.args.get('regrade_text')
    for req in all_regrades: #goes through all the regrade requests primary keys which are requested assignment and the user
        if (global_user == req[0] and assignment == req[1]): #already requested (the assignment and user both match)
            flash('You already requested a regrade for this assignment! Try another one.')
            return render_student_html() #don't submit and flash a message
    c.execute("insert into Regrades (Username, Time, Assessment, Reason, Status) values (?, ?, ?, ?, ?)", (global_user, time(), assignment, text, "unfinished")) #submitting
    con.commit()
    flash('Regrade submitted successfully!')
    return render_student_html() #submit, flash success message

""" Instructor part
@app.route('/')
def root():
    db = get_db()
    db.row_factory = make_dicts
    #check accout existance
    
    #if user not in Users, redirect to login page

    #if user in User,check whether student or instructor
        #if student redirect to student page
        #if instructor redirect to instructor page
    students=[]
    regrades=[]
    feedbacks=[]
    for student in query_db('select * from Students'):
        students.append(student)
    for regrade in query_db('select * from Regrades where Status!="Finished";'):
        regrades.append(regrade)
    for feedback in query_db('select * from Feedback where Instructor=?'):
        feedbacks.append(feedback)
    db.close()
    return render_template('instructor.html', student=students, regrades=regrades, feedback=feedbacks)

@app.route('/regraded', methods=['POST'])
def regrade():
    db = get_db()
    db.row_factory = make_dicts
    cur = db.cursor()

    studentID = request.form['student']
    assessment = request.form['assessment']
    grade = request.form['new-grade']

    cur.execute("UPDATE Students SET "+assessment+"=? where Username = ?", [grade, studentID])
    db.commit()
    cur.close()

    return redirect(url_for('root'))
"""
    
@app.route('/regraded', methods=['POST'])
def regrade():
    db = get_db()
    db.row_factory = make_dicts
    cur = db.cursor()
    studentID = request.form['student']
    assessment = request.form['assessment']
    grade = request.form['new-grade']
    cur.execute("UPDATE Students SET "+assessment+"=? where Username = ?", [grade, studentID])
    db.commit()
    cur.close()
    db = get_db()
    items['student'] = [i for i in query_db("select * from Students where Username='%s'" % studentID)[0].values()] #add changes to global variable
    db.close()
    return redirect(url_for('login'))

if __name__=="__main__":
    app.run(debug=True)
