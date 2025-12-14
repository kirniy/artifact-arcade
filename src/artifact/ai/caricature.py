"""Caricature generation service using Gemini/Imagen.

Generates stylized caricature portraits based on user photos,
optimized for thermal printer output (black and white, high contrast).

Based on patterns from nano-banana-pro with adaptations for
arcade fortune-telling use case.
"""

import logging
import asyncio
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from artifact.ai.client import get_gemini_client

logger = logging.getLogger(__name__)


class CaricatureStyle(Enum):
    """Available caricature styles."""

    MYSTICAL = "mystical"      # Crystal ball, stars, mystical elements
    FORTUNE = "fortune"        # Classic fortune teller style
    SKETCH = "sketch"          # Simple black and white sketch
    CARTOON = "cartoon"        # Exaggerated cartoon style
    VINTAGE = "vintage"        # Old-timey carnival style
    GUESS = "guess"            # Illustration with text annotations
    MEDICAL = "medical"        # X-ray/Dissection style
    ROAST = "roast"            # Mean doodle with arrows/labels
    PROPHET = "prophet"        # Mystical portrait (NOT caricature, no exaggeration)
    TAROT = "tarot"            # Tarot card style portrait
    QUIZ_WINNER = "quiz_winner"  # Victory celebration doodle for quiz winners
    ZODIAC = "zodiac"          # Constellation/zodiac sign portrait
    ROULETTE = "roulette"      # Casino/wheel winner style


@dataclass
class Caricature:
    """A generated caricature."""

    image_data: bytes
    style: CaricatureStyle
    width: int
    height: int
    format: str = "png"


# =============================================================================
# STYLE PROMPTS - Each VISUALLY DISTINCT for different modes
# Optimized for 128x128 pixel display + thermal printing
# TEXT RULES: Russian language, ALL CAPS, VERY LARGE readable
# NO example labels - model copies them literally
# =============================================================================

