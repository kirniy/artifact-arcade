import asyncio,base64,io,json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from artifact.ai.client import GeminiClient
from artifact.ai.caricature import CaricatureStyle,CaricatureService
from artifact.modes.photobooth import PhotoboothMode,get_configured_photobooth_modes
from artifact.modes.photobooth_themes import THEMES
from artifact.animation.idle_scenes import RotatingIdleAnimation,IdleScene
ROOT=Path(__file__).resolve().parents[1]


def test_theme_routing_references_and_idle(monkeypatch):
    monkeypatch.setenv('PHOTOBOOTH_THEME','step-up');monkeypatch.setenv('PHOTOBOOTH_MENU_MODES','step_up');monkeypatch.setenv('ARTIFACT_CLUB_THEME_SCHEDULE','off')
    assert [m.theme_id_override for m in get_configured_photobooth_modes()]==['step-up']
    mode=PhotoboothMode.__new__(PhotoboothMode);mode._theme=THEMES['step-up'];mode.ai_style_key_override=None;mode._load_logo()
    assert len(mode._theme_reference_images)==2
    assert mode._get_caricature_styles()==(CaricatureStyle.PHOTOBOOTH_STEP_UP_SQUARE,CaricatureStyle.PHOTOBOOTH_STEP_UP)
    idle=RotatingIdleAnimation.__new__(RotatingIdleAnimation);idle._theme=mode._theme;idle.idle_variant=idle._detect_idle_variant()
    assert idle.idle_variant=='step_up'
    assert idle._build_idle_scene_playlist()==[IdleScene.CRINGE_CIRCLE_VIDEO]
    idle._cv2_available=True;idle._load_cringe_circle_video();assert idle.cringe_circle_video_path.name=='step-up-fans.mp4'


@pytest.mark.parametrize('status',[200,402,429,500])
def test_byteplus_only_route_no_google_or_paid_retry(monkeypatch,status):
    import aiohttp
    raw=io.BytesIO();Image.new('RGB',(20,30),'white').save(raw,'PNG');png=raw.getvalue();calls=[]
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def json(self):return {'data':[{'b64_json':base64.b64encode(png).decode()}]}
    Response.status=status
    class Session:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def post(self,url,**kw):calls.append((url,kw));return Response()
    monkeypatch.setattr(aiohttp,'ClientSession',Session)
    monkeypatch.setenv('BYTEPLUS_MODELARK_API_KEY','test-only')
    client=object.__new__(GeminiClient);client._image_generation_provider='byteplus'
    assert client.is_available
    result=asyncio.run(client.generate_image('cinematic',reference_photo=b'guest',extra_reference_images=[(b'emblem','image/png')],aspect_ratio='9:16'))
    assert result==(png if status==200 else None)
    assert len(calls)==1
    assert calls[0][0]=='https://ark.ap-southeast.bytepluses.com/api/v3/images/generations'
    payload=calls[0][1]['json'];assert payload['model']=='dola-seedream-5-0-flash-260915'
    assert payload['size']=='864x1536' and len(payload['image'])==2


def test_activation_preserves_quest_camera_and_private_rollback(tmp_path):
    env=tmp_path/'.env';original='ARTIFACT_SPIDERVERSE_QUEST_ENABLED=true\nARTIFACT_QUEST_PROFILE=party_exam\nPHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=false\nGEMINI_IMAGE_MODEL=preserved\n'
    env.write_text(original);env.chmod(0o600)
    variables=dict(os.environ,ARTIFACT_ENV_FILE=str(env),VNVNC_PYTHON=sys.executable,BYTEPLUS_MODELARK_API_KEY='test-only')
    subprocess.run(['bash',str(ROOT/'scripts/activate-step-up-photobooth.sh')],env=variables,check=True,capture_output=True)
    text=env.read_text()
    for line in original.splitlines():assert line in text
    for line in ['PHOTOBOOTH_THEME=step-up','PHOTOBOOTH_MENU_MODES=step_up','ARTIFACT_IMAGE_PROVIDER=byteplus','PHOTOBOOTH_AI_ENABLED=true','ARTIFACT_ENABLE_OPENROUTER_FALLBACK=false']:assert line in text
    backups=list(tmp_path.glob('.env.before-step-up-*'));assert len(backups)==1
    assert backups[0].read_text()==original and backups[0].stat().st_mode&0o777==0o600
    subprocess.run(['bash',str(ROOT/'scripts/activate-step-up-photobooth.sh')],env=variables,check=True,capture_output=True)
    assert env.read_text()==text and len(list(tmp_path.glob('.env.before-step-up-*')))==1


def test_prompt_service_uses_tested_cinematic_direction():
    out=io.BytesIO();Image.new('RGB',(10,20),'white').save(out,'PNG')
    class Client:
        is_available=True
        async def generate_image(self,**kwargs):self.kw=kwargs;return out.getvalue()
    c=Client();service=CaricatureService.__new__(CaricatureService);service._client=c
    refs=[(b'emblem','image/png'),(b'style','image/png')]
    result=asyncio.run(service.generate_caricature(b'guest',style=CaricatureStyle.PHOTOBOOTH_STEP_UP,extra_reference_images=refs))
    assert result and c.kw['aspect_ratio']=='9:16'
    assert 'cinematic dance-film editorial photograph' in c.kw['prompt']
    assert c.kw['extra_reference_images']==refs
