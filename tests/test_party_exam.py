from io import BytesIO
import uuid
import numpy as np
import pytest
from PIL import Image
from artifact.core.events import Event,EventBus,EventType
from artifact.modes.party_exam import PartyExamMode
from artifact.printing.party_exam_roll import PartyExamRollReceiptGenerator
from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
from test_spiderverse_quest import _context, _SilentAudio


def picture():
    b=BytesIO();Image.new('RGB',(450,600),'white').save(b,'PNG');return b.getvalue()


def test_private_print_one_document_and_permanent_qr():
    import cv2
    mode=PartyExamMode(_context());mode.enter();mode._start_quest_photo()
    data={'student_number':26091841,'night':'2026-09-19','claim_url':'https://t.me/vnvncbattlebot?start=exam_'+'a'*32}
    mode._student=data;mode._state.ai_label_bytes=picture()
    mode._start_printing_now();mode._start_printing_now()
    jobs=mode.context.event_bus.get_history(EventType.PRINT_START)
    assert len(jobs)==1
    payload=jobs[0].data
    assert payload['party_exam'] and 'qr_url' not in payload and 'photo' not in payload
    receipt=PhotoboothRollReceiptGenerator().generate_receipt('photobooth',payload)
    image=Image.open(BytesIO(receipt.preview_image))
    decoded,_,_=cv2.QRCodeDetector().detectAndDecode(np.array(image))
    assert decoded==data['claim_url']
    assert receipt.raw_commands.endswith(b'\x1dV\x00') or b'\x1dV' in receipt.raw_commands


def test_no_card_no_print_and_no_gallery(monkeypatch):
    mode=PartyExamMode(_context());mode.enter();mode._start_quest_photo();mode._state.photo_bytes=picture()
    monkeypatch.setattr(mode._uploader,'upload_bytes',lambda *a,**k:pytest.fail('public upload'))
    mode._upload_ai_result_async();mode._upload_raw_capture_async();mode._upload_photo_async();mode._start_printing_now()
    assert not mode.context.event_bus.get_history(EventType.PRINT_START)


def test_receipt_requires_personal_link():
    with pytest.raises(ValueError):PartyExamRollReceiptGenerator().render_document({'claim_url':'https://evil.test/'})


def test_kp7_profile_and_all_displays(monkeypatch):
    from artifact.modes.manager import ModeManager
    from artifact.core.state import StateMachine
    from artifact.graphics.renderer import Renderer
    from artifact.animation.engine import AnimationEngine
    monkeypatch.setenv('ARTIFACT_QUEST_PROFILE','party_exam')
    monkeypatch.setattr('artifact.modes.manager.get_audio_engine',lambda:_SilentAudio())
    bus=EventBus();manager=ModeManager(StateMachine(),bus,Renderer(),AnimationEngine(),enable_spiderverse_quest=True)
    bus.emit(Event(EventType.KEYPAD_PRESS,{'key':'7'}));manager.update(2000)
    mode=manager._current_mode;assert isinstance(mode,PartyExamMode)
    main=np.zeros((128,128,3),dtype=np.uint8);ticker=np.zeros((8,48,3),dtype=np.uint8)
    mode.render_main(main);mode.render_ticker(ticker)
    assert main.any() and len(mode.get_lcd_text())<=16
    mode._state.show_result=True;mode.render_main(main)


def test_print_failure_keeps_document_and_retry_identity():
    mode=PartyExamMode(_context());mode.enter();mode._start_quest_photo()
    mode._student={'student_number':26091841,'night':'2026-09-19','claim_url':'https://t.me/vnvncbattlebot?start=exam_'+'a'*32}
    mode._state.ai_label_bytes=picture();mode._state.show_result=True
    mode._start_printing_now();issue=mode._quest_print_id
    mode.on_input(Event(EventType.PRINT_ERROR,{'issue_id':issue}))
    mode._complete_session();assert mode._quest_print_id==issue
    mode.on_input(Event(EventType.BUTTON_PRESS,{}))
    assert mode._quest_receipt_queued and mode._quest_print_id==issue


@pytest.fixture(autouse=True)
def private_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv('PARTY_EXAM_PRIVATE_DIR', str(tmp_path/'jobs'))


def test_restart_recovers_identity_and_print_ack_prevents_recovery(tmp_path):
    import json
    root=PartyExamMode._private_root();issue=uuid.uuid4().hex
    card={'student_number':26091841,'night':'2026-09-19','claim_url':'https://t.me/vnvncbattlebot?start=exam_'+'b'*32}
    for name,data in [('source.jpg',picture()),('portrait.png',picture()),('student.json',json.dumps(card).encode())]:
        PartyExamMode._save_private(root/issue/name,data)
        assert (root/issue/name).stat().st_mode & 0o777 == 0o600
    mode=PartyExamMode(_context());mode.enter()
    assert mode._quest_print_id==issue and mode._print_error and mode._student==card
    assert not mode.context.event_bus.get_history(EventType.PRINT_START)
    mode.on_input(Event(EventType.BUTTON_PRESS,{}))
    assert mode.context.event_bus.get_history(EventType.PRINT_START)[-1].data['issue_id']==issue
    mode.on_input(Event(EventType.PRINT_COMPLETE,{'issue_id':issue}))
    assert (root/issue/'printed').exists()
    fresh=PartyExamMode(_context());fresh.enter()
    assert fresh._student is None and fresh._quest_print_id != issue


@pytest.mark.asyncio
async def test_issue_network_retry_reuses_portrait_and_id(monkeypatch):
    import asyncio
    mode=PartyExamMode(_context());mode.enter();mode._start_quest_photo()
    mode._state.photo_bytes=picture();issue=mode._quest_print_id
    mode._save_private(mode._private_root()/issue/'portrait.png',picture())
    monkeypatch.setattr('artifact.modes.party_exam.get_gemini_client',lambda:pytest.fail('portrait regenerated'))
    monkeypatch.setenv('ARTIFACT_KIOSK_DEVICE_ID','test-device')
    monkeypatch.setenv('ARTIFACT_KIOSK_DEVICE_SECRET','test-secret')
    calls=[]
    async def request(self,method,path,payload):
        calls.append(payload)
        if len(calls)==1:raise TimeoutError('response lost')
        return {'student_number':26091841,'night':'2026-09-18','claim_url':'https://t.me/vnvncbattlebot?start=exam_'+'c'*32}
    async def no_wait(seconds):pass
    monkeypatch.setattr('artifact.modes.party_exam.VNVNCKioskClient._request',request)
    monkeypatch.setattr(asyncio,'sleep',no_wait)
    result=await mode._generate_photobooth_grid()
    assert result and len(calls)==2 and calls[0]==calls[1] and calls[0]['issue_id']==issue