STYLE_PROMPTS = {
    # =========================================================================
    # GUESS MODE - "Кто Я?" - Detective investigation board
    # =========================================================================
    CaricatureStyle.GUESS: """
Create a DETECTIVE CASE FILE illustration OF THIS PERSON from the photo.

VISUAL CONCEPT - MYSTERY INVESTIGATION BOARD:
- The person's face drawn like a suspect sketch pinned to a detective board
- Red strings/lines connecting their face to floating question marks
- Magnifying glass icon examining a feature
- Fingerprint symbol somewhere on the board
- Scattered sticky notes with question marks (no readable text)
- Pushpins, evidence photos, mystery clues aesthetic
- The vibe: "WHO IS THIS PERSON? WHAT ARE THEY HIDING?"

DISPLAY (128x128 PIXELS):
- VERY THICK black outlines (3-4px minimum)
- Simple bold shapes only
- High contrast black/white

TEXT RULES: If any text, must be RUSSIAN, ALL CAPS, VERY LARGE.
Pure white background. Black and white only.
""",

    # =========================================================================
    # MEDICAL MODE - "Диагноз" - X-ray scan diagnostic
    # =========================================================================
    CaricatureStyle.MEDICAL: """
Create a HUMOROUS X-RAY SCAN illustration OF THIS PERSON from the photo.

VISUAL CONCEPT - FUNNY MEDICAL DIAGNOSTIC:
- Draw the person as seen through an X-ray/CT scan machine
- Their head shows "brain" with gears, cogs, hamster wheel, or chaos inside
- Chest area shows heart with funny symbols (fire, ice, butterflies, black hole)
- Add medical scan frame/border like real diagnostic display
- Include crosshairs, measurement grid lines, scan annotations
- Small icons of what's "diagnosed" inside them (coffee addiction, chaos, etc.)
- The vibe: "WHAT'S WRONG WITH THIS PATIENT?" humorous medical report

DISPLAY (128x128 PIXELS):
- VERY THICK black outlines (3-4px minimum)
- Internal organs as simple bold icons
- Scan grid overlay with thick lines
- High contrast like real X-ray negative

TEXT RULES: Any diagnostic labels MUST be RUSSIAN, ALL CAPS, VERY LARGE readable.
Pure white background. Black and white only.
""",

    # =========================================================================
    # ROAST MODE - "Прожарка" - Graffiti roast doodle
    # =========================================================================
    CaricatureStyle.ROAST: """
Create a GRAFFITI ROAST DOODLE of THIS PERSON from the photo.

VISUAL CONCEPT - SCHOOL DESK / BATHROOM WALL VANDALISM:
- Messy, chaotic, scribbly drawing like graffiti tags
- EXAGGERATE their features hilariously (giant nose, crazy hair, weird ears)
- Multiple arrows pointing at features with mean but funny roast labels
- Scribbled underlines, circles around "problem areas"
- Doodle flames, stink lines, or chaos symbols around them
- The vibe: a bored student roasting their friend with a pen

DISPLAY (128x128 PIXELS):
- VERY THICK scribbled outlines
- Messy but READABLE arrows and labels
- Keep it simple - bold scribbles only
- High contrast black/white

TEXT RULES (CRITICAL):
- ALL labels MUST be in RUSSIAN language
- ALL text MUST be in CAPITAL LETTERS
- Text must be VERY LARGE - readable at 128px
- Chunky graffiti-style scribbled letters
- 2-4 arrows with SHORT funny roast words

Pure white background. Black and white only.
""",

    # =========================================================================
    # PROPHET MODE - "ИИ Пророк" - Mystical oracle portrait
    # =========================================================================
    CaricatureStyle.PROPHET: """
Create a MYSTICAL PROPHET PORTRAIT of THIS PERSON from the photo.

VISUAL CONCEPT - ETHEREAL ORACLE/SEER:
- NOT a caricature - keep proportions NATURAL and beautiful
- Draw them as an all-knowing mystic seer
- Third eye symbol on forehead, glowing softly
- Radiating lines/halo around their head like divine light
- Floating stars, cosmic swirls, constellation dots around them
- Mysterious wise expression, slightly glowing eyes
- The vibe: an ancient prophet who sees past, present, and future

DISPLAY (128x128 PIXELS):
- VERY THICK bold black outlines
- Mystical elements bold and simple
- High contrast black/white

NO TEXT LABELS - pure mystical visual only.
Person should look beautiful, wise, powerful - NOT mocked.
Pure white background. Black and white only.
""",

    # =========================================================================
    # TAROT MODE - "Гадалка" - Tarot card illustration
    # =========================================================================
    CaricatureStyle.TAROT: """
Create a TAROT CARD illustration of THIS PERSON from the photo.

VISUAL CONCEPT - CLASSIC TAROT CARD:
- MUST have ornate decorative FRAME/BORDER around entire image
- Person posed like a tarot archetype (holding a star, magical gesture, regal pose)
- Art nouveau decorative corners and flourishes on the frame
- Mystical symbols: stars, crescent moon, all-seeing eye, zodiac glyph
- Sun rays or divine light behind the figure
- The person looks regal, powerful, magical - like a fortune card figure

DISPLAY (128x128 PIXELS):
- VERY THICK bold black outlines (3-4px)
- Decorative frame must be BOLD and simple
- Large shapes, no intricate fine details
- High contrast black/white

TEXT: If adding card name at bottom, MUST be RUSSIAN, ALL CAPS, VERY LARGE.
NOT a caricature - proportions NATURAL and flattering.
Pure white background. Black and white only.
""",

    # =========================================================================
    # QUIZ WINNER - "Викторина" - Game show champion
    # =========================================================================
    CaricatureStyle.QUIZ_WINNER: """
Create a GAME SHOW WINNER illustration of THIS PERSON from the photo.

VISUAL CONCEPT - TV QUIZ SHOW CHAMPION MOMENT:
- Person in triumphant WINNER POSE (arms up victory, fist pump, or holding trophy high)
- Dramatic spotlight rays radiating from behind them
- Big confetti pieces and stars scattered everywhere
- Simple trophy icon or champagne bottle nearby
- Sparkle/shine star burst effects
- Money bills or coins flying around (optional)
- The vibe: just won a million on TV, pure joy and triumph!

DISPLAY (128x128 PIXELS):
- VERY THICK bold black outlines
- Simple bold celebration shapes
- Large confetti pieces, thick light rays
- High contrast black/white

NO TEXT LABELS - pure visual celebration only.
Make them look like a CHAMPION, a GENIUS, a WINNER!
Pure white background. Black and white only.
""",

    # =========================================================================
    # UNUSED STYLES (kept for compatibility, improved anyway)
    # =========================================================================
    CaricatureStyle.MYSTICAL: """
Create a CRYSTAL BALL VISION of THIS PERSON from the photo.
The person's face appearing inside a fortune teller's crystal ball.
Swirling mist/smoke around the edges, mystical glow effect.
Stars and sparkles floating in the crystal.
VERY THICK bold black outlines. Simple bold shapes.
Pure white background. High contrast black/white only.
If any text: RUSSIAN, ALL CAPS, VERY LARGE.
""",

    CaricatureStyle.FORTUNE: """
Create a VINTAGE FORTUNE MACHINE portrait of THIS PERSON.
Style: Old carnival Zoltar machine aesthetic.
Decorative vintage frame with ornate corners.
Mystical symbols and stars around the portrait.
VERY THICK bold black outlines. Simple bold shapes.
Pure white background. High contrast black/white only.
If any text: RUSSIAN, ALL CAPS, VERY LARGE.
""",

    CaricatureStyle.SKETCH: """
Create a simple artistic PORTRAIT SKETCH of THIS PERSON.
Clean confident line drawing, minimal detail.
Capture their likeness with bold expressive strokes.
VERY THICK bold black outlines. Simple shapes.
Pure white background. High contrast black/white only.
""",

    CaricatureStyle.CARTOON: """
Create a FUN CARTOON CARICATURE of THIS PERSON.
Big head, exaggerated expressive features, comic book style.
Playful and friendly, not mean or ugly.
VERY THICK bold black outlines. Simple bold shapes.
Pure white background. High contrast black/white only.
""",

    CaricatureStyle.VINTAGE: """
Create a VINTAGE CIRCUS POSTER portrait of THIS PERSON.
Victorian sideshow poster aesthetic with decorative frame.
Dramatic presentation like announcing a circus act.
Bold decorative border with flourishes.
VERY THICK bold black outlines.
Pure white background. High contrast black/white only.
If any text: RUSSIAN, ALL CAPS, VERY LARGE.
""",

    # =========================================================================
    # ZODIAC MODE - "Гороскоп" - Constellation portrait
    # =========================================================================
    CaricatureStyle.ZODIAC: """
Create a CONSTELLATION/ZODIAC portrait of THIS PERSON from the photo.

VISUAL CONCEPT - PERSON AS A CONSTELLATION:
- Draw the person's portrait made of stars and constellation lines
- Connect facial features with dotted lines like star maps
- Add their zodiac symbol prominently (will be specified in context)
- Scattered stars and cosmic dust around them
- The face emerges from a starfield/night sky vibe
- Glowing celestial aura around the portrait

DISPLAY (128x128 PIXELS):
- VERY THICK bold black outlines
- Stars as bold dots, constellation lines clear
- Simple cosmic elements
- High contrast black/white

NO TEXT LABELS - pure celestial visual only.
Pure white background. Black and white only.
""",

    # =========================================================================
    # ROULETTE MODE - "Рулетка" - Casino winner style
    # =========================================================================
    CaricatureStyle.ROULETTE: """
Create a CASINO JACKPOT WINNER illustration of THIS PERSON from the photo.

VISUAL CONCEPT - WHEEL OF FORTUNE WINNER:
- Person with excited winning expression
- Surrounded by flying coins, chips, and money symbols
- Casino wheel or slot machine elements in background
- Stars and sparkles like hitting the jackpot
- The vibe: "I JUST WON BIG AT THE CASINO!"

DISPLAY (128x128 PIXELS):
- VERY THICK bold black outlines
- Simple bold casino symbols (coins, stars, sevens)
- Dramatic light rays behind them
- High contrast black/white

NO TEXT LABELS - pure visual celebration.
Pure white background. Black and white only.
""",
}

