import time
import threading
from artifact.utils.countdown_capture import CountdownCapture


def test_ready_candidate_does_not_wait_for_slow_next_frame():
    release=threading.Event()
    def fake(**kwargs):
        kwargs['on_candidate'](b'first-good-frame')
        release.wait(1)
        return b'better-frame'
    capture=CountdownCapture(fake);capture.start()
    deadline=time.monotonic()+1
    while capture.snapshot() is None and time.monotonic()<deadline:time.sleep(.001)
    start=time.monotonic()
    assert capture.snapshot()==b'first-good-frame'
    assert time.monotonic()-start<.02
    assert not capture.finished.is_set()
    capture.stop.set();release.set()
    assert capture.finished.wait(1)


def test_session_isolation_and_failure():
    a=CountdownCapture(lambda **kw:b'old-session');a.start();assert a.finished.wait(1)
    b=CountdownCapture(lambda **kw:None);b.start();assert b.finished.wait(1)
    assert b.snapshot() is None
    assert a.snapshot()==b'old-session'
