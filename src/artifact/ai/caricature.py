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
# VARIETY: Each prompt has multiple variations to avoid repetition
# =============================================================================

# ROAST VARIATIONS - Adult humor with real bite (18+)
ROAST_VARIATIONS = [
    """BRUTAL COMEDY CLUB ROAST DOODLE. Draw this person as a CARICATURE being roasted:
- EXAGGERATE what makes them unique: forehead size, eyebrow shape, cheekbones, lip fullness, ear size, jawline, hairline
- NOT just the nose! Look at EVERYTHING and pick 2-3 features to roast
- Add 3-4 arrows pointing to features with BRUTAL but FUNNY labels in RUSSIAN
- Labels should be ADULT HUMOR - sarcastic, edgy, like a drunk friend roasting you
- Think comedy roast, not kindergarten insults
- Scribbled graffiti style, messy but readable
- RUSSIAN text, ALL CAPS, thick chunky letters
Black and white only, white background.""",

    """SAVAGE STANDUP COMEDIAN SKETCH. Draw this person getting ROASTED:
- Find their DISTINCTIVE features: chin shape, eye spacing, smile lines, hair texture, face shape
- Exaggerate 2-3 unique features BESIDES the nose
- 3-4 arrows with SAVAGE Russian labels - adult standup comedian level humor
- Like a friend who knows you too well and has no filter
- Messy doodle style with stink lines, flames, or shame spirals
- RUSSIAN labels, ALL CAPS, graffiti letters
Black and white only, white background.""",

    """BAR NAPKIN ROAST DRAWING. Someone drew this person at 2am being brutally honest:
- CARICATURE their real features: maybe it's their ears, their eyebrows, their chin, their forehead
- Pick what's ACTUALLY distinctive about THIS person, not default long nose
- Drunk friend energy with arrows and labels in RUSSIAN
- Labels are ADULT - could include mild swears, body humor, lifestyle roasts
- Scribbly, messy, but the insults are READABLE
- RUSSIAN text, ALL CAPS, wobbly drunk handwriting style
Black and white only, white background.""",

    """LOCKER ROOM ROAST DOODLE. The kind of drawing your worst friend would make:
- EXAGGERATE their unique facial geometry: asymmetry, proportions, expression lines
- What would a brutal but loving friend notice first? Draw THAT big
- 3-4 arrows with NO MERCY labels in RUSSIAN
- Adult humor - nothing is off limits except actually mean stuff
- Graffiti vandalism style, chaotic but clear
- RUSSIAN text, ALL CAPS, thick scribbled letters
Black and white only, white background.""",
]

# TAROT VARIATIONS - No more constant third eye
TAROT_VARIATIONS = [
    """TAROT CARD: THE STAR. Draw this person as the Star card archetype:
- Ornate art nouveau FRAME around the image
- Person kneeling, pouring water from two vessels (stars reflected in water)
- 8-pointed star above their head, smaller stars scattered around
- Nude or draped figure (tasteful), serene expression
- Nature elements: tree, bird, flowing water
- NATURAL proportions, beautiful and ethereal
- Thick black lines, white background, high contrast""",

    """TAROT CARD: THE MAGICIAN. Draw this person as the Magician archetype:
- Decorative BORDER with infinity symbol at top
- Person with one arm raised to sky, one pointing to earth
- Table before them with cup, sword, pentacle, wand symbols
- Roses and lilies around the frame
- Confident, powerful pose - they command the elements
- NATURAL proportions, regal bearing
- Thick black lines, white background, high contrast""",

    """TAROT CARD: THE EMPRESS. Draw this person as the Empress archetype:
- Luxurious ornate FRAME with wheat and pomegranate motifs
- Person seated on throne/cushions in flowing robes
- Crown of 12 stars, Venus symbol nearby
- Lush garden or nature surrounding them
- Nurturing, abundant, sensual energy
- NATURAL proportions, beautiful and powerful
- Thick black lines, white background, high contrast""",

    """TAROT CARD: THE EMPEROR. Draw this person as the Emperor archetype:
- Strong geometric FRAME with ram heads at corners
- Person seated on stone throne, armor or royal robes
- Ankh scepter in one hand, orb in other
- Mountains in background, red/orange energy (shown as bold lines)
- Authority, stability, leadership pose
- NATURAL proportions, commanding presence
- Thick black lines, white background, high contrast""",

    """TAROT CARD: THE FOOL. Draw this person as the Fool archetype:
- Whimsical FRAME with floral motifs
- Person mid-step at cliff edge, looking up carefree
- Small dog at their heels, bindle/bag over shoulder
- Sun shining, white rose in hand
- Joyful, innocent, adventurous expression
- NATURAL proportions, youthful energy
- Thick black lines, white background, high contrast""",

    """TAROT CARD: THE HIGH PRIESTESS. Draw this person as the Priestess:
- Mysterious FRAME with moon phases
- Person seated between two pillars (B and J letters)
- Crescent moon at feet, scroll or book in lap
- Pomegranate veil behind them, water below
- Wise, intuitive, mysterious gaze
- NATURAL proportions, serene and knowing
- Thick black lines, white background, high contrast""",
]

