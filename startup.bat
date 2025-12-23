@echo off
echo Starting RTSP stream from USB{1/2/3/4} Video...
ffmpeg -f dshow -rtbufsize 512M -i video="USB2 Video" -rtsp_transport tcp -vcodec libx264 -pix_fmt yuv420p -preset ultrafast -tune zerolatency -f rtsp rtsp://127.0.0.1:8554/test
pause

