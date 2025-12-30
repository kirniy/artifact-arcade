"""Artistic portrait generation service using Gemini/Imagen.

Generates stylized artistic portraits based on user photos.
All images are generated in BLACK AND WHITE to match the grayscale
camera input (NoIR camera has purple tint in color mode) and for
optimal thermal printer output.

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
    PHOTOBOOTH = "photobooth"  # Christmas 2x2 photo booth grid


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
# BLACK AND WHITE for both LED display and thermal printer
# (Camera captures grayscale to avoid NoIR purple tint)
# TEXT RULES: Russian language, ALL CAPS, VERY LARGE readable
# NO example labels - model copies them literally
# VARIETY: Each prompt has multiple variations to avoid repetition
# =============================================================================

# ROAST VARIATIONS - Adult humor with real bite (18+) - BLACK AND WHITE
ROAST_VARIATIONS = [
    """BLACK AND WHITE ROAST SKETCH. Draw this person being hilariously roasted:
- EXAGGERATE what makes them unique: forehead, eyebrows, cheekbones, lips, ears, jawline, hairline
- NOT just the nose! Pick 2-3 features that are ACTUALLY distinctive about THIS person
- Add 3-4 arrows with SAVAGE but FUNNY labels in RUSSIAN
- PURE BLACK AND WHITE - thick black lines on white background
- Hand-drawn sketch style, bold strokes, high contrast
- RUSSIAN text, ALL CAPS, chunky hand-drawn letters
Square aspect ratio. Black ink on white paper aesthetic.""",

    """SAVAGE NOTEBOOK DOODLE. Draw this person getting ROASTED like a mean high school drawing:
- Find their DISTINCTIVE features: chin, eye spacing, smile lines, hair, face shape
- Exaggerate 2-3 unique features BESIDES the nose
- 3-4 arrows with SAVAGE Russian labels like standup comedy roasts
- BLACK AND WHITE ONLY - pen on paper style
- Messy notebook margin doodle aesthetic
- RUSSIAN labels, ALL CAPS, scratchy handwriting
Square aspect ratio. Pure black ink, white background.""",

    """DRUNK ARTIST ROAST. Someone drew this person at 2am being brutally honest:
- CARICATURE their real features: ears, eyebrows, chin, forehead
- Pick what's ACTUALLY distinctive about THIS person
- Drunk friend energy with arrows and labels in RUSSIAN
- SKETCHY BLACK AND WHITE - wobbly lines, cross-hatching
- Labels in wobbly hand-drawn style
- RUSSIAN text, ALL CAPS, sketchy letters
Square aspect ratio. Black marker on napkin aesthetic.""",

    """COURTROOM SKETCH ROAST. Draw this person like a savage court artist:
- EXAGGERATE their unique facial geometry: asymmetry, proportions, expression
- What would a brutal observer notice first? Draw THAT exaggerated
- 3-4 arrows with NO MERCY labels in RUSSIAN
- BLACK AND WHITE charcoal/pencil sketch style
- Quick expressive strokes, dramatic shading
- RUSSIAN text, ALL CAPS, bold blocky letters
Square aspect ratio. Black and white courtroom drama.""",
]

# VNVNC 2026 STICKER VARIATIONS - Festive portrait stickers with Christmas vibes
TAROT_VARIATIONS = [
    """BLACK AND WHITE portrait STICKER of this person celebrating NEW YEAR!
Slight caricature - emphasize their festive joy.
Big decorative "VNVNC 2026" text prominently displayed in Christmas/holiday lettering style.
NOTE: Text must be exactly "VNVNC 2026" 
Snowflakes, party hats, champagne bubbles as decoration.
Sticker die-cut style with white border.
Fun celebration energy, holiday party vibes. Square aspect ratio.""",

    """BLACK AND WHITE NEW YEAR portrait STICKER!
Slight caricature - capture their party spirit.
Ornate Christmas-style "VNVNC 2026" as the main text element.
NOTE: Text must read "VNVNC 2026" exactly - the club/brand name plus year.
Confetti, stars, holiday decorations around the portrait.
Bold sticker outline, festive hand-lettered text.
Joyful celebration mood. Square aspect ratio.""",

    """BLACK AND WHITE festive STICKER portrait!
