from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import pytest
from artifact.modes.club_theme_schedule import scheduled_theme
from artifact.modes.manager import ModeManager, ManagerState
from artifact.modes.photobooth import get_configured_photobooth_modes
from artifact.modes.photobooth_themes import get_current_theme

@pytest.mark.parametrize('time,target',[
 ('2026-09-17T23:00:00+03:00','vse-svoi'),
 ('2026-09-18T06:59:59+03:00','vse-svoi'),
 ('2026-09-18T07:00:00+03:00','project-x'),
 ('2026-09-19T04:00:00+03:00','project-x'),
 ('2026-09-20T06:59:59+03:00','project-x'),
 ('2026-09-20T07:00:00+03:00','vse-svoi'),
 ('2026-09-25T23:00:00+03:00','vse-svoi')])
def test_dates_and_power_on(time,target,monkeypatch):
 monkeypatch.setenv('ARTIFACT_CLUB_THEME_SCHEDULE','project-x-2026')
 now=datetime.fromisoformat(time)
 assert scheduled_theme(now)==target
 assert scheduled_theme(now.astimezone(timezone.utc))==target
 monkeypatch.setattr('artifact.modes.club_theme_schedule.scheduled_theme',lambda:target)
 monkeypatch.setenv('PHOTOBOOTH_THEME','tropical-thai')
 monkeypatch.setenv('PHOTOBOOTH_MENU_MODES','brainrot,wedding')
 assert get_current_theme().id==target
 assert [m.theme_id_override for m in get_configured_photobooth_modes()]==[target]

@pytest.mark.parametrize('state,busy,expected',[
 (ManagerState.MODE_ACTIVE,False,False),
 (ManagerState.MODE_SELECT,True,False),
 (ManagerState.MODE_SELECT,False,True),
 (ManagerState.IDLE,False,True)])
def test_live_change_waits_for_safe_state(state,busy,expected,monkeypatch):
 monkeypatch.setattr('artifact.modes.club_theme_schedule.scheduled_theme',lambda:'project-x')
 manager=ModeManager.__new__(ModeManager)
 manager._state=state;manager._current_mode=object() if busy else None
 manager._prize_drum_active=False;manager._spiderverse_quest_active=False
 manager._registered_modes={};manager._use_pygame_menu=True;manager._menu=object()
 changes=[];manager.register_mode=lambda mode:changes.append(mode)
 manager._idle_animation=SimpleNamespace(reset=lambda:None)
 manager._sync_club_theme_schedule()
 assert bool(changes)==expected
 if expected:assert manager._menu is None
