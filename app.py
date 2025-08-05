
# code to connect to mysql database

# app.py (Modified for MySQL)

import mysql.connector
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition
import numpy as np
import base64
import io
from PIL import Image

app = Flask(__name__)
CORS(app)

# --- Database Connection Configuration ---
db_config = {
    'user': 'root',
    'password': '#Vt@097209',
    'host': 'localhost',
    'database': 'sarthak_db'
}

#populate the datastructure from database
def populateAttendanceData():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("select employee_id,check_in_time from employee_attendance")
    rows = cursor.fetchall()
    attendance_data = {row['employee_id']:row['check_in_time'] for row in rows}
    cursor.close()
    conn.close()
    return attendance_data

def base64_to_image(base64_string):
    if "," in base64_string:
        base64_string = base64_string.split(',')[1]
    img_data = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(img_data))

    #this code is modified to handle 4-channel RGBA image in addition to standard 3-channel RGB 
    if image.mode == 'RGBA':
        image = image.convert('RGB')

    return image

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    employee_id = data.get('employeeId')
    image_data = data.get('image')

    if not employee_id or not image_data:
        return jsonify({"status": "error", "message": "Missing employee ID or image"}), 400

    try:
        image_array = np.array(base64_to_image(image_data))
        new_embedding_list = face_recognition.face_encodings(image_array)

        if len(new_embedding_list) == 0:
            return jsonify({"status": "error", "message": "No face found"}), 400

        new_embedding = new_embedding_list[0]

        # --- Connect to DB and check for duplicates ---
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Check if employee ID is taken
        # cursor.execute("SELECT id FROM employees WHERE employee_id = %s", (employee_id,))
        # if cursor.fetchone():
        #     return jsonify({"status": "error", "message": f"Employee ID {employee_id} already registered."}), 409

        # # Check for duplicate faces by comparing with all stored embeddings
        # cursor.execute("SELECT employee_id, embedding FROM employees")
        # known_employees = cursor.fetchall()

        # for employee in known_employees:
        #     known_embedding = np.frombuffer(employee['embedding'])
        #     is_match = face_recognition.compare_faces([known_embedding], new_embedding, tolerance=0.5)[0]
        #     if is_match:
        #         return jsonify({"status": "error", "message": f"This face is already registered with ID {employee['employee_id']}"}), 409

        # --- Insert new employee ---
        # Serialize the NumPy array to bytes to store in the BLOB field
        embedding_bytes = new_embedding.tobytes()
        cursor.execute(
            "INSERT INTO employees (employee_id, embedding) VALUES (%s, %s)",
            (employee_id, embedding_bytes)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": f"Employee {employee_id} registered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recognize', methods=['POST'])
def recognize():
    attendance_data = populateAttendanceData()
    print(attendance_data)
    c_id = request.get_json().get('employeeId')
    image_data = request.get_json().get('image')

    if not image_data:
        return jsonify({"status": "error", "message": "No image provided"}), 400

    try:
        image_array = np.array(base64_to_image(image_data))
        live_embedding_list = face_recognition.face_encodings(image_array)

        if len(live_embedding_list) == 0:
            return jsonify({"status": "not_found", "message": "No face found in the live image"})

        live_embedding = live_embedding_list[0]

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT employee_id, embedding FROM employees")
        all_employees = cursor.fetchall()

        # cursor.close()
        # conn.close()

        # --- MODIFIED LOGIC: Find all matches ---
        
        # 1. Create an empty list to store all matching IDs.
        matching_ids = []

        matching_ids = []
        check_in_time = datetime.datetime.now()
        for employee in all_employees:
            known_embedding = np.frombuffer(employee['embedding'],dtype=np.float64)
            is_match = face_recognition.compare_faces([known_embedding], live_embedding, tolerance=0.6)[0]
            if is_match:
                matching_ids.append(employee['employee_id'])
                
        print("*******************************")
        print(attendance_data)
        flag = None
        key = None
        if any(key in attendance_data for key in matching_ids):
            if key!=c_id:
                flag = 'red'
        elif any(key in attendance_data for key in matching_ids):
            if key==c_id:
                flag = 'orange'
        else:
            flag = 'green'
        current_time_stamp = datetime.datetime.now()
        # 4. After checking all employees, return the result.
        if len(matching_ids)>=1 and flag=='green':
            cursor.execute("INSERT INTO employee_attendance (employee_id,attendance_status,check_in_time) VALUES (%s, %s,%s)",(c_id,'marked',current_time_stamp))
            conn.commit()
            # write code to save the state to database
            attendance_data
            cursor.close()
            conn.close()
            return jsonify({
                "status": "success", 
                "message": f"Welcome,{c_id}! Attendance Marked",
                "matching_ids": matching_ids
                })
        elif len(matching_ids)>=1 and flag=='orange':
            return jsonify({
                "status": "error", 
                "message": f"Attemp to re-mark attendance for,{c_id}! Attendance Already Marked",
                "matching_ids": matching_ids
                })            
        else:
            return jsonify({
                "status": "error",
                "message":f"cannot mark attendance for {c_id}!"
            })  
            
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": f"Database error: {err}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {e}"}), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)