Slight caricature - bring out their cheerful features.
Decorative vintage Christmas lettering showing "VNVNC 2026" prominently.
NOTE: Include full text "VNVNC 2026" - not just the year!
Winter holiday motifs: snowflakes, bells, ribbons.
Classic sticker format with clean die-cut edge.
New Year's Eve party energy. Square aspect ratio.""",

    """BLACK AND WHITE NEW YEAR STICKER of this person!
Slight caricature - emphasize what makes them look happy.
Big bold "VNVNC 2026" in fancy holiday/Christmas font style.
NOTE: Text is "VNVNC 2026" - the brand name followed by the year.
Fireworks, sparkles, celebration elements.
Sticker aesthetic with thick outline border.
Champagne toast vibes, midnight countdown energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait STICKER - Happy New Year!
Slight caricature - capture their festive personality.
Ornamental "VNVNC 2026" text in decorative Christmas calligraphy.
NOTE: Write "VNVNC 2026" as the main branding element.
Holiday party decorations: balloons, streamers, snow.
Die-cut sticker style, bold graphic look.
New Year celebration, winter wonderland vibes. Square aspect ratio.""",

    """BLACK AND WHITE NEW YEAR celebration STICKER!
Slight caricature - play up their joyful expression.
Retro Christmas card style "VNVNC 2026" lettering.
NOTE: Include exact text "VNVNC 2026" - brand plus year together.
Vintage holiday illustrations: Santa hats, tinsel, ornaments.
Classic sticker format with decorative border.
Nostalgic holiday cheer, party time energy. Square aspect ratio.""",
]

# PROPHET VARIATIONS - Fun, stylish AI prophet portraits - NOT mystical
PROPHET_VARIATIONS = [
    """BLACK AND WHITE portrait of this person as a TECH VISIONARY.
Slight caricature - emphasize their distinctive facial features.
Steve Jobs keynote energy, confident genius, changing the world attitude.
Clean graphic style, bold lines, Silicon Valley prophet vibes.
Think Apple ad meets comic book hero. Square aspect ratio.""",

    """BLACK AND WHITE portrait of this person as a PUNK ORACLE.
Slight caricature - bring out what makes them unique.
Mohawk optional, safety pins and attitude. Knows the future, doesn't care.
DIY zine aesthetic, photocopied rebellion, underground wisdom.
Bold scratchy lines, raw energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait of this person as a JAZZ SAGE.
Slight caricature - capture their distinctive vibe.
Blue Note album cover energy, cool and knowing, improvised prophecy.
Smoky club atmosphere, sophisticated swagger, beatnik philosopher.
Ink wash style, moody shadows. Square aspect ratio.""",

    """BLACK AND WHITE portrait of this person as a COMIC BOOK ORACLE.
Slight caricature - play up what makes their face interesting.
Superhero origin story energy, dramatic panels, destiny awaits.
Bold comic book style, dynamic poses, dramatic lighting.
Thick inks, halftone dots, pow energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait of this person as a RETRO FUTURIST.
Slight caricature - emphasize their unique characteristics.
1960s space age optimism, ray guns and rocket ships, atomic age prophet.
Googie architecture vibes, optimistic tomorrow, stylized cool.
Clean vector style, retrofuture aesthetic. Square aspect ratio.""",
]

