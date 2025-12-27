"""Artistic portrait generation service using Gemini/Imagen.

Generates stylized artistic portraits based on user photos.
Images are displayed in FULL COLOR on the LED matrix,
then converted to B&W only when printing on thermal paper.

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
# FULL COLOR for LED display (square aspect ratio)
# Will be converted to B&W only when printing on thermal paper
# TEXT RULES: Russian language, ALL CAPS, VERY LARGE readable
# NO example labels - model copies them literally
# VARIETY: Each prompt has multiple variations to avoid repetition
# =============================================================================

# ROAST VARIATIONS - Adult humor with real bite (18+) - NOW IN COLOR
ROAST_VARIATIONS = [
    """NEON COMEDY ROAST PORTRAIT. Draw this person being hilariously roasted:
- EXAGGERATE what makes them unique: forehead, eyebrows, cheekbones, lips, ears, jawline, hairline
- NOT just the nose! Pick 2-3 features that are ACTUALLY distinctive about THIS person
- Add 3-4 arrows with SAVAGE but FUNNY labels in RUSSIAN
- NEON COLORS: hot pink, electric blue, toxic green arrows and labels
- Dark purple or black background with neon glow effects
- Graffiti street art style, bold and vibrant
- RUSSIAN text, ALL CAPS, chunky neon-outlined letters
Square aspect ratio. Vibrant colors, high contrast.""",

    """SAVAGE MEME LORD PORTRAIT. Draw this person getting ROASTED meme-style:
- Find their DISTINCTIVE features: chin, eye spacing, smile lines, hair, face shape
- Exaggerate 2-3 unique features BESIDES the nose
- 3-4 arrows with SAVAGE Russian labels like standup comedy roasts
- BOLD COLORS: fire orange, electric yellow, hot magenta
- Deep blue or purple gradient background
- Comic book pop art style with halftone dots
- RUSSIAN labels, ALL CAPS, bold comic font style
Square aspect ratio. Colorful and punchy.""",

    """DRUNK ARTIST ROAST. Someone drew this person at 2am being brutally honest:
- CARICATURE their real features: ears, eyebrows, chin, forehead
- Pick what's ACTUALLY distinctive about THIS person
- Drunk friend energy with arrows and labels in RUSSIAN
- WATERCOLOR SPLASH STYLE: messy color bleeds, artistic chaos
- Warm colors (coral, amber, crimson) with teal accents
- Labels in wobbly hand-drawn style
- RUSSIAN text, ALL CAPS, sketchy letters
Square aspect ratio. Artistic and colorful chaos.""",

    """CYBER ROAST PORTRAIT. Futuristic roast of this person:
- EXAGGERATE their unique facial geometry: asymmetry, proportions, expression
- What would a brutal AI notice first? Draw THAT exaggerated
- 3-4 holographic arrows with NO MERCY labels in RUSSIAN
- CYBERPUNK PALETTE: cyan, magenta, yellow on dark grid background
- Digital glitch effects, scan lines, data corruption aesthetic
- RUSSIAN text, ALL CAPS, pixelated or glitched font style
Square aspect ratio. Neon cyberpunk vibes.""",
]

# TAROT VARIATIONS - Evocative concepts, let the AI interpret artistically
TAROT_VARIATIONS = [
    """Transform this person into THE STAR archetype - hope, renewal, cosmic connection.
Art Nouveau meets celestial illustration. Luminous. Serene. Infinite possibility.
Think Alphonse Mucha painting the night sky. Starlight emanating from within.
Natural beauty, no exaggeration. Rich jewel tones. Square aspect ratio.""",

    """Transform this person into THE MAGICIAN archetype - manifestation, willpower, mastery.
Renaissance mysticism meets modern occult aesthetic. Commanding presence.
"As above, so below" energy. Alchemical transformation. Power radiating outward.
Natural proportions, dignified. Rich purples and golds. Square aspect ratio.""",

    """Transform this person into THE EMPRESS archetype - abundance, fertility, nurturing power.
Pre-Raphaelite sensuality meets Art Nouveau nature goddess.
Surrounded by life, creation, beauty. Maternal cosmic energy.
Lush, verdant, sensual but not explicit. Earth tones and greens. Square aspect ratio.""",

    """Transform this person into THE EMPEROR archetype - authority, structure, power.