NEGATIVE_PROMPT = """
photorealistic, photograph, 3D render, grayscale gradients,
complex shading, detailed background, color, low contrast,
unflattering, ugly, scary, disturbing, offensive
"""


class CaricatureService:
    """Service for generating AI-powered caricatures."""

    def __init__(self):
        self._client = get_gemini_client()

    @property
    def is_available(self) -> bool:
        """Check if caricature service is available."""
        return self._client.is_available

    async def generate_caricature(
        self,
        reference_photo: bytes,
        style: CaricatureStyle = CaricatureStyle.MYSTICAL,
        size: Tuple[int, int] = (384, 384),
        personality_context: Optional[str] = None,
    ) -> Optional[Caricature]:
        """Generate a caricature based on a reference photo.

        Sends the photo directly to Gemini 3 Pro Image Preview which
        can generate styled images based on reference photos.

        Args:
            reference_photo: User's photo as bytes
            style: Caricature style to use
            size: Output size (width, height)
            personality_context: Optional personality traits from questions

        Returns:
            Caricature object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for caricature generation")
            return None

        try:
            import hashlib
            import random

            # Add a small uniqueness token to vary outputs run-to-run
            uniqueness_token = hashlib.md5(str(random.random()).encode()).hexdigest()[:8].upper()

            # Build the caricature prompt
            style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

            # Build personality-aware prompt
            personality_hint = ""
            if personality_context:
                personality_hint = f"""
