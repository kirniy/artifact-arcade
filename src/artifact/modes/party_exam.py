"""Private student portrait + durable offline-issued document; KP7 quest profile."""
import json
import logging
import os
from pathlib import Path
from artifact.modes.spiderverse_quest import SpiderverseQuestMode, QuestScreen
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text
from artifact.ai.client import get_gemini_client
from artifact.utils.party_exam_offline import OfflineCards, local_portrait

logger = logging.getLogger(__name__)
PORTRAIT_PROMPT = '''Make a clean student ID portrait of the single real person in the reference photo.
Preserve their exact identity, face geometry, age, hair, glasses and distinguishing features.
Front-facing head and shoulders, eyes toward camera, relaxed neutral expression. No beauty filter.
Elegant light monochrome ink-and-pencil editorial illustration, realistic likeness, restrained linework,
very sparse pale grey shading, clean contours. Pure solid white background (#FFFFFF), white margins.
No heavy black clothing fills, no dark backdrop, no hatch texture or decorative marks.
One portrait only. No text, frame, badge, logo, props or extra people. Crop ratio 3:4.
This will be printed on a thermal student document: keep it bright, airy and exceptionally recognizable.'''


class PartyExamMode(SpiderverseQuestMode):
    name = 'party_exam'
    display_name = 'PARTY\nEXAM'
    description = 'VNVNC UNIVERSITY'
    theme_id_override = None
    ai_style_key_override = 'party_exam'

    def __init__(self, context):
        self._student = None
        super().__init__(context)
        self._ai_enabled = True
        self._camera2_ai_enabled = True

    def _reset_to_quest_ready(self):
        self._student = None
        self._print_error = False
        self._printed = False
        super()._reset_to_quest_ready()

    @staticmethod
    def _private_root():
        return Path(os.environ.get('PARTY_EXAM_PRIVATE_DIR', str(Path.home()/'.local/share/artifact/party-exam')))

    @staticmethod
    def _save_private(path, data):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = path.with_suffix(path.suffix + '.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def on_enter(self):
        super().on_enter()
        # A power/network interruption preserves the original issue ID and photo.
        # Recover visibly; an operator press confirms any ambiguous physical reprint.
        import time
        root = self._private_root()
        if not root.exists():
            return
        candidates = sorted(root.glob('*/source.jpg'), key=lambda p:p.stat().st_mtime, reverse=True)
        for source in candidates:
            folder = source.parent
            if ((folder/'printed').exists() or (folder/'abandoned').exists()
                    or time.time() - source.stat().st_mtime > 8*3600):
                continue
            try:
                import re
                if not re.fullmatch(r'[a-f0-9]{32}', folder.name):
                    continue
                self._quest_print_id = folder.name
                self._quest_screen = QuestScreen.PHOTO
                self._state.photo_bytes = source.read_bytes()
                if (folder/'portrait.png').exists():
                    self._state.ai_label_bytes = (folder/'portrait.png').read_bytes()
                    self._state.ai_display_frame = self._decode_photo_frame(self._crop_to_square(self._state.ai_label_bytes))
                if (folder/'student.json').exists():
                    self._student = json.loads((folder/'student.json').read_text())
                    if self._student.get('offline') and (folder/'portrait.png').exists():
                        store = OfflineCards(root)
                        store.restore(folder.name, self._student)
                        self._save_private(folder/'receipt-ready', b'final')
                        store.ready(folder.name, folder/'portrait.png')
                self._print_error = True
                self._state.show_result = True
                from artifact.modes.base import ModePhase
                self.change_phase(ModePhase.RESULT)
                return
            except (ValueError, OSError):
                logger.exception('Could not recover PARTY EXAM job')
                self._reset_to_quest_ready()

    def _retry_saved_job(self):
        import asyncio
        from artifact.modes.base import ModePhase
        self._state.show_result = False
        self._state.is_generating = True
        self._print_error = False
        self._progress_tracker.reset()
        self._ai_task = asyncio.create_task(self._generate_photobooth_grid())
        self.change_phase(ModePhase.PROCESSING)

    async def _generate_photobooth_grid(self):
        import asyncio
        from io import BytesIO
        from PIL import Image

        root = self._private_root()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        issue = root/self._quest_print_id
        issue.mkdir(exist_ok=True, mode=0o700)
        source_path = issue/'source.jpg'
        if not source_path.exists():
            if not self._state.photo_bytes:
                return None
            self._save_private(source_path, self._state.photo_bytes)
        source = source_path.read_bytes()

        # Reserve the number and signed claim link locally before any network
        # call. Recovery and every reprint use these exact same identifiers.
        store = OfflineCards(root)
        saved_card = issue/'student.json'
        if saved_card.exists():
            self._student = json.loads(saved_card.read_text())
            if self._student.get('offline'):
                store.restore(self._quest_print_id, self._student)
        else:
            self._student = store.reserve(self._quest_print_id, issued_at=source_path.stat().st_mtime)
            self._save_private(saved_card, json.dumps(self._student, ensure_ascii=False).encode())

        if (issue/'portrait.png').exists():
            picture = (issue/'portrait.png').read_bytes()
        else:
            picture = await asyncio.to_thread(local_portrait, source)
            # A power loss during AI still leaves a printable real portrait.
            self._save_private(issue/'portrait.png', picture)
            try:
                budget = max(1.0, min(20.0, float(os.getenv('PARTY_EXAM_AI_TIMEOUT_SECONDS', '12'))))
                generated = await asyncio.wait_for(get_gemini_client().generate_image(
                    prompt=PORTRAIT_PROMPT, reference_photo=source, aspect_ratio='3:4'), timeout=budget)
                if generated:
                    with Image.open(BytesIO(generated)) as image:
                        image.verify()
                    picture = generated
            except Exception as exc:
                # A failed AI request must never prevent the personalized QR.
                logger.warning('PARTY EXAM uses local portrait (%s)', type(exc).__name__)
        # Bound the private API payload and thermal raster, independently of model output size.
        with Image.open(BytesIO(picture)) as portrait:
            portrait = portrait.convert('L')
            portrait.thumbnail((540, 720))
            encoded = BytesIO(); portrait.save(encoded, 'PNG', optimize=True)
            picture = encoded.getvalue()
        self._save_private(issue/'portrait.png', picture)
        if self._student.get('offline'):
            self._save_private(issue/'receipt-ready', b'final')
            store.ready(self._quest_print_id, issue/'portrait.png')
        # A separate systemd worker uploads later. No registration/network
        # request lies between this return and PRINT_START.
        return self._crop_to_square(picture), picture

    # All public-gallery paths are deliberately disabled for this profile.
    def _upload_ai_result_async(self):
        pass

    def _upload_raw_capture_async(self):
        pass

    def _upload_photo_async(self):
        pass

    def _start_printing_now(self):
        if not self._student or not self._state.ai_label_bytes:
            logger.error('PARTY EXAM document not issued; preserving private capture for recovery')
            return
        if self._state.is_printing or self._quest_receipt_queued:
            return
        self._state.is_printing = self._quest_receipt_queued = True
        self.context.event_bus.emit(Event(EventType.PRINT_START,data={
            'type':'photobooth','party_exam':True,'caricature':self._state.ai_label_bytes,
            'issue_id':self._quest_print_id,'print_required':True,**self._student},source=self.name))

    def on_input(self, event):
        if event.type in {EventType.PRINT_COMPLETE, EventType.PRINT_ERROR}:
            if event.data.get('issue_id') != self._quest_print_id:
                return False
            self._state.is_printing = False
            self._quest_receipt_queued = False
            self._print_error = event.type == EventType.PRINT_ERROR
            self._printed = event.type == EventType.PRINT_COMPLETE
            if self._printed:
                self._save_private(self._private_root()/self._quest_print_id/'printed', b'complete')
            return True
        if self._state.show_result:
            if event.type == EventType.KEYPAD_INPUT and str(event.data.get('key')) == '#':
                if self._quest_receipt_queued:
                    return True
                self._save_private(self._private_root()/self._quest_print_id/'abandoned', b'operator')
                self._reset_to_quest_ready()
                return True
            if event.type == EventType.BUTTON_PRESS:
                if not self._student or not self._state.ai_label_bytes:
                    self._retry_saved_job()
                elif self._print_error:
                    self._print_error = False
                    self._start_printing_now()
                elif not self._quest_receipt_queued:
                    self._reset_to_quest_ready()
            return True
        return super().on_input(event)

    def on_update(self, delta_ms):
        super().on_update(delta_ms)
        if (self._state.show_result and self._student and not self._printed
                and not self._print_error and not self._quest_receipt_queued):
            self._start_printing_now()

    def _complete_session(self):
        if self._print_error or (self._state.show_result and not self._printed):
            self._state.countdown_timer = 1.0
            return
        super()._complete_session()

    def render_main(self, buffer):
        if not self._state.show_result:
            super().render_main(buffer)
            if self._quest_screen == QuestScreen.READY:
                draw_centered_text(buffer, 'ОДИН ГОСТЬ', 96, (247,240,213), scale=1)
            return
        fill(buffer, (12,31,83))
        if not self._student:
            for y,text in ((17,'НЕ УДАЛОСЬ'),(34,'ВЫДАТЬ ЧЕК'),(62,'КНОПКА: ПОВТОР'),(93,'# НОВОЕ ФОТО')):
                draw_centered_text(buffer,text,y,(255,240,220),scale=1)
            return
        if self._state.ai_display_frame is not None:
            from PIL import Image
            import numpy as np
            frame = Image.fromarray(self._state.ai_display_frame).resize((80,80))
            buffer[5:85,24:104] = np.array(frame.convert('RGB'))
        draw_centered_text(buffer, str(self._student['student_number']),90,(255,255,255),scale=1)
        text = 'ЗАБЕРИ ЧЕК' if self._printed else 'ПЕЧАТАЮ ЧЕК'
        if self._print_error:
            text = 'ПРОВЕРЬ ПРИНТЕР'
        draw_centered_text(buffer,text,104,(255,240,220),scale=1)
        if self._print_error:
            draw_centered_text(buffer,'КНОПКА: ПОВТОР',116,(255,240,220),scale=1)

    def _render_quest_attract(self, buffer):
        fill(buffer,(12,31,83))
        draw_rect(buffer,3,3,122,122,(218,211,182),filled=False,thickness=1)
        draw_rect(buffer,6,6,116,116,(89,111,167),filled=False,thickness=1)
        draw_centered_text(buffer,'VNVNC',16,(247,240,213),scale=2)
        draw_centered_text(buffer,'UNIVERSITY',35,(247,240,213),scale=1)
        draw_line(buffer,18,48,110,48,(218,211,182))
        draw_centered_text(buffer,'PARTY',58,(255,255,255),scale=2)
        draw_centered_text(buffer,'EXAM',78,(255,255,255),scale=2)
        draw_centered_text(buffer,'НАЖМИ КНОПКУ',108,(247,240,213),scale=1)

    def render_ticker(self, buffer):
        from artifact.graphics.text_utils import render_idle_style_ticker_text
        fill(buffer, (0, 0, 0))
        render_idle_style_ticker_text(buffer,'VNVNC UNIVERSITY · PARTY EXAM',(120,160,255),self._time_in_mode)

    def get_lcd_text(self):
        return 'PARTY EXAM'