Byzantine iconography meets royal portraiture. Stern but just.
Mountain-solid stability. Leadership without tyranny. Ancient wisdom.
Noble bearing, natural proportions. Crimson and gold. Square aspect ratio.""",

    """Transform this person into THE FOOL archetype - new beginnings, innocence, leap of faith.
Whimsical illustration meets spiritual journey. Joy without naivety.
Standing at the edge of everything possible. Fearless adventure.
Youthful energy, bright and hopeful. Sunny colors. Square aspect ratio.""",

    """Transform this person into THE HIGH PRIESTESS archetype - intuition, mystery, hidden knowledge.
Symbolist painting meets lunar mysticism. What she knows, she doesn't tell.
Keeper of secrets between worlds. Serene knowing. Veiled truths.
Enigmatic beauty. Midnight blues and silvers. Square aspect ratio.""",
]

# PROPHET VARIATIONS - Evocative mystic concepts, let AI interpret
PROPHET_VARIATIONS = [
    """Transform this person into a COSMIC ORACLE - one who reads fate in the stars.
Hubble telescope photography meets Russian icon painting. Infinite depth.
They contain galaxies. Nebulae bloom in their presence. Ancient beyond time.
Serene transcendence. Deep space colors with golden divine light. Square aspect ratio.""",

    """Transform this person into a LUNAR ORACLE - keeper of night wisdom.
Art Deco elegance meets celestial mysticism. Silver light illuminates truth.
The moon speaks through them. Tide-like intuition. Dreams made visible.
Ethereal beauty, silver and midnight blue. Square aspect ratio.""",

    """Transform this person into a CRYSTAL SEER - gazer into other realms.
Victorian spiritualism meets psychedelic visions. Refracted light reveals futures.
Reality bends around them. What the crystal shows, only they can interpret.
Mystical intensity, prismatic colors, focused power. Square aspect ratio.""",

    """Transform this person into a FIRE PROPHET - bearer of transformative visions.
Phoenix mythology meets Zoroastrian flame worship. Destruction births creation.
They burn but are not consumed. Truth spoken through flames.
Fierce passionate energy, ember reds and phoenix golds. Square aspect ratio.""",

    """Transform this person into a MYSTIC FORTUNE TELLER - reader of hidden fates.
Romani mysticism meets Belle Époque Parisian occultism. Intimate secrets revealed.
Cards speak, tea leaves whisper, palms tell stories only they can read.
Candlelit intimacy, velvet purples and antique gold. Square aspect ratio.""",
]

STYLE_PROMPTS = {
    # =========================================================================
    # GUESS MODE - "Кто Я?" - Detective investigation board
    # =========================================================================
    CaricatureStyle.GUESS: """Transform this person into a MYSTERY to be solved.
True crime podcast aesthetic meets noir detective fiction. Red string conspiracy board energy.
Who are they really? What secrets hide behind those eyes? The investigation begins.
Polaroid snapshots, evidence markers, magnifying glasses, question marks floating.
Film noir lighting, amber and shadow, forensic blue accents. Square aspect ratio.""",

    # =========================================================================
    # MEDICAL MODE - "Диагноз" - X-ray scan diagnostic
    # =========================================================================
    CaricatureStyle.MEDICAL: """Transform this person into a HUMOROUS MEDICAL SCAN.
Vintage medical illustration meets cyberpunk biometrics. What makes them tick?
Their brain: gears? chaos? coffee? Their heart: fire? ice? butterflies?
Playful diagnostic overlay revealing funny truths about their inner workings.
X-ray cyan and lime greens, medical scan aesthetic. RUSSIAN diagnostic labels.
Square aspect ratio.""",

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
    CaricatureStyle.QUIZ_WINNER: """Transform this person into a GAME SHOW CHAMPION moment!
Who Wants to Be a Millionaire meets anime victory pose. Pure triumph energy.
Confetti explosion, spotlight glory, champion's aura radiating.
They just proved they're the smartest person in the room. Celebrate it!
Golden victory light, celebratory colors, sparkle effects. Square aspect ratio.""",

    # =========================================================================
    # MYSTICAL & FORTUNE - Classic fortune teller aesthetics
    # =========================================================================
    CaricatureStyle.MYSTICAL: """Transform this person into a CRYSTAL BALL VISION.
Art Nouveau mystic illustration meets ethereal photography.
They appear within swirling cosmic mists, fate crystallizing around them.
The boundary between seer and seen dissolves.
Iridescent purples, mystic blues, crystal refractions. Square aspect ratio.""",

    CaricatureStyle.FORTUNE: """Transform this person into a VINTAGE FORTUNE MACHINE portrait.
