from types import SimpleNamespace
import numpy as np
from artifact.hardware.camera import picamera


def test_rgb_full_resolution_and_supported_focus(monkeypatch):
    class Fake:
        camera_controls={'AfMode': (0,2,0)}
        def create_still_configuration(self,**kw): self.config=kw;return kw
        def configure(self,config): pass
        def set_controls(self,values):self.values=values
        def start(self):pass
        def capture_array(self,name):return np.array([[[255,30,200]]],dtype=np.uint8)
    fake=Fake()
    monkeypatch.setattr(picamera,'_PICAMERA2_AVAILABLE',True)
    monkeypatch.setattr(picamera,'_picamera2',lambda:fake)
    monkeypatch.setattr(picamera,'controls',SimpleNamespace(AfModeEnum=SimpleNamespace(Continuous=2)),raising=False)
    camera=picamera.PiCamera()
    assert camera.open()
    assert fake.config['main']=={'size':(2048,1536),'format':'BGR888'}
    assert fake.values=={'AfMode':2}
    assert camera.capture_full().tolist()==[[[255,30,200]]]


def test_no_autofocus_control_on_unsupported_sensor(monkeypatch):
    class Fake:
        camera_controls={}
        def create_still_configuration(self,**kw):return kw
        def configure(self,config):pass
        def start(self):pass
        def set_controls(self,values):raise AssertionError('unsupported controls')
    monkeypatch.setattr(picamera,'_PICAMERA2_AVAILABLE',True)
    monkeypatch.setattr(picamera,'_picamera2',Fake)
    assert picamera.PiCamera().open()
