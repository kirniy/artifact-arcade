import asyncio
import hashlib
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from PIL import Image
from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.ai.project_x import SCENES, build_prompt
from artifact.modes.photobooth import PhotoboothMode, get_configured_photobooth_modes, get_moscow_party_stamp
from artifact.modes.photobooth_themes import THEMES

@pytest.mark.parametrize('alias', ['project-x','project_x'])
def test_menu_and_canonical_emblem(alias, monkeypatch):
    monkeypatch.setenv('PHOTOBOOTH_MENU_MODES',alias)
    assert [m.theme_id_override for m in get_configured_photobooth_modes()]==['project-x']
    mode=PhotoboothMode.__new__(PhotoboothMode)
    mode._theme=THEMES['project-x'];mode.ai_style_key_override=None
    assert mode._get_caricature_styles()==(CaricatureStyle.PHOTOBOOTH_PROJECT_X_SQUARE,CaricatureStyle.PHOTOBOOTH_PROJECT_X)
    mode._load_logo()
    assert len(mode._theme_reference_images)==1
    assert hashlib.sha256(mode._theme_reference_images[0][0]).hexdigest()==mode._theme.required_reference_sha256

@pytest.mark.parametrize('square',[False,True])
def test_service_actual_dispatch(square):
    buf=io.BytesIO();Image.new('RGB',(90,160),'white').save(buf,format='PNG')
    class Client:
        is_available=True
        async def generate_image(self,**kwargs):
            self.call=kwargs
            return buf.getvalue()
    client=Client();service=CaricatureService.__new__(CaricatureService);service._client=client
    refs=[(b'canonical-emblem','image/png'),(b'identity','image/jpeg')]
    style=CaricatureStyle.PHOTOBOOTH_PROJECT_X_SQUARE if square else CaricatureStyle.PHOTOBOOTH_PROJECT_X
    result=asyncio.run(service.generate_caricature(b'guests',style=style,extra_reference_images=refs,prompt_variation_index=2))
    assert result and result.width==90
    assert client.call['reference_photo']==b'guests'
    assert client.call['extra_reference_images']==refs
    assert client.call['aspect_ratio']==('1:1' if square else '9:16')
    assert SCENES[2] in client.call['prompt']
    assert asyncio.run(service.generate_caricature(b'guests',style=style)) is None

def test_scene_variation_and_club_night():
    assert len({build_prompt(i) for i in range(4)})==4
    for i in range(4):
        assert '75%' in build_prompt(i) and 'BLACK AND WHITE' in build_prompt(i)
    theme=THEMES['project-x']
    before=get_moscow_party_stamp(theme,datetime(2026,9,19,6,59,tzinfo=ZoneInfo('Europe/Moscow')))
    after=get_moscow_party_stamp(theme,datetime(2026,9,19,7,0,tzinfo=ZoneInfo('Europe/Moscow')))
    assert before[0]!=after[0]
