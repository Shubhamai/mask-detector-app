
# Importing all necessary libraries
import streamlit as st
import cv2
import time
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.preprocessing.image import img_to_array
import numpy as np
from tensorflow.keras.models import load_model
from datetime import datetime
import sqlite3
import collections
import glob
import hashlib
from pathlib import Path
import os


# Connecting to the database
conn = sqlite3.connect('data.db')


def loading_models(source=0):
    """
    Function to loading the fanenet (Face Detector ) & MaskNet (Mask detector ) & reading the camera 



    Parameters
    ----------
    source : str or int
        The source link of the camera (default is 0)

    Returns
    ----------
        cv2 VideoCapture, faceNet, maskNet

    """

    faceNet = cv2.dnn.readNet("./models/face_detector/deploy.prototxt",
                              "./models/face_detector/res10_300x300_ssd_iter_140000.caffemodel")

    maskNet = load_model("./models/mask_detector/mask_detector.model")
    return cv2.VideoCapture(source), faceNet, maskNet


def make_hashes(password):
    """
    Function generate hash of a password



    Parameters
    ----------
    password : str
        The password that user inputs

    Returns
    ----------
        A hashed password

    """

    return hashlib.sha256(str.encode(password)).hexdigest()


def check_hashes(password, hashed_text):
    """
    Function to compare the password and hashed password while login  



    Parameters
    ----------
    password : str 
        The password that use inputs
    hashed_text : str
        The hashed password

    Returns
    ----------
        If password & hashed_text got matched, returns hashed_text, else False

    """

    if make_hashes(password) == hashed_text:
        return hashed_text
    return False


c = conn.cursor()


def create_usertable():
    """
    Function to create a new sqlite table  
    """
    c.execute(
        'CREATE TABLE IF NOT EXISTS userstable(username TEXT UNIQUE,password TEXT)')


def add_userdata(username, password):
    """
    Function add a user data while signup in the sqlite3 database 



    Parameters
    ----------
    username : str
    password: str

    Returns
    ----------
        Adds the data in the table

    """
    try:
        c.execute(
            'INSERT INTO userstable(username,password) VALUES (?,?,?,?)', (username, password))
        st.success("You have successfully created a valid Account")
        st.info("Go to Login Menu to login")
        os.mkdir(username)

    except:
        st.warning("Try using different username or try again later")

    conn.commit()


def login_user(username, password):
    """
    Function login the user will username & password 

    Parameters
    ----------
    username : str
    password: str

    """
    c.execute('SELECT * FROM userstable WHERE username =? AND password = ?',
              (username, password))
    data = c.fetchall()
    return data


def mask_detector(frame, detections, maskNet):
    """
    Function take the frame, face detections and maskNet and return the faces, locations and prediction  of mask   
    **The function/pipeline was highly inspired/taken from codeblogger in this kaggle notebook https://www.kaggle.com/codeblogger/mask-detection-for-the-video/code **


    Parameters
    ----------
    frame : The cv2 VideoCapture 
    detections : The faces detections from 
    maskNet : The maskNet detections network

    Returns
    ----------
    faces, locs, preds
    """

    faces = []
    locs = []
    preds = []
    (h, w) = frame.shape[:2]

    for i in range(0, detections.shape[2]):

        confidence = detections[0, 0, i, 2]

        if confidence > 0.6:

            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            (startX, startY) = (max(0, startX), max(0, startY))
            (endX, endY) = (min(w - 1, endX), min(h - 1, endY))

            face = frame[startY:endY, startX:endX]
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            face = cv2.resize(face, (224, 224))
            face = img_to_array(face)
            face = preprocess_input(face)

            faces.append(face)
            locs.append((startX, startY, endX, endY))

    if len(faces) > 0:
        faces = np.array(faces, dtype="float32")
        preds = maskNet.predict(faces, batch_size=32)

    return faces, locs, preds


