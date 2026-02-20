"""Artistic portrait generation service using Gemini/Imagen.

Generates stylized artistic portraits based on user photos.
Most styles generate BLACK AND WHITE for thermal printer output.
PHOTOBOOTH styles generate FULL COLOR for digital-only display and S3 gallery.

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
    PHOTOBOOTH = "photobooth"  # 9:16 vertical photo booth strip for label
    PHOTOBOOTH_SQUARE = "photobooth_square"  # 1:1 square photo booth for LED display
    PHOTOBOOTH_VENICE = "photobooth_venice"  # 9:16 vertical - TRIP:VENICE carnival theme
    PHOTOBOOTH_VENICE_SQUARE = "photobooth_venice_square"  # 1:1 square - TRIP:VENICE theme
    PHOTOBOOTH_LOVEINTHEAIR = "photobooth_loveintheair"  # 9:16 vertical - Valentine's theme
    PHOTOBOOTH_LOVEINTHEAIR_SQUARE = "photobooth_loveintheair_square"  # 1:1 square - Valentine's theme
    PHOTOBOOTH_MALCHISHNIK = "photobooth_malchishnik"  # 9:16 vertical - Hangover bachelor party theme
    PHOTOBOOTH_MALCHISHNIK_SQUARE = "photobooth_malchishnik_square"  # 1:1 square - Hangover bachelor party theme
    Y2K = "y2k"                # 2000s era character portrait
    BAD_SANTA = "bad_santa"    # Naughty/nice Santa verdict


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
# Most styles: BLACK AND WHITE for thermal printer
# PHOTOBOOTH styles: FULL COLOR for digital gallery
# TEXT RULES: Russian language, ALL CAPS, VERY LARGE readable
# NO example labels - model copies them literally
# VARIETY: Each prompt has multiple variations to avoid repetition
# =============================================================================

# ROAST VARIATIONS - Reddit/r/RoastMe style (18+) - BLACK AND WHITE
# Style: Isolated portrait, stunning minimal B&W, speech bubbles, cool doodles
# CRITICAL: DO NOT use example texts literally! Create ORIGINAL content for THIS PERSON!
ROAST_VARIATIONS = [
    """ISOLATE THE PERSON. Perfect BLACK AND WHITE drawing - stunning and MINIMAL.
r/RoastMe energy - BRUTAL but CREATIVE. What would Reddit say about THIS face?
Add HANDWRITTEN TEXT as SPEECH BUBBLES with savage RUSSIAN roasts.
Surround with cool DOODLES and SCRIBBLES - abstract shapes, squiggles, stars, arrows.

Think "top comment on Reddit" - personal, specific, DEVASTATING but hilarious.
The roast must be SPECIFIC to THIS PERSON's actual appearance!
Look at their face, hair, expression, vibe - and roast THAT.
BRANDING: Just "VNVNC" somewhere small - NO YEAR, never add 2024/2025/2026!
Black ink on white. Square. The kind of roast that makes you say "damn" and laugh.""",

    """STUNNING MINIMAL B&W PORTRAIT. Isolate this person, draw them PERFECTLY.
BRUTAL HONEST ROAST like r/RoastMe - find what's ACTUALLY roastable about THIS SPECIFIC PERSON.
SPEECH BUBBLES with YOUR OWN savage labels in RUSSIAN - be ORIGINAL, don't copy anything.
Cool DOODLES scattered around - messy scribbles, zigzags, exclamation marks, spirals.

NO GENERIC INSULTS - be SPECIFIC to THIS person's unique flaws.
You are a comedy WRITER. Don't copy - CREATE. Look at this person and
find what's ACTUALLY funny about them. Original observations only.
BRANDING: Just "VNVNC" small somewhere - NEVER add any year!
Clean portrait, chaotic doodles. Square. Make it hurt (in a funny way).""",

    """ISOLATED PORTRAIT - perfect B&W, super minimal. ROAST BATTLE energy.
What would a standup comedian IMMEDIATELY notice about THIS person? Draw that.
HANDWRITTEN SPEECH BUBBLES in RUSSIAN with standup-worthy burns.
Add cool SCRIBBLES and DOODLES around - lightning bolts, crosses, underlines, chaos.

BE ORIGINAL: Study the photo. What's weird? What's tryhard? What screams "roast me"?
Create roasts that are SPECIFIC to this face. No templates, no copying.
Like a mean caricature artist at a carnival who tells the TRUTH.
BRANDING: "VNVNC" only - NO YEAR (never 2024, 2025, 2026, etc)!
Stunning drawing meets savage comedy. Square.""",

    """PERFECT BLACK AND WHITE SKETCH. Isolate this person BEAUTIFULLY.
INTERNET ROAST DOODLE energy - what would Reddit say about THIS SPECIFIC face?
SPEECH BUBBLES with YOUR ORIGINAL savage humor in RUSSIAN - internet troll energy.
Messy DOODLES around - scrawls, asterisks, emphasis marks, chaotic decorations.

Find the MEME potential unique to THIS person. Exaggerate what makes THEM roastable.
CREATIVITY REQUIRED: Every person has something unique to roast. Find it.
Don't use any pre-written labels. Observe and create fresh burns for THIS face.
BRANDING: Just "VNVNC" - absolutely NO year attached!
Beautiful portrait meets chaotic energy. Square. Original savage commentary only.""",
]

# VNVNC STICKER VARIATIONS - Portrait stickers with mystical/fortune-teller vibes
TAROT_VARIATIONS = [
    """BLACK AND WHITE portrait STICKER of this person as a MYSTICAL CHARACTER!
Slight caricature - emphasize their mysterious charm.
Big decorative "VNVNC" logo prominently displayed in ornate mystical lettering.
Stars, moons, cosmic swirls, crystal ball elements as decoration.
Sticker die-cut style with white border.
Fortune teller carnival energy, mystical arcade vibes. Square aspect ratio.""",

    """BLACK AND WHITE portrait STICKER with magical vibes!
Slight caricature - capture their enigmatic spirit.
Ornate mystical-style "VNVNC" as the main text element.
Tarot card aesthetic, all-seeing eye, celestial motifs around the portrait.
Bold sticker outline, vintage carnival hand-lettered text.
Mysterious fortune teller mood. Square aspect ratio.""",

    """BLACK AND WHITE mystical STICKER portrait!
Slight caricature - bring out their mysterious features.
Decorative vintage carnival lettering showing "VNVNC" prominently.
Crystal balls, playing cards, stars, cosmic rays.
Classic sticker format with clean die-cut edge.
Arcade fortune machine aesthetic. Square aspect ratio.""",

    """BLACK AND WHITE MYSTIC STICKER of this person!