# PROPHET VARIATIONS - Not always third eye
PROPHET_VARIATIONS = [
    """MYSTIC ORACLE PORTRAIT - COSMIC SEER:
- Draw this person with NATURAL beautiful proportions
- Radiating halo of light rays behind their head
- Eyes slightly glowing with inner wisdom
- Floating constellation dots and star patterns around them
- Cosmic swirls and nebula shapes in background
- Wise, knowing expression - they see your future
- NO third eye, focus on the cosmic elements
- Thick black lines, white background, high contrast""",

    """MYSTIC ORACLE PORTRAIT - MOON PROPHET:
- Draw this person with NATURAL beautiful proportions
- Large crescent moon cradling their head from behind
- Stars scattered in their hair like a crown
- Moth or owl symbol near them (wisdom messenger)
- Flowing ethereal hair or robes
- Calm, all-knowing gaze
- Moon phases arranged around the portrait
- Thick black lines, white background, high contrast""",

    """MYSTIC ORACLE PORTRAIT - CRYSTAL GAZER:
- Draw this person with NATURAL beautiful proportions
- Hands raised, holding or hovering over crystal ball
- Light emanating from the crystal upward to their face
- Mystical smoke or mist swirling around
- Geometric sacred symbols floating nearby
- Deep concentrated expression
- NO third eye, the crystal is the focus
- Thick black lines, white background, high contrast""",

    """MYSTIC ORACLE PORTRAIT - FIRE ORACLE:
- Draw this person with NATURAL beautiful proportions
- Flames in their hands or rising behind them
- Phoenix feathers or fire bird silhouette
- Sparks and embers floating upward
- Intense, passionate prophet energy
- Hair flowing upward like flames
- Powerful and transformative vibe
- Thick black lines, white background, high contrast""",

    """MYSTIC ORACLE PORTRAIT - TAROT READER:
- Draw this person with NATURAL beautiful proportions
- Holding fanned tarot cards in elegant pose
- Cards floating around them showing mystical symbols
- Candles or mystical light sources
- Velvet draping or mystical cloth elements
- Knowing smile, they've seen your cards
- NO third eye, cards are the magical element
- Thick black lines, white background, high contrast""",
]

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
    # ROAST MODE - "Прожарка" - Adult roast doodle (uses ROAST_VARIATIONS)
    # =========================================================================
    CaricatureStyle.ROAST: "ROAST_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # PROPHET MODE - "ИИ Пророк" - Mystical oracle (uses PROPHET_VARIATIONS)
    # =========================================================================
    CaricatureStyle.PROPHET: "PROPHET_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # TAROT MODE - "Гадалка" - Tarot card (uses TAROT_VARIATIONS)
    # =========================================================================
    CaricatureStyle.TAROT: "TAROT_VARIATION",  # Will be replaced with random variation

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

            # Build the caricature prompt - resolve variation placeholders
            style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CaricatureStyle.SKETCH])

            # Replace placeholders with random variations for more variety
            if style_prompt == "ROAST_VARIATION":
                style_prompt = random.choice(ROAST_VARIATIONS)
            elif style_prompt == "PROPHET_VARIATION":
                style_prompt = random.choice(PROPHET_VARIATIONS)
            elif style_prompt == "TAROT_VARIATION":
                style_prompt = random.choice(TAROT_VARIATIONS)

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

    async def generate_multiple_caricatures(
        self,
        reference_photo: bytes,
        style: CaricatureStyle = CaricatureStyle.MYSTICAL,
        count: int = 3,
        size: Tuple[int, int] = (384, 384),
        personality_context: Optional[str] = None,
    ) -> List[Caricature]:
        """Generate multiple caricatures with different variations.

        Useful for creating sequences to display or letting user choose.

        Args:
            reference_photo: User's photo as bytes
            style: Caricature style to use
            count: Number of images to generate (1-5)
            size: Output size (width, height)
            personality_context: Optional personality traits

        Returns:
            List of Caricature objects (may have fewer than requested on errors)
        """
        count = max(1, min(5, count))  # Clamp to 1-5

        # Generate concurrently for speed
        tasks = [
            self.generate_caricature(
                reference_photo=reference_photo,
                style=style,
                size=size,
                personality_context=personality_context,
            )
            for _ in range(count)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        caricatures = []
        for result in results:
            if isinstance(result, Caricature):
                caricatures.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"One caricature failed: {result}")

        return caricatures

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