PERSONALITY INSIGHT (use to inform the caricature's expression/vibe):
{personality_context}

Express their personality through the caricature - confident people get confident poses,
introverts get gentle expressions, risk-takers get dynamic poses, etc.
"""

            prompt = f"""Create a caricature portrait OF THIS EXACT PERSON from the reference photo.

CRITICAL REQUIREMENTS:
- This must be a caricature of THE PERSON IN THE PHOTO - capture their likeness
- Exaggerate their distinctive facial features (nose, eyes, chin, hair, etc.)
- THICK bold black outlines only
- Pure white background - no shading, no gradients, no gray
- Black and white only - suitable for thermal receipt printer
{personality_hint}
Style: {style_prompt}

The result should be recognizable as THIS specific person, but as a fun caricature.
UNIQUENESS TOKEN: {uniqueness_token}
"""

            # Send photo directly to Gemini 3 Pro Image Preview
            # The model understands to use the photo as reference
            image_data = await self._client.generate_image(
                prompt=prompt,
                reference_photo=reference_photo,
                photo_mime_type="image/jpeg",
                aspect_ratio="1:1",
                image_size="1K",  # Use 1K resolution
                style="Black and white sketch caricature, hand-drawn style, high contrast",
            )

            if image_data:
                # Process for thermal printer
                processed = await self._process_for_printer(image_data, size)
                return Caricature(
                    image_data=processed,
                    style=style,
                    width=size[0],
                    height=size[1],
                    format="png",
                )

        except Exception as e:
            logger.error(f"Caricature generation failed: {e}")

        return None

    def _build_caricature_prompt(self, description: str, style: CaricatureStyle) -> str:
        """Build the full prompt for caricature generation.

        Args:
            description: Description of the person's features
            style: Caricature style

        Returns:
            Complete prompt string
        """
        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

        return f"""Create a caricature portrait based on this description:
{description}

Style requirements:
{style_prompt}

Important: The caricature should be friendly, fun, and suitable for all ages.
Output should be optimized for thermal printer (pure black and white, high contrast).
"""

    async def _process_for_printer(
        self,
        image_data: bytes,
        target_size: Tuple[int, int],
    ) -> bytes:
        """Process the generated image for thermal printer output.

        Converts to high-contrast black and white, resizes for printer.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions

        Returns:
            Processed image bytes
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(image_data))

            # Convert to grayscale
            img = img.convert("L")

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Apply threshold for pure black and white
            threshold = 128
            img = img.point(lambda p: 255 if p > threshold else 0, mode="1")

            # Convert back to grayscale for compatibility
            img = img.convert("L")

            # Save to bytes
            output = BytesIO()
            img.save(output, format="PNG", optimize=True)
            return output.getvalue()

        except ImportError:
            logger.warning("PIL not available, returning original image")
            return image_data
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return image_data

    async def generate_simple_caricature(
        self,
        style: CaricatureStyle = CaricatureStyle.SKETCH,
    ) -> Optional[Caricature]:
        """Generate a generic caricature without a reference photo.

        Useful for testing or when camera is unavailable.

        Args:
            style: Caricature style

        Returns:
            Caricature object or None on error
        """
        if not self._client.is_available:
            return None

        style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

        prompt = f"""Create a caricature portrait of a friendly mystical fortune teller character with:
- Warm, welcoming expression
- Mysterious yet approachable eyes
- Slight knowing smile
- Perhaps a headscarf or mystical accessory

Style requirements:
{style_prompt}
"""

        try:
            image_data = await self._client.generate_image(
                prompt=prompt,
                aspect_ratio="1:1",
                image_size="1K",
                style="Black and white sketch caricature, hand-drawn style, high contrast",
            )

            if image_data:
                processed = await self._process_for_printer(image_data, (384, 384))
                return Caricature(
                    image_data=processed,
                    style=style,
                    width=384,
                    height=384,
                    format="png",
                )

        except Exception as e:
            logger.error(f"Simple caricature generation failed: {e}")

        return None

    async def generate_squid_sketch(
        self,
        reference_photo: bytes,
        eliminated: bool = False,
        size: Tuple[int, int] = (384, 384),
    ) -> Optional[bytes]:
        """Generate a Squid Game style sketch of the player (not a caricature).

        Args:
            reference_photo: Player photo bytes
            eliminated: Whether to add an eliminated vibe
            size: Target size for printing

        Returns:
            Processed PNG bytes ready for thermal printing, or None on failure
        """
        if not self._client.is_available:
            logger.warning("AI not available for Squid sketch")
            return None

        mood = "determined survivor energy, mid-run pose" if not eliminated else "eliminated, dramatic ink X across the portrait"

        import hashlib, random
        uniqueness_token = hashlib.md5(str(random.random()).encode()).hexdigest()[:8].upper()

        prompt = f"""Create a black-and-white hand-drawn sketch of THIS PERSON from the photo.
Style: Squid Game contestant in the teal tracksuit with a number patch. Face is clearly visible and recognizable.
NOT a caricature — keep proportions natural. Use thick black outlines only, pure white background, no shading or gray.
Mood: {mood}.
All text/patches on clothing or background must be RUSSIAN and ALL CAPS if any appear.
UNIQUENESS TOKEN: {uniqueness_token}
Make it look awesome on thermal receipt paper (high contrast, clean lines)."""

        try:
            image_data = await self._client.generate_image(
                prompt=prompt,
                reference_photo=reference_photo,
                photo_mime_type="image/jpeg",
                aspect_ratio="1:1",
                image_size="1K",
                style="Black and white thermal-printer sketch, Squid Game outfit, bold lines",
            )

            if image_data:
                return await self._process_for_printer(image_data, size)

        except Exception as e:
            logger.error(f"Squid sketch generation failed: {e}")

        return None