Slight caricature - emphasize what makes them intriguing.
Big bold "VNVNC" in fancy vintage carnival font style.
Sparkles, stars, mystical symbols, fortune-telling elements.
Sticker aesthetic with thick outline border.
Sideshow attraction vibes, mysterious oracle energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait STICKER - Fortune Teller Style!
Slight caricature - capture their mystical personality.
Ornamental "VNVNC" text in decorative vintage calligraphy.
Crystal ball, tarot cards, cosmic decorations.
Die-cut sticker style, bold graphic look.
Carnival mystic, arcade fortune machine vibes. Square aspect ratio.""",

    """BLACK AND WHITE mystical celebration STICKER!
Slight caricature - play up their mysterious expression.
Retro sideshow poster style "VNVNC" lettering.
Vintage circus illustrations: stars, moons, cosmic elements.
Classic sticker format with decorative border.
Nostalgic carnival energy, fortune teller aesthetic. Square aspect ratio.""",
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

# PHOTOBOOTH VARIATIONS - BOILING ROOM underground DJ party theme VERTICAL photo strip
# OUTPUT: 9:16 VERTICAL aspect ratio — FULL COLOR (red & black only)
# STYLE: Chromatic aberration, super wide angle, film grain, analog textures
PHOTOBOOTH_VARIATIONS = [
    """BOILING ROOM — VECTOR ART PHOTO BOOTH (VERTICAL 9:16)

Create a VERTICAL photo booth strip (9:16 ratio) with 4 drawings in a 2×2 grid.

CRITICAL TEXT RULES:
- ONLY these texts allowed: "BOILING ROOM", "31.01", "VNVNC"
- NO OTHER TEXT WHATSOEVER — no captions, no labels, no words, no letters anywhere else
- "VNVNC" must be in TALL CONDENSED IMPACT-STYLE FONT — white letters inside thin red rectangular border

ART STYLE — VECTOR / SKETCH ILLUSTRATION (NOT A PHOTO!):
- Each frame is a STYLISH PINTEREST-WORTHY DRAWING / ILLUSTRATION of the person
- Bold clean lines, flat color fills, graphic novel / poster art quality
- Think: Shepard Fairey, Alphonse Mucha meets modern vector art, screen print aesthetic
- Strong graphic shapes, high contrast, confident ink strokes
- NOT photorealistic — this is an ILLUSTRATION, a cool artistic interpretation
- Capture the person's likeness and distinctive features 

PRINTED FULL BLEED ON DARK TEXTURED POLAROID PAPER — THE ENTIRE BACKGROUND:
- The paper/background is DARK — black or very dark charcoal with visible texture
- Heavy paper grain, rough matte black cardstock feel, tactile and moody
- Borders between frames are DARK textured paper — not white, not cream
- The whole strip feels like it's printed on expensive dark art paper
- Ink and color sit ON TOP of the dark surface — like screen printing on black paper
- Visible paper fiber, subtle noise, rough tactile quality throughout

ALL PEOPLE FROM THE REFERENCE PHOTO:
- Include all MAIN SUBJECTS in the foreground — if it's a group photo, draw the WHOLE GROUP together
- Same people in all 4 frames but with DIFFERENT expressions and poses each time
- Background within each frame: dark with red/neon accents, smoke, club atmosphere

COLOR PALETTE: Red, black, white, and skin tones only. Red neon glows, white highlights.
Person looks ATTRACTIVE and cool — stylish, confident, flattering artistic interpretation.
NOT sweaty. NOT gross. Clean and stylish vector art.

4 FRAMES — same person, different vibes:
Frame 1: Cool confident look, slight smile, red neon glow behind
Frame 2: Laughing or big smile, head tilted, dynamic line work
Frame 3: Arms up or hands near face, vibing, eyes closed, red backlight glow
Frame 4: Different angle — looking to side or over shoulder, moody red accent lighting

LENS FEEL: SUPER WIDE ANGLE (14-18mm) distortion in the drawing — exaggerated perspective.
EFFECTS: Halftone dots, screen print texture, bold outlines, graphic poster quality.

TOP: "BOILING ROOM" bold graphic text (ENGLISH!), "31.01" below.
BOTTOM: "VNVNC" — tall condensed white letters inside thin red rectangular border.

9:16 VERTICAL. Vector/sketch style drawings on DARK textured paper!""",

    """BOILING ROOM — SKETCH ART BOOTH (VERTICAL 9:16)

Generate a VERTICAL (9:16) photo booth strip — 4 illustrations in a 2×2 grid.

CRITICAL TEXT RULES:
- ONLY these texts allowed: "BOILING ROOM", "31.01", "VNVNC"
- NO OTHER TEXT WHATSOEVER — no captions, no labels, no words, no letters anywhere else
- "VNVNC" must be in TALL CONDENSED IMPACT-STYLE FONT — white letters inside thin red rectangular border

ART STYLE — BOLD SKETCH / VECTOR ILLUSTRATION:
- NOT a photograph — each frame is a stylish DRAWING of the person
- Clean vector lines, bold ink strokes, flat graphic color fills
- Screen print / risograph / poster art aesthetic
- High contrast, strong silhouettes, graphic and punchy
- Capture the person's LIKENESS — recognizable features rendered as cool illustration

CAMERA: EXTREME WIDE ANGLE (12-16mm) distortion in EVERY frame — fisheye-like barrel distortion, dramatic close-ups!

DARK TEXTURED PAPER SURFACE:
- Background paper is BLACK or very dark — like printing on black cardstock
- Heavy visible paper texture: grain, fiber, rough matte surface
- Dark borders and gaps between all 4 frames — dark paper visible everywhere
- Art sits ON the dark surface — colors pop against the dark background
- Feels like a limited-edition screen print on premium dark stock
- Text and logos also look printed/stamped on the dark paper

ALL PEOPLE FROM THE REFERENCE PHOTO:
- Include all MAIN SUBJECTS in the foreground — if it's a group photo, draw the WHOLE GROUP together
- Same people in all 4 frames with DIFFERENT expressions and poses
- Background within frames: dark with red/neon graphic elements, smoke shapes

LOOK: Person rendered as ATTRACTIVE and cool — flattering artistic style.
COLOR: Red, white, black. Skin rendered with warmth but stylized. Red neon accents.
NOT sweaty. NOT dark/murky faces. Bold, well-defined, stylish illustration.

4 FRAMES — same person, 4 different moments:
Frame 1: Looking at viewer, confident, red glow behind, bold line work
Frame 2: Genuine smile or laugh, dynamic pose, graphic energy
Frame 3: Vibing — eyes closed, head back, feeling the music, red backlight shapes
Frame 4: Profile or three-quarter view, moody red rim light, mysterious

