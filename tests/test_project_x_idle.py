import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from artifact.animation.idle_scenes import RotatingIdleAnimation,IdleScene
from artifact.modes.photobooth_themes import THEMES

VIDEO=Path(__file__).resolve().parents[1]/'assets/idle/project_x/video/project-x-fan-10x.mp4'

def test_config_and_entire_video_decode():
 idle=RotatingIdleAnimation.__new__(RotatingIdleAnimation);idle._theme=THEMES['project-x']
 idle.idle_variant=idle._detect_idle_variant()
 assert idle.idle_variant=='project_x'
 assert idle._build_idle_scene_playlist()==[IdleScene.CRINGE_CIRCLE_VIDEO]
 assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO]=='PROJECT X'
 data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(VIDEO)]))
 assert len(data['streams'])==1
 video=data['streams'][0]
 assert (video['width'],video['height'],video['codec_name'],video['avg_frame_rate'])==(128,128,'h264','24/1')
 assert float(data['format']['duration'])==150
 subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(VIDEO),'-f','null','-'],check=True)

def test_player_reuses_frame_and_loops():
 import cv2
 idle=RotatingIdleAnimation.__new__(RotatingIdleAnimation)
 idle.idle_variant='project_x';idle._cv2_available=True
 idle.cringe_circle_video_capture=cv2.VideoCapture(str(VIDEO))
 idle.state=SimpleNamespace(time=0)
 idle._tropical_video_start_ms=0;idle._tropical_video_frame_index=-1;idle._tropical_video_frame=None
 idle._draw_cringe_overlay=lambda *args:None
 buffer=np.zeros((128,128,3),dtype=np.uint8)
 try:
  idle._render_cringe_circle_video(buffer);first=buffer.copy()
  idle.state.time=16;idle._render_cringe_circle_video(buffer)
  assert np.array_equal(first,buffer)
  idle.state.time=150000;idle._render_cringe_circle_video(buffer)
  assert np.array_equal(first,buffer)
 finally:idle.cringe_circle_video_capture.release()