Zoltar meets Art Deco carnival poster. Old world mysticism in ornate frame.
They ARE the fortune telling machine come to life.
Antique brass and copper tones, carnival atmosphere. Square aspect ratio.""",

    CaricatureStyle.SKETCH: """Transform this person into elegant PORTRAIT ART.
Egon Schiele's expressiveness meets modern fashion illustration.
Bold confident lines that capture essence, not just likeness.
Artistic minimalism with maximum impact.
Rich earth tones and sophisticated palette. Square aspect ratio.""",

    CaricatureStyle.CARTOON: """Transform this person into playful CARTOON ENERGY.
Pixar character design meets anime expressiveness. Fun exaggeration.
Capture their personality in bigger-than-life form.
Joyful, friendly, inviting. Not mean, just playful.
Bright saturated colors, dynamic pose. Square aspect ratio.""",

    CaricatureStyle.VINTAGE: """Transform this person into a VINTAGE CIRCUS POSTER star.
P.T. Barnum era showmanship meets Art Nouveau elegance.
They are the main attraction, the star of the show!
Victorian theatrical drama with decorative flourishes.
Aged warm tones, gold accents, theatrical flair. Square aspect ratio.""",

    # =========================================================================
    # ZODIAC MODE - "Гороскоп" - Constellation portrait
    # =========================================================================
    CaricatureStyle.ZODIAC: """Transform this person into a LIVING CONSTELLATION.
NASA deep space imagery meets classical star chart illustration.
Their essence mapped in starlight, face emerging from cosmic dust.
They are written in the stars, their destiny spelled in celestial bodies.
Deep space blues, stellar golds, nebula purples. Square aspect ratio.""",

    # =========================================================================
    # ROULETTE MODE - "Рулетка" - Casino winner style
    # =========================================================================
    CaricatureStyle.ROULETTE: """Transform this person into a CASINO ROYALE winner moment!
James Bond glamour meets Las Vegas jackpot energy.
Fortune favors the bold, and tonight fortune favors THEM.
Chips flying, dice tumbling, lady luck herself smiling.
Gold and emerald casino colors, dramatic spotlight. Square aspect ratio.""",
}

NEGATIVE_PROMPT = """
photorealistic photograph, 3D render, low quality, blurry,
unflattering, ugly, scary, disturbing, offensive,
pixel art, 8-bit, retro game graphics, blocky pixels
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
PERSONALITY INSIGHT (use to inform the artwork's expression and energy):
{personality_context}

Express their personality through the art - confident people get powerful poses,
introverts get serene expressions, risk-takers get dynamic energy, etc.
"""

            prompt = f"""Create an artistic portrait OF THIS EXACT PERSON from the reference photo.

CRITICAL REQUIREMENTS:
- This must capture THE PERSON IN THE PHOTO - their likeness is essential
- Recognize their distinctive features and incorporate them naturally
- FULL COLOR - rich, vibrant, artistic colors
- High quality artistic illustration, NOT pixel art, NOT photorealistic
{personality_hint}
{style_prompt}

The result should be recognizable as THIS specific person, transformed artistically.
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
                style="Artistic illustration, rich colors, high quality, professional art",
            )

            if image_data:
                # Keep image in COLOR for display - B&W conversion happens only when printing
                processed = await self._process_for_display(image_data, size)
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

    async def _process_for_display(
        self,
        image_data: bytes,
        target_size: Tuple[int, int],
    ) -> bytes:
        """Process the generated image for LED display (keep colors).

        Resizes while maintaining aspect ratio. Colors are preserved.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions

        Returns:
            Processed image bytes (full color)
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(image_data))

            # Ensure RGB mode (keep colors!)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Save to bytes - keep as color PNG
            output = BytesIO()
            img.save(output, format="PNG", optimize=True)
            return output.getvalue()

        except ImportError:
            logger.warning("PIL not available, returning original image")
            return image_data
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            return image_data

    async def _process_for_printer(
        self,
        image_data: bytes,
        target_size: Tuple[int, int],
    ) -> bytes:
        """Process the generated image for thermal printer output.

        Converts to high-contrast black and white, resizes for printer.
        Call this only when actually printing, not for display.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions

        Returns:
            Processed image bytes (B&W for thermal printer)
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