PERSPECTIVE: SUPER WIDE ANGLE distortion feel — exaggerated foreshortening in the drawing.
EFFECTS: Halftone, screen print texture, bold outlines, limited color palette.

TOP: "BOILING ROOM" bold text (ENGLISH!), "31.01" below.
BOTTOM: "VNVNC" — TALL CONDENSED IMPACT-STYLE FONT, white letters in thin red rectangular border.

9:16 VERTICAL. Sketch/vector illustrations on DARK textured paper!""",

    """BOILING ROOM — GRAPHIC ART BOOTH (VERTICAL 9:16)

Create a VERTICAL (9:16) photo booth strip with 4 illustrations in 2×2 layout.

CRITICAL TEXT RULES:
- ONLY these texts allowed: "BOILING ROOM", "31.01", "VNVNC"
- NO OTHER TEXT WHATSOEVER — no captions, no labels, no words, no letters anywhere else
- "VNVNC" must be in TALL CONDENSED IMPACT-STYLE FONT — white letters inside thin red rectangular border

ART STYLE — GRAPHIC VECTOR ILLUSTRATION:
- Each frame is a VECTOR-STYLE ARTWORK of the person — NOT a photograph
- Bold graphic lines, clean shapes, flat fills with subtle gradients
- Aesthetic: mix of pop art, screen print, editorial illustration
- Strong outlines, confident strokes, high contrast, punchy composition
- Person's face and features are RECOGNIZABLE — artistic but accurate likeness


DARK TEXTURED PAPER — PREMIUM FEEL:
- ENTIRE background/paper is DARK — black or deep charcoal
- Rich paper texture: visible grain, matte finish, rough fiber, tactile
- Dark gaps between frames show the paper surface — no white borders
- Art is printed ON dark paper — colors and whites pop dramatically
- Feels like a limited run art print on heavy dark stock
- All text looks screen-printed or letterpress-stamped on the dark surface

ALL PEOPLE FROM REFERENCE PHOTO:
- Include all MAIN SUBJECTS in the foreground — if it's a group photo, draw the WHOLE GROUP
- All people together in each frame with dark + red graphic background elements
- Same people, 4 DIFFERENT expressions and poses — vary the energy

STYLE: Person looks ATTRACTIVE — cool, stylish, confident in the illustration.
COLOR: Red, black, white primary palette. Warm skin tones (stylized but natural).
Red neon glows and accents. NOT sweaty. NOT grimy. Clean, bold, aspirational art.

4 FRAMES — different expressions and angles:
Frame 1: Direct look, confident half-smile, red glow shapes behind
Frame 2: Candid laugh, dynamic composition, bold graphic energy
Frame 3: Music vibe — eyes closed, peaceful or ecstatic, red backlight shapes
Frame 4: Profile or angled view, moody red accent, atmospheric

PERSPECTIVE: SUPER WIDE ANGLE distortion in the illustration — barrel distortion feel.
EFFECTS: Halftone dots, screen print registration marks, bold outlines, graphic texture.

TOP: "BOILING ROOM" — bold graphic text (ENGLISH!), "31.01" below.
BOTTOM: "VNVNC" — TALL CONDENSED IMPACT-STYLE FONT, white letters inside thin red rectangular border.

9:16 VERTICAL. Vector/graphic art on DARK textured paper!""",
]

# PHOTOBOOTH SQUARE VARIATIONS - BOILING ROOM theme 1:1 for LED display
# OUTPUT: 1:1 SQUARE aspect ratio for 128x128 LED display preview
# STYLE: Red & black only, chromatic aberration, wide angle, analog texture
PHOTOBOOTH_SQUARE_VARIATIONS = [
    """BOILING ROOM — VECTOR ART BOOTH (SQUARE 1:1)

Create a SQUARE (1:1) photo booth grid with 4 vector-style drawings in a 2×2 layout.

ART STYLE: VECTOR / SKETCH ILLUSTRATION — NOT a photo. Bold lines, flat color fills,
screen print / poster art aesthetic. Capture the person's likeness as cool illustration.
High contrast, strong graphic shapes, modern editorial art quality.

DARK TEXTURED PAPER: Background is BLACK/dark charcoal with heavy paper grain texture.
Dark borders between frames. Art printed ON dark paper — colors pop against black.
Feels like a limited-edition screen print on premium dark stock.

ALL PEOPLE FROM THE REFERENCE PHOTO:
- Include all MAIN SUBJECTS in the foreground — if it's a group photo, draw the WHOLE GROUP
- Same people, 4 DIFFERENT expressions and poses.

Person looks ATTRACTIVE and cool in the illustration. NOT sweaty. Clean, stylish, bold art.
COLOR: Red, black, white. Warm skin tones (stylized). Red neon accents and glows.

4 FRAMES — different expressions:
Frame 1: Confident look, slight smile, red glow shapes behind
Frame 2: Laughing, dynamic, bold graphic energy
Frame 3: Vibing — eyes closed, feeling music, red backlight shapes
Frame 4: Different angle, moody red accent lighting

PERSPECTIVE: SUPER WIDE ANGLE distortion feel in the drawing.
EFFECTS: Halftone, screen print texture, bold outlines.

BRANDING: "VNVNC" — tall condensed white letters in thin red rectangular border.

SQUARE 1:1. Vector/sketch art on DARK textured paper!""",
]

# =============================================================================
# TRIP:VENICE PHOTOBOOTH VARIATIONS - Venetian Carnival 3D Sims-style theme
# =============================================================================
# OUTPUT: 9:16 VERTICAL aspect ratio - for label printing
# STYLE: High-quality 3D render like Sims characters, Venice carnival masks,
#        dark mysterious atmosphere, printed on textured paper
# DATES: 06.02-07.02

TRIPVENICE_VARIATIONS = [
    """TRIP:VENICE — FLAT VECTOR PHOTO BOOTH (VERTICAL 9:16)

Create a VERTICAL photo booth strip (9:16 ratio) with 4 illustrations in a 2×2 grid.

TEXT RULES:
- ONLY allowed: "TRIP:VENICE", "06.02-07.02", "VNVNC"
- NO OTHER TEXT — no captions, no labels, no words anywhere else
- "VNVNC" in tall condensed white letters inside thin gold border

STYLE — PINTEREST-WORTHY FLAT VECTOR ART:
- Stylish flat vector illustration — NOT a photograph, NOT 3D
- Bold clean lines, flat color fills, modern poster art quality
- Cool, fashionable, aspirational — like a high-end fashion illustration
- Person looks ATTRACTIVE, STYLISH, CONFIDENT — never creepy or weird
- Capture likeness but make them look their BEST

