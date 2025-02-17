import paho.mqtt.client as mqtt
import cv2
import threading
import queue
import time
import json
import numpy as np

class StreamPublisher:
    def __init__(self, topic, gps_topic, video_address="new2.avi", start_stream=True, host="65.0.71.42", port=1883) -> None:
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)         
        self.client.max_inflight_messages_set(20)
        self.client.max_message_size = 10485760
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.on_disconnect = self.on_disconnect

        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()
        self.topic = topic
        self.gps_topic = gps_topic
        self.video_source = video_address

        self.cam = cv2.VideoCapture(self.video_source)
        self.frame_rate = self.cam.get(cv2.CAP_PROP_FPS)
        self.frame_time = 1.0 / self.frame_rate
        self.frame_queue = queue.Queue(maxsize=2)

        # Use GStreamer for H.264 Encoding
        self.gstreamer_pipeline = (
            "appsrc ! videoconvert ! video/x-raw,format=I420 ! "
            "x264enc speed-preset=ultrafast tune=zerolatency bitrate=500 key-int-max=30 ! "
            "h264parse ! mp4mux ! filesink location=output.mp4"
        )

        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.publish_thread = threading.Thread(target=self.publish_frames)
        self.gps_thread = threading.Thread(target=self.publish_gps_data)

        self.publish_success_count = 0
        self.publish_total_count = 0

        if start_stream:
            self.capture_thread.start()
            self.publish_thread.start()
            self.gps_thread.start()

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected with code {rc}. Reconnecting...")
        try:
            client.reconnect()
        except Exception as e:
            print(f"Reconnect failed: {e}")

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"✅ Connected to MQTT Broker with result code {reason_code}")

    def on_publish(self, client, userdata, mid, reason_code, properties=None):
        if reason_code.is_failure:
            print(f"Publish failed with code: {reason_code}")
        else:
            self.publish_success_count += 1


    def capture_frames(self):
        print("Capturing from video source: {}".format(self.video_source))
        prev_capture_time = time.time()

        while True:
            current_time = time.time()
            elapsed_time = current_time - prev_capture_time

            if elapsed_time >= self.frame_time:
                ret, img = self.cam.read()
                if not ret:
                    print("Failed to read frame")
                    break

                img_resized = cv2.resize(img, (1280, 720))

                if not self.frame_queue.full():
                    self.frame_queue.put(img_resized)
                else:
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put(img_resized)
                    except queue.Empty:
                        pass

                prev_capture_time = current_time
        self.cam.release()

    def publish_frames(self):
        print("Publishing to topic: {}".format(self.topic))

        while True:
            if not self.frame_queue.empty():
                img = self.frame_queue.get()

                # Encode frame using GStreamer
                success, encoded_frame = cv2.imencode('.jpg', img)
                if not success:
                    print("Error encoding frame!")
                    continue
                
                img_str = encoded_frame.tobytes()

                try:
                    result = self.client.publish(self.topic, img_str)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        print(f"Publish failed with code: {result.rc}")
                    self.publish_total_count += 1
                except Exception as e:
                    print(f"Failed to publish: {e}")

                if self.publish_total_count >= 10:
                    success_rate = self.publish_success_count / self.publish_total_count
                    if success_rate < 0.8:
                        self.frame_rate = max(5, self.frame_rate - 1)
                    elif success_rate > 0.9:
                        self.frame_rate = min(30, self.frame_rate + 1)
                    self.frame_time = 1.0 / self.frame_rate
                    print(f"Adjusted frame rate to: {self.frame_rate}")

                    self.publish_success_count = 0
                    self.publish_total_count = 0

    def publish_gps_data(self):
        print("Publishing GPS data to topic: {}".format(self.gps_topic))
        i = 0
        while True:
            i = i + 0.00025
            lati = 28.604537463058893 + i 
            longi = 77.36896549554069 + i
            print(lati)
            gps_data = { 
                'lat': lati ,  
                'lon': longi,  
                'alt': 100  
            }
            gps_message = json.dumps(gps_data)
            try:
                result = self.client.publish(self.gps_topic, gps_message)
                print("gps data published ", gps_data)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"GPS publish failed with code: {result.rc}")
            except Exception as e:
                print(f"Failed to publish GPS data: {e}")
            
            time.sleep(1)  # Publish GPS data every 2 seconds

if __name__ == "__main__":
    webcam = StreamPublisher("test", gps_topic="drone/gps", video_address="test.mp4")