# PHOTOBOOTH VARIATIONS - Christmas 2x2 photo booth grid with VNVNC 2026
# NOTE: These prompts handle both single person AND groups - include ALL people from the photo!
PHOTOBOOTH_VARIATIONS = [
    """Create a FUN CHRISTMAS PHOTO BOOTH 2x2 GRID image!

IMPORTANT: Look at the reference photo carefully!
- If there is ONE person: show that person in 4 different playful poses
- If there are MULTIPLE people: show the WHOLE GROUP together in all 4 frames!
ALL people from the reference MUST appear in each frame!

LAYOUT: A 2x2 grid of 4 photo booth frames:
- Frame 1: Big smiles, looking happy together
- Frame 2: Silly faces, tongues out, funny expressions
- Frame 3: Peace signs, celebration poses, thumbs up
- Frame 4: Surprised / excited expressions, party energy

CRITICAL: Preserve EVERY person's likeness!
Each person's face, hair, and distinctive features must be recognizable in ALL 4 frames.

CHRISTMAS DECORATIONS: Festive frame with snowflakes, stars, holly, Christmas lights.
Colors: red, green, gold, silver, white - vibrant holiday energy!

BRANDING LAYOUT - 3D layered effect:
- "VNVNC" in LARGE letters BEHIND the people (partially obscured by them for 3D depth effect)
- "2026" displayed BELOW/UNDER the people at the bottom
This creates a cool 3D perspective where people appear in front of the VNVNC text!
Use festive Christmas-style lettering with snow caps for both texts.

High quality, joyful, professional photo booth aesthetic. Square aspect ratio.""",

    """CHRISTMAS PHOTO BOOTH STRIP - 2x2 grid of fun poses!

FIRST: Count how many people are in the reference photo.
- ONE person? Show them solo in 4 different poses
- TWO or MORE people? Include the ENTIRE GROUP in each frame!
Never leave anyone out!

Create a classic photo booth layout:
- 4 frames arranged in a 2x2 grid
- Each frame shows THE SAME PEOPLE from the reference photo
- Poses: happy, silly, excited, peace signs

ESSENTIAL: EVERY person in the reference must appear in ALL 4 frames!
Same faces, same hair, same clothing - just different expressions.

FESTIVE FRAME: Christmas decorations, sparkles, holly, candy canes.
BRIGHT COLORS: Red, green, gold holiday palette!

3D BRANDING EFFECT:
- Large "VNVNC" text positioned BEHIND the people (they partially cover it - creates depth!)
- "2026" text placed UNDERNEATH/BELOW the people
This layering creates a cool 3D pop-out effect where people appear in the foreground!
Festive holiday font with decorative elements.

Fun party atmosphere, professional photo booth quality. Square aspect ratio.""",

    """NEW YEAR PHOTO BOOTH GRID - 4 fun poses!

CHECK THE REFERENCE: How many people are there?
- Single person: 4 different solo poses
- Group photo: ALL people together in each of the 4 frames!

2x2 photo booth layout:
- Top left: Genuine smiles, looking happy
- Top right: Funny faces, playful expressions
- Bottom left: Victory poses, celebration
- Bottom right: Surprised, excited energy

CRITICAL REQUIREMENT: EVERYONE from the reference appears in ALL 4 frames!
Same facial features, hairstyles, and outfits - just different expressions.
Do NOT omit anyone from the group!

HOLIDAY DECORATIONS: Snowflakes, confetti, stars, Christmas lights border.
COLORS: Festive red, green, gold, silver.

LAYERED 3D BRANDING:
- "VNVNC" in BIG letters as BACKGROUND (behind the people, they stand in front)
- "2026" at the BOTTOM, below the people
Creates depth and dimension - people pop forward in front of VNVNC!
Christmas calligraphy style for both texts.

Joyful holiday photo booth energy! Square aspect ratio.""",
]

# GUESS VARIATIONS - Detective investigation board
GUESS_VARIATIONS = [
    """BLACK AND WHITE portrait as a MYSTERY CASE FILE.
Slight caricature - emphasize their distinctive facial features.
True crime documentary aesthetic, case file photo energy.
Polaroid snapshot with evidence markers, question marks, magnifying glass.
Film noir shadows, detective board conspiracy vibes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). High contrast black ink. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a DETECTIVE BOARD PHOTO.
Slight caricature - play up what makes them suspicious.
Newspaper clipping aesthetic, red string connections (in B&W).
Pushpins, sticky notes, question marks around the portrait.
Hard-boiled detective vibes, midnight investigation.
ALL TEXT AND LABELS IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as an FBI WANTED POSTER.
Slight caricature - emphasize memorable features.
Vintage typewriter text, official stamp marks, file number.
Document folder aesthetic, classified information vibes.
Noir thriller energy, mystery to be solved.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). High contrast. Square aspect ratio.""",
]

# MEDICAL VARIATIONS - X-ray scan diagnostic
MEDICAL_VARIATIONS = [
    """BLACK AND WHITE portrait as a HUMOROUS MEDICAL SCAN.
Slight caricature - play up their unique features.
Vintage anatomy illustration style, diagnostic overlay.
Their brain: gears? chaos? coffee? Their heart: fire? ice? butterflies?
Arrow labels pointing to funny observations.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Medical textbook woodcut style. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a PERSONALITY X-RAY.
Slight caricature - what's inside this person?
Transparent view showing their inner mechanisms.
Thought bubbles, dream clouds, fear zones, hope organs.
Anatomical diagram meets psychology chart.
ALL LABELS IN RUSSIAN, ALL CAPS (except VNVNC). High contrast. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a DIAGNOSTIC CHART.
Slight caricature - clinical observation aesthetic.
Hospital record vibe with vital signs and readings.
Charts showing: caffeine levels, overthinking index, kindness meter.
Medical illustration meets character profile.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Clean lines. Square aspect ratio.""",
]