COLOR PALETTE:
- GOLD (primary), RED VELVET (secondary), deep purple, black, cream
- Warm flattering skin tones — glowing and healthy looking
- NOT muddy, NOT dark faces, NOT sweaty

VENETIAN CARNIVAL VIBES:
- Ornate Venetian masks with golden filigree, feathers, jewels
- Elegant mystery, dark romance, Venice at night energy
- Carnival lights, palazzo silhouettes in background

DEPTH AND LAYERS:
- Background: misty Venice silhouettes, canal reflections, soft carnival lights
- Middle: floating confetti, golden sparkles, feathers
- Foreground: person crisp and vibrant

DARK TEXTURED PAPER:
- Background is BLACK with visible paper grain texture
- Dark borders between frames — premium art print feel

PEOPLE:
- Draw everyone from the reference photo
- Same people in all 4 frames, DIFFERENT cool poses each time
- 2 frames WITH Venetian masks, 2 frames WITHOUT masks
- Make them look fashionable and having fun

TOP: "TRIP:VENICE" bold text, "06.02-07.02" below
BOTTOM: "VNVNC" white condensed letters in gold border

9:16 VERTICAL. Stylish, Pinterest-worthy, flat vector art!""",

    """TRIP:VENICE — STYLISH VECTOR BOOTH (VERTICAL 9:16)

VERTICAL (9:16) photo booth strip — 4 flat vector illustrations in 2×2 grid.

TEXT: Only "TRIP:VENICE", "06.02-07.02", "VNVNC" allowed. Nothing else.
"VNVNC" = tall condensed white letters in thin gold rectangular border.

STYLE — COOL FLAT VECTOR ART:
- Pinterest-worthy flat illustration — fashionable and stylish
- Bold lines, flat colors, modern poster aesthetic
- Person looks GORGEOUS — attractive, confident, never weird or creepy
- Like a fashion magazine illustration meets screen print art

COLORS:
- GOLD and RED VELVET primary accents
- Deep purple, black, cream supporting colors
- Warm glowing skin tones — flattering and vibrant

VENETIAN CARNIVAL:
- Elegant Venetian masks — gilded, feathered, jeweled
- Venice at night atmosphere — mystery and romance
- Carnival celebration energy

DEPTH:
- Layered composition with background, middle, foreground
- Soft misty carnival background, floating confetti middle layer
- Person sharp and detailed in front

DARK PAPER TEXTURE:
- Black textured paper background with visible grain
- Dark gaps between frames

PEOPLE:
- Include everyone from photo — draw the whole group if multiple people  
- 4 different poses — mix of masked and unmasked looks
- Make them look cool, stylish, having an amazing time

Header: "TRIP:VENICE" + "06.02-07.02"
Footer: "VNVNC" in gold-bordered white text

9:16 VERTICAL. Stylish flat vector on dark textured paper!""",

    """TRIP:VENICE — VECTOR ART BOOTH (VERTICAL 9:16)

VERTICAL (9:16) photo booth — 4 flat vector frames in 2×2 layout.

TEXT ONLY: "TRIP:VENICE", "06.02-07.02", "VNVNC" — nothing else anywhere.

STYLE — FASHIONABLE FLAT VECTOR:
- Pinterest aesthetic — cool, stylish, aspirational
- Flat colors, bold outlines, modern screen print look
- Person rendered BEAUTIFULLY — attractive and confident
- NOT creepy, NOT weird, NOT dark muddy faces
- Fashion illustration meets poster art quality

COLOR SCHEME:
- GOLD + RED VELVET as main accent colors
- Purple, black, cream, ivory supporting
- Skin: warm, glowing, flattering tones

VENICE CARNIVAL MOOD:
- Ornate masks with gold details, feathers, gems
- Mysterious elegant night atmosphere
- Candlelight warmth, carnival magic

VISUAL DEPTH:
- Background layer: Venice palazzo shapes, canal lights in fog
- Middle layer: sparkles, confetti, floating feathers
- Foreground: person rendered crisp and vibrant

PAPER:
- Dark black textured paper background
- Visible grain, premium print feel

SUBJECTS:
- Draw everyone in the reference photo together
- 4 frames with different cool poses
- Mix of with-mask and without-mask shots
- Everyone looks stylish and happy

"TRIP:VENICE" + "06.02-07.02" at top
"VNVNC" in gold-framed white text at bottom

9:16 VERTICAL. Stylish, Pinterest-worthy flat vector art!""",
]

# TRIP:VENICE SQUARE VARIATIONS - 1:1 for LED display
TRIPVENICE_SQUARE_VARIATIONS = [
    """TRIP:VENICE — FLAT VECTOR BOOTH (SQUARE 1:1)

SQUARE (1:1) photo booth grid — 4 flat vector illustrations in 2×2 layout.

TEXT: Only "TRIP:VENICE", "06.02-07.02", "VNVNC" allowed. Nothing else.
"VNVNC" = tall condensed white letters in thin gold rectangular border.

STYLE — PINTEREST-WORTHY FLAT VECTOR:
- Stylish flat vector illustration — fashionable and cool
- Bold lines, flat colors, modern poster aesthetic
- Person looks GORGEOUS — attractive, confident, stylish
- NOT creepy, NOT weird, NOT dark muddy faces
- Like fashion illustration meets screen print art

COLORS:
- GOLD + RED VELVET primary accents
- Purple, black, cream supporting colors
- Warm glowing skin — flattering and vibrant

VENETIAN CARNIVAL:
- Elegant Venetian masks — gilded, feathered, jeweled
- Venice at night energy — mystery and elegance

DEPTH:
- Background: misty Venice shapes, soft carnival lights
- Middle: floating confetti, sparkles, feathers
- Foreground: person crisp and vibrant

PAPER:
- Black textured paper background with visible grain
- Dark gaps between frames

PEOPLE:
- Draw everyone from reference photo together
- 4 frames with different cool poses
- Mix of masked and unmasked looks
- Everyone looks stylish and having fun

"VNVNC" in gold-bordered white text

SQUARE 1:1. Stylish, Pinterest-worthy flat vector!""",
]

# =============================================================================
# LOVE IN THE AIR PHOTOBOOTH VARIATIONS - Valentine's Day romantic theme
# =============================================================================
# OUTPUT: 9:16 VERTICAL aspect ratio - for label printing / S3 gallery
# STYLE: Warm illustrated Valentine's card — clean linework, soft colors
# DATES: 13.02-14.02
# NOTE: ONE prompt only — no variations, exact style match required

LOVEINTHEAIR_VARIATIONS = [
    """LOVE IN THE AIR — VALENTINE PORTRAIT CARD (VERTICAL 9:16)