def main():
    """The Application"""

    # Setting the title of application
    st.title("Mask Detection Application 😷")

    # The 3 Navigation pages
    menu = ["Home", "Login", "SignUp"]
    choice = st.sidebar.selectbox("Menu", menu)

    # If user select's home
    if choice == "Home":

        st.subheader("Home")

        st.write("")

        st.warning(
            "To get Access to the Application. First **SignUp** and then **Login** to the application in the **Sidebar**")
        st.info("If you have already **SignUp**, just **Login** to the **Application**")

    # if user selects login
    elif choice == "Login":

        # Take username & password
        username = st.sidebar.text_input("User Name")
        password = st.sidebar.text_input("Password", type='password')

        # If user selects on login
        if st.sidebar.checkbox("Login"):

            create_usertable()

            # Take thr password and convert it to hash
            hashed_password = make_hashes(password)

            # Login the user
            result = login_user(username, check_hashes(
                password, hashed_password))

            # If result was not false
            if result:

                # Cjeckbox to see the violations
                violation_checkbox = st.sidebar.checkbox("Show All Voilations")

                # if user selects on violation checkbox
                if violation_checkbox:
                    st.write("")
                    st.header('Violations')

                    # Read all folders & files and show the images
                    folders = glob.glob(f'./{username}/*')

                    for folder in folders:
                        st.subheader(folder)
                        for f in glob.glob(folder+'/*.jpg'):

                            st.image(f, caption=f)

                # If user just login
                else:

                    st.success("Logged In as {}".format(username))

                    # Take the camera link from user
                    camera_link = st.text_input(
                        "Enter the Camera link. Use 0 if you want to use your webcam")

                    # If camera link is valid
                    if camera_link != "":

                        # Try to convert the camea_link to int
                        try:
                            camera_link = int(camera_link)

                        except:
                            pass

                        # Set the frame for showing like video
                        frameST = st.empty()

                        # Setting the header for showing live violations
                        violations_header = st.empty()

                        # Count current people without mask and in previous frame
                        people_without_mask = 0
                        previous_people_without_mask = 0

                        # Loading all the models inputting camera link
                        cap, faceNet, maskNet = loading_models(camera_link)

                        while True:

                            # Start reading the csmera
                            ret, frame = cap.read()

                            # If able to read camera, continue or if not able to read camera, throw an warning
                            try:
                                (h, w) = frame.shape[:2]
                            except:
                                st.warning(
                                    "Please make sure the IP is correct")
                                break

                            # Preprocessing the Image
                            blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                                         (104.0, 177.0, 123.0))

                            # Inputting the frame to the faceNet Model
                            faceNet.setInput(blob)
                            detections = faceNet.forward()

                            # Input the frame, face detections and maskNet
                            faces, locs, preds = mask_detector(
                                frame, detections, maskNet)

                            # Get the number of people without mask
                            for i in preds:
                                if i[0] < [1]:
                                    people_without_mask += 1
                                else:
                                    pass

                            # Loop throught every boxes locations & predictions and make a bounding box around the face
                            # If face had no mask, make red bouncing box, else green bounding box
                            for (box, pred) in zip(locs, preds):

                                (startX, startY, endX, endY) = box
                                (mask, withoutMask) = pred

                                if mask > withoutMask:
                                    label = "Mask"
                                else:
                                    label = "No Mask"

                                color = (0, 255, 0) if label == "Mask" else (
                                    0, 0, 255)

                                cv2.rectangle(frame, (startX, startY),
                                              (endX, endY), color, 2)

                            # If there we not people without mask
                            if people_without_mask == 0:
                                pass

                            # If there were people without mask
                            else:

                                # If people with mask are different with current and previous frame
                                if previous_people_without_mask != people_without_mask:

                                    # Get the current date & time
                                    now = datetime.now()

                                    # Save the image
                                    folder_path = Path(
                                        f"./{username}/{now.strftime('%d-%m-%Y')}")
                                    folder_path.mkdir(
                                        exist_ok=True, parents=True)

                                    dt_string = now.strftime(
                                        "%d-%m-%Y %H-%M-%S")

                                    # Show the image
                                    cv2.imwrite(
                                        f"{folder_path.as_posix()}/{dt_string}.jpg", frame)
                                    st.image(
                                        frame,  channels="BGR", use_column_width=True, caption=dt_string)

                                else:
                                    pass

                            previous_people_without_mask = people_without_mask
                            people_without_mask = 0

                            # Show the live feed
                            frameST.image(frame, channels="BGR",
                                          use_column_width=True)
                            violations_header.header("Violations 🚫")

                    else:
                        pass

            # If user enter password while login was incorrect
            else:
                st.warning("Incorrect Username/Password")

    # If user goes to signup
    elif choice == "SignUp":

        st.subheader("Create New Account")

        # Take the username & password
        new_user = st.text_input("Username")
        new_password = st.text_input("Password", type='password')

        # When user clicks on Signup button
        if st.button("Signup"):

            # Add the data in database
            create_usertable()
            add_userdata(new_user, make_hashes(new_password))


# Run the application
if __name__ == '__main__':
    main()