# QUIZ WINNER VARIATIONS - Game show champion
QUIZ_WINNER_VARIATIONS = [
    """BLACK AND WHITE portrait as a GAME SHOW CHAMPION!
Slight caricature - emphasize what makes them look like a winner.
Triumphant pose, championship energy, they just won it all!
Confetti and trophy vibes, spotlight moment, victory celebration.
Bold comic book style, action lines, champion's glow.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). High contrast ink drawing. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a QUIZ MASTER.
Slight caricature - capture their victorious expression.
Gold medal energy, podium champion, brain power visualized.
Lightning bolts of knowledge, stars of success.
Retro game show aesthetic, 80s TV vibes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold lines. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a TRIVIA GENIUS.
Slight caricature - play up their smart features.
Graduation cap optional, encyclopedia knowledge radiating.
Light bulb moments, eureka energy, intellectual swagger.
Vintage academic illustration meets celebration poster.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",
]

# MYSTICAL VARIATIONS - Vintage magician style
MYSTICAL_VARIATIONS = [
    """BLACK AND WHITE portrait as a VINTAGE MAGICIAN.
Slight caricature - bring out their charismatic features.
Old school stage magic vibes, top hat and cape energy.
Houdini-era showmanship, dramatic theatrical flair.
Vintage playbill illustration style, bold lines.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Fun entertainer energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a VAUDEVILLE STAR.
Slight caricature - emphasize their showman qualities.
Classic illusionist aesthetic, cards and rabbits optional.
Dramatic lighting, stage curtain frame, applause energy.
1920s magic poster style, art deco flourishes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as a CIRCUS MENTALIST.
Slight caricature - capture their mysterious charm.
Mind-reading performer vibes, hypnotic spiral background optional.
Crystal balls, playing cards, mysterious symbols.
Vintage sideshow poster aesthetic.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold graphics. Square aspect ratio.""",
]

# FORTUNE VARIATIONS - Carnival showman style
FORTUNE_VARIATIONS = [
    """BLACK AND WHITE portrait as a CARNIVAL SHOWMAN.
Slight caricature - emphasize their distinctive features.
Vintage carnival poster aesthetic, ringmaster energy.
Step right up! See the amazing! Barnum and Bailey vibes.
Art deco circus poster style, bold graphic lines.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Fun theatrical energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a CIRCUS ANNOUNCER.
Slight caricature - play up their charismatic features.
Big top energy, striped tent frame, spotlight beams.
Megaphone optional, crowd excitement, showtime vibes.
Vintage broadside poster style.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as a FORTUNE BOOTH KEEPER.
Slight caricature - capture their knowing expression.
Arcade fortune machine aesthetic, coin slot decorations.
Mechanical fortune teller vibes, vintage automaton energy.
Carnival fairground poster style.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). High contrast. Square aspect ratio.""",
]

# SKETCH VARIATIONS - Fashion sketch style
SKETCH_VARIATIONS = [
    """BLACK AND WHITE portrait in elegant FASHION SKETCH style.
Slight caricature - capture what makes their face distinctive.
Fashion illustration meets editorial portrait.
Bold confident ink strokes, high contrast.
Vogue-worthy composition, effortless cool.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Clean lines, artistic minimalism. Square aspect ratio.""",

    """BLACK AND WHITE portrait in EDITORIAL ILLUSTRATION style.
Slight caricature - emphasize their striking features.
Magazine cover energy, sophisticated lines.
Brush pen strokes, dynamic composition.
High fashion meets fine art portraiture.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait in QUICK SKETCH style.
Slight caricature - capture their essence in bold strokes.
Artist's notebook aesthetic, spontaneous energy.
Confident line work, expressive minimalism.
Portrait study vibes, gallery worthy.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",
]