Create a VERTICAL (9:16) Valentine's portrait card. Follow this EXACT layout and style:

CARD LAYOUT (top to bottom):
1. HEADER SECTION (top ~25%):
   - Cream/ivory background for the whole card
   - Thin rounded pink border around the entire card with rounded corners
   - Big hand-drawn pink puffy letters: "LOVE IN THE AIR" — all four words on ONE single line
   - All words same hand-drawn pink style, "IN THE" slightly smaller than "LOVE" and "AIR"
   - DO NOT repeat "in the" or any words — the header is EXACTLY four words: LOVE IN THE AIR
   - Small decorative curly ornaments (flourishes) on either side
   - "VNVNC  13.02-14.02" in small dark text centered below
   - A thin horizontal line separating header from portrait

2. PORTRAIT SECTION (middle ~55%):
   - Inside a rounded rectangle with thin pink border
   - Person drawn in warm illustrated style — clean bold outlines, flat warm colors
   - CRITICAL LIKENESS: The person MUST look like THEMSELVES — same face shape, same hairstyle, same hair color, same facial features, same glasses if worn, same clothing. This is a portrait of THEM, not a generic person.
   - Normal adult proportions, attractive but RECOGNIZABLE as the actual person in the photo
   - Warm natural skin tones, clean hair rendering matching their real hair
   - EXACT same clothing as in their photo — same colors, same style
   - CRITICAL BACKGROUND: Draw the ACTUAL background from the reference photo — the real venue, real walls, real furniture, real lighting. This is a nightclub/bar, NOT a coffee shop, NOT a park, NOT a random place. Draw what you SEE in the photo behind them.
   - Scattered around them: small red/pink hearts, a red rose, a love letter envelope with heart seal
   - Hearts and romantic elements float ON TOP of the real scene, not replacing the background

3. FOOTER SECTION (bottom ~20%):
   - Pink/blush banner ribbon with RUSSIAN text in dark rose cursive:
     ALWAYS use: "Любовь витает в воздухе" (this is the ONLY text allowed here)
   - Below the banner: "VNVNC" on the left, "13.02-14.02" on the right, small dark text

ART STYLE — MUST MATCH EXACTLY:
- Warm illustrated portrait — like a modern greeting card or webtoon portrait
- Clean bold outlines with flat warm color fills
- Slightly stylized but NORMAL proportions — NOT chibi, NOT anime, NOT exaggerated
- Warm soft palette: cream, blush pink, rose, coral, warm skin tones
- Person looks attractive and natural, like a skilled illustrator drew them
- Clean, polished, professional illustration quality

TEXT RULES:
- "LOVE IN THE AIR" header: EXACTLY these 4 words, ONE LINE ONLY, hand-drawn pink puffy letters. NEVER duplicate or repeat any word.
- Bottom banner: RUSSIAN only, max 5 words, dark rose cursive
- "VNVNC" always in English
- NO "Love is..." in English, NO long text anywhere
- NO year in header (just "VNVNC  13.02-14.02")

ALL PEOPLE AND SURROUNDINGS FROM REFERENCE PHOTO:
- Draw everyone visible — friends together, groups together
- Do NOT assume people are couples. Friends, groups, solo — draw them as they are
- Only draw people as a romantic couple if it's obviously a man and woman in a romantic pose
- Male friends together = friends, NOT a couple. Female friends = friends, NOT a couple.
- LIKENESS IS EVERYTHING: Each person must be RECOGNIZABLE — same face, same hair, same features, same clothes. Do not generalize or beautify beyond recognition.
- The background MUST be the REAL venue from the photo — a nightclub/bar interior. NEVER replace it with a coffee shop, park, bedroom, or any imagined location. Draw what is actually visible behind them.

9:16 VERTICAL format.""",
]

# LOVE IN THE AIR SQUARE VARIATIONS - 1:1 for LED display
# NOTE: ONE prompt only — same style as vertical, adapted for square
LOVEINTHEAIR_SQUARE_VARIATIONS = [
    """LOVE IN THE AIR — VALENTINE PORTRAIT (SQUARE 1:1)

SQUARE (1:1) Valentine's portrait — same style as the vertical card.

Warm illustrated portrait with clean bold outlines and flat warm colors.
Slightly stylized but NORMAL adult proportions — NOT chibi, NOT anime.
Like a modern greeting card illustration — polished, warm, attractive.

COLORS: Cream/ivory tones, blush pink, rose, coral, warm skin tones.
Small scattered hearts and rose petals floating on top of the scene.

BACKGROUND: Draw the ACTUAL background from the reference photo — the real venue (nightclub/bar), real walls, real furniture. NEVER replace with a coffee shop, park, or imagined location. Draw what you SEE.

PEOPLE:
- Everyone from reference photo, normal proportions
- Do NOT assume people are couples — draw friends as friends, groups as groups
- Only portray as romantic couple if obviously a man and woman in romantic pose
- LIKENESS IS CRITICAL: Same face, same hair, same clothing, same features — person must be RECOGNIZABLE as themselves

TEXT: Only small "VNVNC" somewhere. No other text.

SQUARE 1:1 format.""",
]


# =============================================================================
# МАЛЬЧИШНИК PHOTOBOOTH VARIATIONS — Hangover bachelor party theme
# =============================================================================
# OUTPUT: 9:16 VERTICAL aspect ratio — for label printing / S3 gallery
# STYLE: Disposable camera / Polaroid film shot — analog grain, blown flash
# DATES: 20.02-22.02  VENUE: Конюшенная 2В  BRAND: VNVNC.RU
# NOTE: Moscow time is passed via personality_context and must appear in caption

MALCHISHNIK_VARIATIONS = [
    """МАЛЬЧИШНИК — FILM POLAROID PARTY PHOTO (VERTICAL 9:16)

A POLAROID taken by someone drunk at 3am. Shot on a disposable KODAK FunSaver —
grainy, flash-blown, slightly tilted, full analog soul.

POLAROID FRAME LAYOUT (vertical, white borders all sides):

TOP LABEL — bold rubber-stamp block letters across the top white border:
  "МАЛЬЧИШНИК"

PHOTO AREA (~75% of height):
  Person(s) from reference photo in full chaos mode — drunk smiles,
  arms around each other, wild eyes, someone mid-shout or mid-laugh.
  Classic Hangover movie energy: photographic evidence from the night.
  Nightclub/bar interior behind them — dark walls, colored lights,
  drinks on a table, smoke, neon reflections.
  DRAW THE ACTUAL PEOPLE from the reference photo with real features.
  Flash hits center hard — faces slightly bleached, background darker.
  Slight Dutch angle (frame tilted 2-5 degrees). Possible red-eye.
  Motion blur at edges from camera shake. Very "caught in the act" energy.

