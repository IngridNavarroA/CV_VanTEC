#!/usr/bin/env python
"""
    @modified: Wed Jan 30, 2019
    @author: Ingrid Navarro 
    @file: detector_node.py
    @version: 1.0
    @brief:    
        This code implements a ROS node to perform object detection and classification 
        using YOLO detection frameworks. Node receives frames from another node and 
        publishes the coordinates of the detected objects. 
    @requirements: 
        Tested on python2.7 and python3.6. 
        OpenCV version 3.4+ (because it uses the "dnn" module).
        Cuda version 8.0
        Tested on ROS Kinetic. 
        Tested on Ubuntu 16.04 LTS
"""
from detection.detector import Detector 
from std_msgs.msg import String
from imutils.video import VideoStream
from imutils.video import FPS

from custom_msgs.srv import ColorDeImagen
from cv_bridge import CvBridge, CvBridgeError

import imutils
import argparse
import numpy as np 
import time
import rospy
import cv2

# Parse arguments
ap = argparse.ArgumentParser()
ap.add_argument('--config', required=True, help = 'Path to yolo config file')
ap.add_argument('--weights', required=True, help = 'Path to yolo pre-trained weights')
ap.add_argument('--classes', required=True, help = 'Path to text file containing class names')
ap.add_argument('--video', required=True, help = 'Path to the video' )
args = ap.parse_args()

bridge = CvBridge()

class Color():
    BLUE  = '\033[94m'
    GREEN = '\033[92m'
    RED  = '\033[91m'
    DONE  = '\033[0m'
    
def add_brightness(image):
    image_HLS = cv2.cvtColor(image,cv2.COLOR_RGB2HLS) ## Conversion to HLS
    image_HLS = np.array(image_HLS, dtype = np.float64) 
    random_brightness_coefficient = 1.5 ## generates value between 0.5 and 1.5
    image_HLS[:,:,1] = image_HLS[:,:,1]*random_brightness_coefficient ## scale pixel values up or down for channel 1(Lightness)
    image_HLS[:,:,1][image_HLS[:,:,1]>255]  = 255 ##Sets all values above 255 to 255
    image_HLS = np.array(image_HLS, dtype = np.uint8)
    image_RGB = cv2.cvtColor(image_HLS,cv2.COLOR_HLS2RGB) ## Conversion to RGB
    return image_RGB

def add_darkness(image):
    image_HLS = cv2.cvtColor(image,cv2.COLOR_RGB2HLS) ## Conversion to HLS
    image_HLS = np.array(image_HLS, dtype = np.float64) 
    random_brightness_coefficient = 0.5 ## generates value between 0.5 and 1.5
    image_HLS[:,:,1] = image_HLS[:,:,1]*random_brightness_coefficient ## scale pixel values up or down for channel 1(Lightness)
    image_HLS[:,:,1][image_HLS[:,:,1]>255]  = 255 ##Sets all values above 255 to 255
    image_HLS = np.array(image_HLS, dtype = np.uint8)
    image_RGB = cv2.cvtColor(image_HLS,cv2.COLOR_HLS2RGB) ## Conversion to RGB
    return image_RGB

def enviar_img(img,x,y,w,h):

	global bridge

	img = bridge.cv2_to_imgmsg(img, encoding = "bgr8")
	rospy.wait_for_service("/get_color")
	try:
		service = rospy.ServiceProxy("/get_color", ColorDeImagen)
		color = service(img,x,y,w,h)
		#rospy.loginfo(color)
		return color
	except rospyServicesException as e:
		rospy.logerr(e)


def send_message(color, msg):
    """ Publish message to ros node. """
    msg = color + msg + Color.DONE
    rospy.loginfo(msg)
    detector_pub.publish(msg)

def detect():
    """ Performs object detection and publishes coordinates. """
    
    # Initialize detector 
    send_message(Color.GREEN, "[INFO] Initializing TinyYOLOv3 detector.")
    det = Detector(args.config, args.weights, args.classes)
    (H, W) = (None, None)

    # Load model 
    send_message(Color.GREEN, "[INFO] Loading network model.")
    net = det.load_model()

    # Initilialize Video Stream
    send_message(Color.GREEN, "[INFO] Starting video stream.")
    if args.video == "0":
        video = cv2.VideoCapture(0)
    else:
        video = cv2.VideoCapture(args.video)

    counter = 0
    dets = 0
    nondets = 0
    detect = True
    fps = FPS().start()
    boxes, confidences, indices, cls_ids = [], [], [], []

    while not rospy.is_shutdown() or video.isOpened():
        # Grab next frame
        ret, frame = video.read()
        
    ##AQUI SE MODIFICA EL VIDEO
        
        #frame = add_brightness(frame)
        #frame = add_darkness(frame)
        
        
        
        if not ret:
            send_message(Color.RED, "[DONE] Finished processing.")
            cv2.waitKey(2000)
            break
        elif cv2.waitKey(1) & 0xFF == ord ('q'):
            send_message(Color.RED, "[DONE] Quitting program.")
            break

        frame = imutils.resize(frame, width=1000)
        (H, W) = frame.shape[:2]
        if det.get_w() is None or det.get_h() is None:
            det.set_h(H)
            det.set_w(W)
        
        # Perform detection 
        if detect:
            detect = False
            dets += 1
            # Get bounding boxes, condifences, indices and class IDs
            boxes, confidences, indices, cls_ids = det.get_detections(net, frame)

            # Publish detections
            det_str = "Det: {}, BBoxes {}".format(dets, boxes)
            send_message(Color.BLUE, det_str)
        else:
            nondets += 1
            counter += 1
            if counter == 24:
                detect = True
                counter = 0

        # If there were any previous detections, draw them
        for ix in indices:
            i = ix[0]
            box = boxes[i]
            x, y, w, h = box
            x, y, w, h = int(x), int(y), int(w), int(h)
            
            color = enviar_img(frame,x,y,h,w)
            
            color = str(color.color)
            
            det.draw_prediction(frame, cls_ids[i], confidences[i], color, x, y, x+w, y+h)

        fps.update()
        fps.stop()

        info = [
            ("Detects: ", dets),
            ("No detects: ", nondets),
            ("FPS", "{:.2F}".format(fps.fps())),
        ]
        for (i, (k, v)) in enumerate(info):
            text = "{}: {}".format(k, v)
            cv2.putText(frame, text, (10, det.get_h() - ((i * 20) + 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Show current frame
        cv2.imshow("Frame", frame)

        rate.sleep()

if __name__ == '__main__':
    try:
        # Create publisher 
        detector_pub = rospy.Publisher('detections', String, queue_size=10)
        rospy.init_node('detector')
        rate = rospy.Rate(10) # 10Hz
        detect()
    except rospy.ROSInterruptException:
        pass
