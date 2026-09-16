import io
import threading
from types import SimpleNamespace
import numpy as np
from PIL import Image
from artifact.utils.capture_quality import evaluate,choose
from artifact.utils.camera_service import CameraService
from artifact.hardware.camera.picamera import PiCamera


def test_face_region_not_sharp_background():
    import cv2
    sharp=np.zeros((200,200,3),dtype=np.uint8)
    sharp[50:150:4,50:150]=180
    blurred=cv2.GaussianBlur(sharp,(15,15),4)
    # Background distractions don't contribute to explicitly supplied face box.
    blurred[:30,::2]=255
    a=evaluate(sharp,[(50,50,100,100)])
    b=evaluate(blurred,[(50,50,100,100)])
    assert a['score']>b['score']
    assert choose([a,b])==0
    assert choose([{'faces':1,'score':100},{'faces':2,'score':1}])==1


def test_request_is_released_even_when_metadata_fails():
    released=[]
    request=SimpleNamespace(make_array=lambda name:np.zeros((2,2,3),dtype=np.uint8),
        get_metadata=lambda:(_ for _ in ()).throw(ValueError()),release=lambda:released.append(True))
    cam=PiCamera();cam._camera=SimpleNamespace(capture_request=lambda:request);cam._is_streaming=True
    import pytest
    with pytest.raises(ValueError):cam.capture_full_with_metadata()
    assert released==[True]


def test_burst_partial_failure_preserves_success(monkeypatch):
    monkeypatch.setenv("ARTIFACT_CAMERA_BURST_ENABLED", "1")
    frames=iter([np.full((20,20,3),70,dtype=np.uint8),None,np.full((20,20,3),150,dtype=np.uint8)])
    camera=SimpleNamespace(is_open=True,capture_full=lambda:next(frames))
    service=CameraService.__new__(CameraService);service._camera=camera;service._camera_lock=threading.Lock()
    monkeypatch.setattr('artifact.utils.capture_quality.evaluate',lambda f:{'faces':1,'score':float(f[0,0,0]),'clipped':0})
    data=service.capture_best_jpeg()
    assert np.asarray(Image.open(io.BytesIO(data)))[0,0,0]>140
    assert service.last_capture_quality['selected']==2