ANALOG FILM IMPERFECTIONS:
  Heavy film grain across the whole image.
  Warm pushed colors — yellows and ambers boosted, slight green in shadows.
  Light leaks on one or two edges (orange/red burn creeping in).
  Slight chemical staining — faint magenta or cyan patches.
  Center overexposed (flash), corners slightly vignette-dark.

BOTTOM CAPTION STRIP (white Polaroid area, handwritten ink):
  Left side:   "VNVNC.RU"
  Right side:  "[time from personality context] МСК"
  Center row:  "20.02–22.02  ·  Конюшенная 2В"

OVERALL FEELING: This photo is undeniable evidence of a legendary night.
The kind you find in your pocket three days later wondering what happened.

VERTICAL 9:16 format.""",

    """МАЛЬЧИШНИК — DISPOSABLE CAMERA FOUND FOOTAGE (VERTICAL 9:16)

Imagine this photo printed from a disposable camera that was left on a bar
and shot by five different people throughout the night. This is frame 23.

POLAROID FRAME (white border, thick at bottom):

TOP STAMP: "МАЛЬЧИШНИК" — heavy stencil font, slightly imperfect ink

PHOTO:
  Group or solo shot — person from reference photo deep in party mode.
  Close-up, slightly off-center — nobody posed for this, it just happened.
  Expression: genuine chaos. Could be laughing, yelling, toasting, confused.
  Real venue behind them: nightclub/bar with moody colored lighting.
  DRAW THE REAL PERSON — same face, same hair, same clothes from the photo.
  If multiple people in reference, all appear together in glorious disorder.

FILM LOOK:
  Fujifilm Superia 400 aesthetic — slightly cooler than Kodak, more grain.
  Blown highlights in the center from cheap flash, dark murky edges.
  Color shift toward magenta in midtones.
  Slight horizontal scan lines from bad development.
  One small light leak on the upper-right corner (red-orange glow).

CAPTION AREA (bottom white strip, messy handwritten style):
  "VNVNC.RU" — left                    "[time from personality context] МСК" — right
  "20.02–22.02  Конюшенная 2В" — centered below

VIBE: The Hangover. If you were there, you know. If you weren't — look at this.

VERTICAL 9:16 format.""",

    """МАЛЬЧИШНИК — ANALOG EVIDENCE PHOTO (VERTICAL 9:16)

Police evidence photo but make it fashion. Or rather — party evidence.
Someone's gonna show their kids this photo and say "I was young."

POLAROID LAYOUT (white frame border):

TOP HEADER on white border: "МАЛЬЧИШНИК" — block stamp letters

PHOTO ZONE (main image):
  Person from reference photo mid-celebration — maximum energy moment.
  They look like they've been awake for 18 hours and are proud of it.
  Behind them: real nightclub interior. Dark, smoky, colored spotlights,
  drinks, other people blurred in the background.
  ABSOLUTE LIKENESS — draw the exact person from the photo.
  Same face structure, same hair, same clothes. Make them recognizable.
  The camera caught them at their most alive and most chaotic.

ANALOG QUALITY:
  Overexposed highlights (especially faces hit by flash).
  Kodak Gold 200 warmth — golden amber tones dominating.
  Scratchy film grain — thick, visible, beautiful.
  Slight vignette at all four corners.
  Color fringing (chromatic aberration) at high-contrast edges.
  One light streak across a corner — accidental but iconic.

BOTTOM CAPTION (white Polaroid strip, handwritten):
  "VNVNC.RU" · "[time from personality context] МСК"
  "20.02–22.02  ·  Конюшенная 2В"

FEELING: The morning after. But the photo from the night before.

VERTICAL 9:16 format.""",
]

# МАЛЬЧИШНИК SQUARE VARIATIONS — 1:1 for LED display
MALCHISHNIK_SQUARE_VARIATIONS = [
    """МАЛЬЧИШНИК — DISPOSABLE CAMERA PARTY SHOT (SQUARE 1:1)

Raw disposable camera energy. Shot by someone who definitely shouldn't
have been holding a camera. Kodak FunSaver or similar.

SQUARE POLAROID (thin white border all sides):

PHOTO (fills most of frame):
  Person(s) from reference photo in full party chaos.
  Flash-blown faces, drunk energy, genuine emotion.
  Real nightclub/bar behind them — colored lights, dark walls.
  DRAW THE ACTUAL PEOPLE from the photo — real faces, real clothes.
  Everyone visible appears. Classic Hangover-movie group shot energy.

ANALOG LOOK:
  Heavy film grain. Blown flash center. Warm amber/yellow color push.
  Slight motion blur at edges. Film vignette corners.
  Chemical color shift — slightly warm/overcooked.

CORNER STAMP (small, bottom-right area of frame):
  "МАЛЬЧИШНИК" on top line
  "VNVNC.RU  20.02–22.02" on bottom line

Not photorealistic — illustrated analog photography aesthetic.
SQUARE 1:1 format.""",

    """МАЛЬЧИШНИК — FILM PHOTO MOMENT (SQUARE 1:1)

That one photo from the night that makes everyone say "send it to me."

SQUARE FRAME:
  Person from reference in their finest chaotic moment.
  Genuine expression — laughing, surprised, toasting, lost in it.
  Nightclub atmosphere behind them — authentic venue, moody lighting.
  REAL LIKENESS — must look like the actual person from the photo.

FILM AESTHETIC:
  Fujifilm disposable look. Grainy, pushed warm, slightly overexposed.
  Strong center flash bloom. Slight red-eye possible.
  Film edge burn (orange at corners). Chemical grain texture.

BRANDING (integrated into film border, small):
  "МАЛЬЧИШНИК  20.02–22.02"
  "VNVNC.RU  Конюшенная 2В"

SQUARE 1:1 format.""",
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

# Y2K VARIATIONS - 2000s era character portrait with AI creative freedom
Y2K_VARIATIONS = [
    """BLACK AND WHITE portrait of this person as a 2000s CHARACTER.
Based on their personality traits, transform them into an authentic early 2000s archetype.
AI HAS CREATIVE FREEDOM to choose the subculture that fits best:
- emo kid with side bangs and band tees
- raver with glow sticks and pacifier
- rapper with oversized jersey and bling
- pop princess with butterfly clips
- gamer with Xbox controller
- skater with baggy jeans
- scene kid with raccoon stripes
Pick what fits THIS person's vibe. Draw them in that style.
Background elements: Nokia 3310, ICQ flower, Windows XP hills, CD-ROM, flip phone.
Text: their archetype in RUSSIAN (all lowercase or ALL CAPS - your choice) + "VNVNC 2000s"
Bold ink illustration style, nostalgic millennium energy. Square aspect ratio.""",

    """BLACK AND WHITE portrait transforming this person into a Y2K ICON.