# CARTOON VARIATIONS - Playful cartoon style
CARTOON_VARIATIONS = [
    """BLACK AND WHITE portrait in playful CARTOON style.
Moderate caricature - exaggerate their fun features.
Pixar meets manga character design, friendly exaggeration.
Capture their personality in bigger-than-life form.
Joyful, friendly, inviting. Not mean, just playful.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold ink lines, dynamic pose. Square aspect ratio.""",

    """BLACK AND WHITE portrait in ANIMATED CHARACTER style.
Moderate caricature - bring out their animated personality.
Disney energy meets anime expressiveness.
Big eyes optional, exaggerated expressions welcome.
Lovable character design, instant likability.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait in COMIC STRIP style.
Moderate caricature - make them a comic character.
Sunday funnies aesthetic, expressive simplicity.
Speech bubble ready, panel-worthy pose.
Classic newspaper comic energy.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold outlines. Square aspect ratio.""",
]

# VINTAGE VARIATIONS - Circus poster star
VINTAGE_VARIATIONS = [
    """BLACK AND WHITE portrait as a CIRCUS POSTER STAR.
Slight caricature - emphasize their showman qualities.
P.T. Barnum era showmanship meets Art Nouveau elegance.
They are the main attraction, the star of the show!
Victorian theatrical drama with decorative flourishes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Woodcut poster style. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a SILENT FILM STAR.
Slight caricature - capture their dramatic expression.
1920s Hollywood glamour, title card aesthetic.
Dramatic lighting, theatrical pose, silver screen energy.
Art deco frame, vintage film grain texture.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as a VAUDEVILLE PERFORMER.
Slight caricature - play up their entertainer qualities.
Stage lights, curtain frame, applause energy.
Classic theatrical poster design.
Ornate Victorian borders, showbiz glamour.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",
]

# ZODIAC VARIATIONS - Space explorer style
ZODIAC_VARIATIONS = [
    """BLACK AND WHITE portrait as a SPACE EXPLORER.
Slight caricature - capture their adventurous spirit.
Retro sci-fi pulp magazine cover energy, astronaut helmet optional.
Star maps and constellations as decorative background.
1950s space age optimism, rocket ship vibes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold ink illustration. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a COSMIC NAVIGATOR.
Slight caricature - emphasize their visionary gaze.
Starship captain energy, control panel background.
Galaxy swirls, planet rings, cosmic dust.
Golden age sci-fi aesthetic, pulp adventure vibes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as an ASTRAL VOYAGER.
Slight caricature - capture their otherworldly charm.
Constellation map overlay, celestial coordinates.
Moon phases, shooting stars, orbital paths.
Vintage astronomy textbook meets adventure poster.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",
]

