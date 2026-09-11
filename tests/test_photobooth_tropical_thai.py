import asyncio
import hashlib
import io
import os
from pathlib import Path
import subprocess

import pytest
from PIL import Image
from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.ai.tropical_thai import SCENES, build_prompt
from artifact.animation.idle_scenes import IdleScene, RotatingIdleAnimation
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('alias',['tropical-thai','tropical_thai'])
def test_theme_menu_and_idle(alias,monkeypatch):
    monkeypatch.setenv('PHOTOBOOTH_MENU_MODES',alias)
    monkeypatch.setenv('PHOTOBOOTH_THEME','tropical-thai')
    assert [m.theme_id_override for m in get_configured_photobooth_modes()] == ['tropical-thai']
    theme=THEMES['tropical-thai']
    mode=PhotoboothMode.__new__(PhotoboothMode)
    mode._theme=theme;mode.ai_style_key_override=None
    assert mode._get_caricature_styles()==(CaricatureStyle.PHOTOBOOTH_TROPICAL_THAI_SQUARE,CaricatureStyle.PHOTOBOOTH_TROPICAL_THAI)
    mode._load_logo()
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest()==theme.required_reference_sha256
    idle=RotatingIdleAnimation.__new__(RotatingIdleAnimation);idle._theme=theme
    idle.idle_variant=idle._detect_idle_variant()
    assert idle.idle_variant=='tropical_thai'
    assert idle._build_idle_scene_playlist()==[IdleScene.CRINGE_CIRCLE_VIDEO]
    assert idle._build_variant_scene_titles()[IdleScene.CRINGE_CIRCLE_VIDEO]=='TROPICAL THAI'
    assert theme.ticker_color[0]==0

@pytest.mark.parametrize('square',[False,True])
def test_real_service_routes_tropical_prompt_and_preserves_refs(square):
    buf=io.BytesIO();Image.new('RGB',(90,160),(100,200,180)).save(buf,format='PNG')
    class Client:
        is_available=True
        async def generate_image(self,**kwargs):
            self.call=kwargs
            return buf.getvalue()
    client=Client();service=CaricatureService.__new__(CaricatureService);service._client=client
    refs=[(b'canonical-emblem','image/png'),(b'face-crop','image/jpeg')]
    style=CaricatureStyle.PHOTOBOOTH_TROPICAL_THAI_SQUARE if square else CaricatureStyle.PHOTOBOOTH_TROPICAL_THAI
    result=asyncio.run(service.generate_caricature(b'original-guests',style=style,extra_reference_images=refs,prompt_variation_index=1))
    assert result and (result.width,result.height)==(90,160)
    assert client.call['aspect_ratio']==('1:1' if square else '9:16')
    assert client.call['reference_photo']==b'original-guests'
    assert client.call['extra_reference_images']==refs
    prompt=client.call['prompt']
    assert 'CLOTHING LOCK' in prompt and 'Octane' in prompt and '70%' in prompt
    assert 'Image 2 is the exact' in prompt and SCENES[1] in prompt
    assert 'REPLACE the original room/background' in prompt
    assert asyncio.run(service.generate_caricature(b'original',style=style)) is None


def test_activation_keeps_provider_and_disables_quest(tmp_path):
    env_file=tmp_path/'.env'
    env_file.write_text('PHOTOBOOTH_THEME=vse-svoi\nARTIFACT_SPIDERVERSE_QUEST_ENABLED=true\nARTIFACT_IMAGE_PROVIDER=vertex\nKEEP_ME=unchanged\n')
    import sys
    env={**os.environ,'ARTIFACT_REMOTE_DIR':str(ROOT),'ARTIFACT_ENV_FILE':str(env_file),'VNVNC_PYTHON':sys.executable}
    subprocess.run(['bash',str(ROOT/'scripts/activate-tropical-thai-photobooth.sh')],env=env,check=True,capture_output=True)
    text=env_file.read_text()
    assert 'PHOTOBOOTH_THEME=tropical-thai' in text
    assert 'ARTIFACT_SPIDERVERSE_QUEST_ENABLED=false' in text
    assert 'ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED=0' in text
    assert 'ARTIFACT_IMAGE_PROVIDER=vertex' in text and 'KEEP_ME=unchanged' in text
    before=env_file.read_bytes()
    env['TROPICAL_THAI_IDLE_VIDEO_PATH']=str(tmp_path/'missing.mp4')
    result=subprocess.run(['bash',str(ROOT/'scripts/activate-tropical-thai-photobooth.sh')],env=env,capture_output=True)
    assert result.returncode != 0 and env_file.read_bytes()==before


def test_variations_are_distinct_but_preserve_rules():
    assert len({build_prompt(i) for i in range(4)})==4
    for i in range(4):
        assert 'original clothes exactly' in build_prompt(i)
        assert 'no black video background' in build_prompt(i)


def test_idle_video_uses_elapsed_time_and_loops(monkeypatch):
    import sys
    import types
    import numpy as np
    class Capture:
        def __init__(self): self.position=0;self.reads=0
        def isOpened(self):return True
        def get(self,key):return {1:24,2:3614}[key]
        def set(self,key,value):self.position=value
        def read(self):
            self.reads+=1;self.position+=1
            return True,np.zeros((128,128,3),dtype=np.uint8)
    monkeypatch.setitem(sys.modules,'cv2',types.SimpleNamespace(CAP_PROP_FPS=1,CAP_PROP_FRAME_COUNT=2,CAP_PROP_POS_FRAMES=3,COLOR_BGR2RGB=4,cvtColor=lambda f,c:f))
    idle=RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._cv2_available=True;idle.idle_variant='tropical_thai';idle.cringe_circle_video_capture=Capture()
    idle.state=types.SimpleNamespace(time=0)
    idle._tropical_video_start_ms=0;idle._tropical_video_frame_index=-1;idle._tropical_video_frame=None
    idle._draw_cringe_overlay=lambda *a:None
    buffer=np.zeros((128,128,3),dtype=np.uint8)
    idle._render_cringe_circle_video(buffer)
    idle.state.time=16;idle._render_cringe_circle_video(buffer)
    assert idle.cringe_circle_video_capture.reads==1
    idle.state.time=1000;idle._render_cringe_circle_video(buffer)
    assert idle._tropical_video_frame_index==24
    idle.state.time=3614/24*1000+10;idle._render_cringe_circle_video(buffer)
    assert idle._tropical_video_frame_index==0