You decide what 2000s character they become based on their appearance and energy:
Could be a nu-metal fan, a pop punk kid, a hip-hop head, a techno raver,
a mall goth, a preppy teen, a skater, a scene queen - whatever fits THEM.
Style them with era-appropriate fashion: low-rise jeans, frosted tips, platform shoes,
butterfly clips, chain wallets, oversized hoodies, or whatever matches the archetype.
Add 2000s props: MP3 player, flip phone, MSN messenger, early internet vibes.
Text: character type in RUSSIAN + "VNVNC 2000s" banner.
Thick black ink lines, white background, nostalgic early internet aesthetic. Square aspect ratio.""",

    """BLACK AND WHITE 2000s TRANSFORMATION portrait!
Look at this person and decide what millennium character they'd be:
- The answers to their quiz suggest their personality
- Transform them into the 2000s archetype that matches
Could be emo, scene, raver, skater, hip-hop, pop star, gamer, punk, goth...
AI DECIDES based on their vibe. No fixed categories - be creative!
Draw them with signature 2000s elements: chunky highlights, band merch,
cargo pants, platform sneakers, studded belts, wallet chains...
Background: early 2000s tech (CRT monitor, dial-up, ICQ, MSN, Winamp)
Include "VNVNC 2000s" text in decorative early-internet style.
High contrast ink drawing, millennium nostalgia. Square aspect ratio.""",

    """BLACK AND WHITE portrait - НУЛЕВЫЕ (Y2K) CHARACTER REVEAL!
This person answered questions about 2000s culture. Based on their answers:
Transform them into their 2000s alter ego.
AI picks the subculture - could be anything from that era:
Russian: тусовщик, эмо, рэпер, гот, панк, геймер, рейвер, скейтер
International: emo, scene, punk, goth, raver, skater, hip-hop, pop
Draw them fully styled for their chosen tribe.
Props: Motorola RAZR, iPod mini, PS2, DDR, LiveJournal vibes.
Russian archetype label + "VNVNC 2000s" branding.
Bold graphic style, pure black ink on white. Square aspect ratio.""",
]

# BAD SANTA VARIATIONS - Naughty/nice verdict with adult humor
BAD_SANTA_VARIATIONS = [
    """BLACK AND WHITE portrait as a BAD SANTA VERDICT!
Draw this person in a comedic Santa-related scenario.
If they're NICE: reluctant Santa gives them a gift, sarcastic halo, "too good to be true" energy
If they're NAUGHTY: coal, drunk Santa judgment, middle finger optional, stamp of disapproval
Adult humor OK - this is R-rated Bad Santa movie vibes, not mall Santa.
Russian text verdict in BOLD (could be praise or roast depending on result).
Add "VNVNC BAD SANTA 2026" branding.
Sketch comedy energy, thick ink lines, white background. Square aspect ratio.""",

    """BLACK AND WHITE BAD SANTA JUDGMENT portrait!
Based on their quiz answers, render the verdict:
NICE LIST: Gift-receiving pose, skeptical Santa in background muttering curses,
ironic halo, "серьёзно?" Santa expression, they somehow passed
NAUGHTY LIST: Coal pile, crossed-out gifts, Santa's middle finger salute,
"ЗАСРАНЕЦ" stamp, they blew it
Billy Bob Thornton Bad Santa energy - drunk, rude, but funny.
Russian verdict text + "VNVNC BAD SANTA 2026" banner.
Bold comic style, adult humor, high contrast ink. Square aspect ratio.""",

    """BLACK AND WHITE portrait - ПЛОХОЙ САНТА ПРИГОВОР!
Comedic Santa verdict scene based on their naughty/nice score:
FOR WINNERS (nice): Begrudging gift, sarcastic compliment in Russian,
Santa can't believe they actually deserve it, suspicious halo
FOR LOSERS (naughty): Dramatic coal pile, Russian profanity (жопа, сука level),
Santa's disappointed judgment, "УГОЛЬ" stamp
Adult comedy style - think Bad Santa movie, not Coca-Cola Santa.
Include "VNVNC BAD SANTA 2026" in festive-ironic style.
Thick black lines, sketch comedy aesthetic. Square aspect ratio.""",
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
    # PHOTOBOOTH MODE - 9:16 vertical photo booth for label printing
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH: "PHOTOBOOTH_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # PHOTOBOOTH SQUARE MODE - 1:1 square photo booth for LED display
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SQUARE: "PHOTOBOOTH_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH VENICE MODE - 9:16 vertical TRIP:VENICE carnival theme
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_VENICE: "TRIPVENICE_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH VENICE SQUARE MODE - 1:1 square TRIP:VENICE for LED display
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_VENICE_SQUARE: "TRIPVENICE_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH LOVE IN THE AIR MODE - 9:16 vertical Valentine's theme
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR: "LOVEINTHEAIR_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH LOVE IN THE AIR SQUARE MODE - 1:1 square Valentine's for LED
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR_SQUARE: "LOVEINTHEAIR_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH МАЛЬЧИШНИК MODE - 9:16 vertical Hangover bachelor party theme
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_MALCHISHNIK: "MALCHISHNIK_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH МАЛЬЧИШНИК SQUARE MODE - 1:1 square bachelor party for LED
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_MALCHISHNIK_SQUARE: "MALCHISHNIK_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # Y2K MODE - 2000s era character portrait (uses Y2K_VARIATIONS)
    # =========================================================================
    CaricatureStyle.Y2K: "Y2K_VARIATION",  # Will be replaced with random variation

    # =========================================================================
    # BAD SANTA MODE - Naughty/nice verdict (uses BAD_SANTA_VARIATIONS)
    # =========================================================================
    CaricatureStyle.BAD_SANTA: "BAD_SANTA_VARIATION",  # Will be replaced with random variation
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
                "PHOTOBOOTH_SQUARE_VARIATION": PHOTOBOOTH_SQUARE_VARIATIONS,
                "TRIPVENICE_VARIATION": TRIPVENICE_VARIATIONS,
                "TRIPVENICE_SQUARE_VARIATION": TRIPVENICE_SQUARE_VARIATIONS,
                "LOVEINTHEAIR_VARIATION": LOVEINTHEAIR_VARIATIONS,
                "LOVEINTHEAIR_SQUARE_VARIATION": LOVEINTHEAIR_SQUARE_VARIATIONS,
                "MALCHISHNIK_VARIATION": MALCHISHNIK_VARIATIONS,
                "MALCHISHNIK_SQUARE_VARIATION": MALCHISHNIK_SQUARE_VARIATIONS,
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
                "Y2K_VARIATION": Y2K_VARIATIONS,
                "BAD_SANTA_VARIATION": BAD_SANTA_VARIATIONS,
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

            # Determine if this style should be full color (photobooth) or B&W (thermal print styles)
            is_color_style = style in (
                CaricatureStyle.PHOTOBOOTH,
                CaricatureStyle.PHOTOBOOTH_SQUARE,
                CaricatureStyle.PHOTOBOOTH_VENICE,
                CaricatureStyle.PHOTOBOOTH_VENICE_SQUARE,
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR_SQUARE,
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK_SQUARE,
            )
            is_venice_style = style in (
                CaricatureStyle.PHOTOBOOTH_VENICE,
                CaricatureStyle.PHOTOBOOTH_VENICE_SQUARE,
            )
            is_loveintheair_style = style in (
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR_SQUARE,
            )
            is_malchishnik_style = style in (
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK_SQUARE,
            )

            if is_malchishnik_style:
                color_instruction = """- FULL COLOR — analog film palette: pushed warm yellows/ambers, boosted reds, slight green in shadows