# ROULETTE VARIATIONS - Casino winner style
ROULETTE_VARIATIONS = [
    """BLACK AND WHITE portrait as a HIGH ROLLER.
Slight caricature - play up their lucky charm vibe.
Casino royale winner moment, James Bond swagger.
Poker chips flying, dice tumbling, jackpot energy.
Retro Las Vegas lounge style, suave and sophisticated.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Bold ink drawing, dramatic spotlight. Square aspect ratio.""",

    """BLACK AND WHITE portrait as a CASINO CHAMPION.
Slight caricature - emphasize their winning expression.
Slot machine jackpot energy, coins showering down.
Neon sign aesthetic (in B&W), victory celebration.
Vegas golden era, rat pack vibes.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",

    """BLACK AND WHITE portrait as a POKER MASTER.
Slight caricature - capture their poker face (or lack thereof).
Card shark energy, royal flush background.
Smoke and mirrors, high stakes drama.
Film noir casino aesthetic, tension and triumph.
ALL TEXT IN RUSSIAN, ALL CAPS (except VNVNC). Square aspect ratio.""",
]

STYLE_PROMPTS = {
    # =========================================================================
    # GUESS MODE - "Кто Я?" - Detective investigation board (uses GUESS_VARIATIONS)
    # =========================================================================
    CaricatureStyle.GUESS: "GUESS_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # MEDICAL MODE - "Диагноз" - X-ray scan diagnostic (uses MEDICAL_VARIATIONS)
    # =========================================================================
    CaricatureStyle.MEDICAL: "MEDICAL_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # ROAST MODE - "Прожарка" - Adult roast doodle (uses ROAST_VARIATIONS)
    # =========================================================================
    CaricatureStyle.ROAST: "ROAST_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # PROPHET MODE - "ИИ Пророк" - Fun AI prophet (uses PROPHET_VARIATIONS)
    # =========================================================================
    CaricatureStyle.PROPHET: "PROPHET_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # TAROT MODE - "Гадалка" - New Year 2026 sticker (uses TAROT_VARIATIONS)
    # =========================================================================
    CaricatureStyle.TAROT: "TAROT_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # QUIZ WINNER - "Викторина" - Game show champion (uses QUIZ_WINNER_VARIATIONS)
    # =========================================================================
    CaricatureStyle.QUIZ_WINNER: "QUIZ_WINNER_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # MYSTICAL - Now fun/stylish, not esoteric (uses MYSTICAL_VARIATIONS)
    # =========================================================================
    CaricatureStyle.MYSTICAL: "MYSTICAL_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # FORTUNE - Now fun/stylish carnival, not mystical (uses FORTUNE_VARIATIONS)
    # =========================================================================
    CaricatureStyle.FORTUNE: "FORTUNE_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # SKETCH - Fashion sketch style (uses SKETCH_VARIATIONS)
    # =========================================================================
    CaricatureStyle.SKETCH: "SKETCH_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # CARTOON - Playful cartoon style (uses CARTOON_VARIATIONS)
    # =========================================================================
    CaricatureStyle.CARTOON: "CARTOON_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # VINTAGE - Circus poster star (uses VINTAGE_VARIATIONS)
    # =========================================================================
    CaricatureStyle.VINTAGE: "VINTAGE_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # ZODIAC MODE - Space explorer style (uses ZODIAC_VARIATIONS)
    # =========================================================================
    CaricatureStyle.ZODIAC: "ZODIAC_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # ROULETTE MODE - Casino winner style (uses ROULETTE_VARIATIONS)
    # =========================================================================
    CaricatureStyle.ROULETTE: "ROULETTE_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # PHOTOBOOTH MODE - Christmas 2x2 photo booth grid (uses PHOTOBOOTH_VARIATIONS)
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH: "PHOTOBOOTH_VARIATION",  # Will be replaced with random variation
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
            variation_map = {
                "ROAST_VARIATION": ROAST_VARIATIONS,
                "PROPHET_VARIATION": PROPHET_VARIATIONS,
                "TAROT_VARIATION": TAROT_VARIATIONS,
                "PHOTOBOOTH_VARIATION": PHOTOBOOTH_VARIATIONS,
                "GUESS_VARIATION": GUESS_VARIATIONS,
                "MEDICAL_VARIATION": MEDICAL_VARIATIONS,
                "QUIZ_WINNER_VARIATION": QUIZ_WINNER_VARIATIONS,
                "MYSTICAL_VARIATION": MYSTICAL_VARIATIONS,
                "FORTUNE_VARIATION": FORTUNE_VARIATIONS,
                "SKETCH_VARIATION": SKETCH_VARIATIONS,
                "CARTOON_VARIATION": CARTOON_VARIATIONS,
                "VINTAGE_VARIATION": VINTAGE_VARIATIONS,
                "ZODIAC_VARIATION": ZODIAC_VARIATIONS,
                "ROULETTE_VARIATION": ROULETTE_VARIATIONS,
            }
            if style_prompt in variation_map:
                style_prompt = random.choice(variation_map[style_prompt])

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
- BLACK AND WHITE ONLY - pure black ink on white background, high contrast
- NO colors, NO grayscale shading - just black and white like a thermal print
- High quality artistic illustration, NOT pixel art, NOT photorealistic
- TEXT LANGUAGE RULES (CRITICAL!!!):
  * The brand name "VNVNC" must ALWAYS stay in ENGLISH letters: V-N-V-N-C
  * NEVER translate or transliterate VNVNC to Russian (НЕ писать ВНВНЦ или что-то подобное!)
  * All OTHER text (labels, annotations, decorations) must be in RUSSIAN, ALL CAPS
  * Example: "VNVNC 2026" is correct, "ВНВНЦ 2026" is WRONG!
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
                style="Black and white illustration, high contrast ink drawing, thermal printer style",
            )

            if image_data:
                # Process and ensure B&W output
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
        """Process the generated image for display (convert to grayscale).

        Converts to grayscale and resizes while maintaining aspect ratio.
        This ensures consistent B&W output even if Gemini returns color.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions

        Returns:
            Processed image bytes (grayscale as RGB for compatibility)
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(image_data))

            # Convert to grayscale first
            img = img.convert("L")

            # Convert back to RGB (grayscale values in all 3 channels)
            # This ensures compatibility with displays expecting RGB
            img = img.convert("RGB")

            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

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