- Disposable camera / Polaroid aesthetic — heavy film grain, blown center flash, chemical color shift
- Overexposed highlights, underexposed dark corners, light leaks at edges (orange/red burn)
- Authentic party photography feel — NOT photorealistic, illustrated analog photography"""
            elif is_loveintheair_style:
                color_instruction = """- FULL COLOR — CREAM, BLUSH PINK, ROSE, CORAL, WARM SKIN TONES palette
- Warm illustrated portrait style — clean bold outlines, flat warm color fills
- Valentine's Day card with hearts, roses, love letters
- Modern greeting card / webtoon portrait quality, polished and attractive"""
            elif is_venice_style:
                color_instruction = """- FULL COLOR — GOLD, BURGUNDY, PURPLE, BLACK palette
- High-quality 3D rendered characters like The Sims 4 or Pixar
- Venetian carnival atmosphere with masks, candles, fog
- Premium art quality, cinematic lighting, NOT photorealistic"""
            elif is_color_style:
                color_instruction = """- FULL COLOR — RED AND BLACK ONLY palette
- Chromatic aberration on edges, super wide angle distortion, heavy film grain
- Shot like raw analog concert photography — textured, deep, authentic
- High quality artistic illustration, NOT pixel art, NOT photorealistic"""
            else:
                color_instruction = """- BLACK AND WHITE ONLY - pure black ink on white background, high contrast
- NO colors, NO grayscale shading - just black and white like a thermal print
- High quality artistic illustration, NOT pixel art, NOT photorealistic"""

            prompt = f"""Create an artistic portrait OF THIS EXACT PERSON from the reference photo.

CRITICAL REQUIREMENTS:
- This must capture THE PERSON IN THE PHOTO - their likeness is essential
- Recognize their distinctive features and incorporate them naturally
{color_instruction}
- TEXT LANGUAGE RULES (CRITICAL!!!):
  * The brand name "VNVNC" must ALWAYS stay in ENGLISH letters: V-N-V-N-C
  * NEVER translate or transliterate VNVNC to Russian (НЕ писать ВНВНЦ или что-то подобное!)
  * All OTHER text (labels, annotations, decorations) must be in RUSSIAN, ALL CAPS
  * NEVER add any year (2024, 2025, 2026, etc.) - just "VNVNC" alone if adding branding
  * Example: "VNVNC" is correct, "ВНВНЦ" or "VNVNC 2026" is WRONG!
{personality_hint}
{style_prompt}

The result should be recognizable as THIS specific person, transformed artistically.
UNIQUENESS TOKEN: {uniqueness_token}
"""

            # Determine aspect ratio based on style
            # Photobooth uses 9:16 vertical format for better label layout
            if style in (CaricatureStyle.PHOTOBOOTH, CaricatureStyle.PHOTOBOOTH_VENICE, CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR, CaricatureStyle.PHOTOBOOTH_MALCHISHNIK):
                aspect_ratio = "9:16"
            else:
                aspect_ratio = "1:1"

            # Send photo directly to Gemini 3 Pro Image Preview
            # The model understands to use the photo as reference
            if is_malchishnik_style:
                image_style = "Analog disposable camera photography, Polaroid film photo, heavy film grain, blown flash, warm pushed colors, party chaos, Hangover movie aesthetic"
            elif is_loveintheair_style:
                image_style = "Warm illustrated Valentine's card portrait, clean bold outlines, flat warm colors, cream and blush pink, hearts and roses, modern greeting card style"
            elif is_venice_style:
                image_style = "High-quality 3D Sims-style character render, Venetian carnival masks, gold and burgundy, cinematic lighting, dark atmosphere"
            elif is_color_style:
                image_style = "Raw analog concert photography, red and black only, chromatic aberration, film grain, wide angle distortion"
            else:
                image_style = "Black and white illustration, high contrast ink drawing, thermal printer style"

            image_data = await self._client.generate_image(
                prompt=prompt,
                reference_photo=reference_photo,
                photo_mime_type="image/jpeg",
                aspect_ratio=aspect_ratio,
                image_size="1K",  # Use 1K resolution
                style=image_style,
            )

            if image_data:
                # For photobooth styles, keep full resolution from Gemini (uploaded to S3 gallery)
                # Only downscale for non-photobooth styles (thermal printer / LED display)
                if is_color_style:
                    # Keep original resolution, just ensure PNG format
                    from PIL import Image
                    img = Image.open(BytesIO(image_data))
                    img = img.convert("RGB")
                    output = BytesIO()
                    img.save(output, format="PNG")
                    processed = output.getvalue()
                    actual_w, actual_h = img.size
                else:
                    processed = await self._process_for_display(image_data, size, color=False)
                    actual_w, actual_h = size
                return Caricature(
                    image_data=processed,
                    style=style,
                    width=actual_w,
                    height=actual_h,
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
        color: bool = False,
    ) -> bytes:
        """Process the generated image for display.

        For B&W styles: converts to grayscale and resizes.
        For color styles: keeps full color, just resizes.

        Args:
            image_data: Original image bytes
            target_size: Target dimensions
            color: If True, keep full color (photobooth). If False, convert to grayscale.

        Returns:
            Processed image bytes (RGB)
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(image_data))

            if not color:
                # Convert to grayscale for B&W styles (thermal printer)
                img = img.convert("L")

            # Ensure RGB for display compatibility
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
