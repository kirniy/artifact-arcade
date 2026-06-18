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
    PHOTOBOOTH_FEYPHORIA = "photobooth_feyphoria"  # 9:16 vertical - Enchanted fairy forest theme
    PHOTOBOOTH_FEYPHORIA_SQUARE = "photobooth_feyphoria_square"  # 1:1 square - Enchanted fairy forest theme
    PHOTOBOOTH_FIESTA = "photobooth_fiesta"  # 9:16 vertical - Realistic Spanish party theme
    PHOTOBOOTH_FIESTA_SQUARE = "photobooth_fiesta_square"  # 1:1 square - Realistic Spanish party theme
    PHOTOBOOTH_BIGCITYLIFE = "photobooth_bigcitylife"  # 9:16 vertical - 90s NYC graffiti theme
    PHOTOBOOTH_BIGCITYLIFE_SQUARE = "photobooth_bigcitylife_square"  # 1:1 square - 90s NYC graffiti theme
    PHOTOBOOTH_BRAINROT = "photobooth_brainrot"  # 9:16 vertical - cringe-party brainrot mode
    PHOTOBOOTH_BRAINROT_SQUARE = "photobooth_brainrot_square"  # 1:1 square - cringe-party brainrot mode
    PHOTOBOOTH_WEDDING = "photobooth_wedding"  # 9:16 vertical - Russian wedding postcard mode
    PHOTOBOOTH_WEDDING_SQUARE = "photobooth_wedding_square"  # 1:1 square - Russian wedding postcard mode
    PHOTOBOOTH_WHATSAPP = "photobooth_whatsapp"  # 9:16 vertical - grandma WhatsApp postcard mode
    PHOTOBOOTH_WHATSAPP_SQUARE = "photobooth_whatsapp_square"  # 1:1 square - grandma WhatsApp postcard mode
    PHOTOBOOTH_SLAVIC_SOUL = "photobooth_slavic_soul"  # 9:16 vertical - slavic soul luxury mode
    PHOTOBOOTH_SLAVIC_SOUL_SQUARE = "photobooth_slavic_soul_square"  # 1:1 square - slavic soul mode
    PHOTOBOOTH_SLAVIC_TALES = "photobooth_slavic_tales"  # 9:16 vertical - slavic fairy-tale mode
    PHOTOBOOTH_SLAVIC_TALES_SQUARE = "photobooth_slavic_tales_square"  # 1:1 square - slavic fairy-tale mode
    PHOTOBOOTH_BANYA_CHIC = "photobooth_banya_chic"  # 9:16 vertical - decadent bathhouse mode
    PHOTOBOOTH_BANYA_CHIC_SQUARE = "photobooth_banya_chic_square"  # 1:1 square - decadent bathhouse mode
    PHOTOBOOTH_VNVNC_BDAY = "photobooth_vnvnc_bday"  # 9:16 vertical - VNVNC birthday premium poster mode
    PHOTOBOOTH_VNVNC_BDAY_SQUARE = "photobooth_vnvnc_bday_square"  # 1:1 square - VNVNC birthday premium poster mode
    PHOTOBOOTH_CIRCUS_MAXIMUS = "photobooth_circus_maximus"  # 9:16 vertical - creepy circus mode
    PHOTOBOOTH_CIRCUS_MAXIMUS_SQUARE = "photobooth_circus_maximus_square"  # 1:1 square - creepy circus mode
    PHOTOBOOTH_MTV_NIGHT = "photobooth_mtv_night"  # 9:16 vertical - glossy MTV night poster mode
    PHOTOBOOTH_MTV_NIGHT_SQUARE = "photobooth_mtv_night_square"  # 1:1 square - glossy MTV night poster mode
    PHOTOBOOTH_SHADOW_KINGDOM = "photobooth_shadow_kingdom"  # 9:16 vertical - gothic shadow kingdom mode
    PHOTOBOOTH_SHADOW_KINGDOM_SQUARE = "photobooth_shadow_kingdom_square"  # 1:1 square - gothic shadow kingdom mode
    PHOTOBOOTH_CANDY_SHOP = "photobooth_candy_shop"  # 9:16 vertical - white candy shop luxury mode
    PHOTOBOOTH_CANDY_SHOP_SQUARE = "photobooth_candy_shop_square"  # 1:1 square - white candy shop luxury mode
    PHOTOBOOTH_STREET_HEAT = "photobooth_street_heat"  # 9:16 vertical - west coast polaroid mode
    PHOTOBOOTH_STREET_HEAT_SQUARE = "photobooth_street_heat_square"  # 1:1 square - west coast polaroid mode
    PHOTOBOOTH_OFFICE_CORE = "photobooth_office_core"  # 9:16 vertical - pixelated office-core mode
    PHOTOBOOTH_OFFICE_CORE_SQUARE = "photobooth_office_core_square"  # 1:1 square - pixelated office-core mode
    PHOTOBOOTH_2K17 = "photobooth_2k17"  # 9:16 vertical - pixelated 2K17 street-style mode
    PHOTOBOOTH_2K17_SQUARE = "photobooth_2k17_square"  # 1:1 square - pixelated 2K17 street-style mode
    PHOTOBOOTH_SUMMER_CAMP = "photobooth_summer_camp"  # 9:16 vertical - pixelated summer sports camp mode
    PHOTOBOOTH_SUMMER_CAMP_SQUARE = "photobooth_summer_camp_square"  # 1:1 square - pixelated summer sports camp mode
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
# OUTPUT: 9:16 VERTICAL aspect ratio — fixed prompt, no random styling drift
# STYLE: Premium 2D club-poster illustration, wide-angle, dark paper, visible venue
# DATES: 27.03-29.03  VENUE: КОНЮШЕННАЯ 2В  BRAND: VNVNC.RU
# NOTE: Moscow time is passed via personality_context and must appear in footer
PHOTOBOOTH_VARIATIONS = [
    """BOILING ROOM — GRAPHIC CLUB POSTER PHOTO BOOTH (VERTICAL 9:16)

Create a VERTICAL 9:16 photo booth strip with 4 illustrated frames in a 2×2 grid on dark textured paper.

ABSOLUTE #1 PRIORITY — EXACT LIKENESS, EXACT CLOTHING, EXACT GROUP:
- These must be THE EXACT PEOPLE from the source photo in all 4 frames
- Same faces, same facial structure, same hairstyle, same hair color, same glasses, same facial hair, same makeup, same body proportions
- SAME clothing, SAME accessories, SAME styling from the source photo
- Preserve ANY text, logos, prints, or graphics on clothing letter-for-letter
- If the source photo is a group shot, include ALL people from the source photo in EVERY frame
- Do NOT replace them with generic club characters, do NOT beautify beyond recognition

CRITICAL TEXT RULES:
- ONLY these texts allowed: "BOILING ROOM", "27.03-29.03", "VNVNC.RU", the time from personality_context, "КОНЮШЕННАЯ 2В"
- NO OTHER TEXT WHATSOEVER — no captions, no labels, no words, no letters anywhere else
- "VNVNC.RU" must stay exact Latin text in tall condensed white letters inside a thin red rectangular border
- The timestamp must come from personality_context exactly as written
- NO per-frame timestamps. NO "МСК". NO year. The date appears once at the top only

STYLE — PREMIUM DRAWN CLUB POSTER ILLUSTRATION:
- Strictly a DRAWN / ILLUSTRATED image, NOT photorealistic, NOT 3D, NOT a vinyl toy
- Premium 2D editorial club-poster art with bold black ink lines, red and white highlights, subtle halftone texture
- High-end underground flyer energy, clean graphic shapes, confident line work, stylish but controlled
- Chromatic aberration, super wide angle, film grain, analog textures
- Faces must stay highly recognizable while being rendered as polished illustration
- Attractive and cool, but still unmistakably the real people from the source photo

COMPOSITION / CAMERA:
- Super wide-angle lens feel, around 18-24mm
- Show enough of the scene so the venue remains visible behind the people
- Do NOT crop too tight on faces; include upper body / mid-shot framing
- Keep strong perspective, ceiling lines, room depth, and club-space geometry

BACKGROUND — SHOW WHAT IS BEHIND THE PEOPLE TOO:
- Show the actual venue/background elements visible behind the people in the source photo
- Preserve the real room structure: lights, walls, mirrors, railings, ceiling lines, LED strips, furniture, architectural shapes
- Convert the real background into the same red/black illustrated style instead of deleting it
- Background must stay visible and readable in every frame, not empty black, not abstract smoke only
- Club atmosphere is welcome, but the real scene behind the people must still be present

DARK PRINTED CARD:
- Entire strip printed on black / dark charcoal textured paper
- Rich paper grain, matte finish, subtle wear, tactile premium poster-stock feel
- Dark borders between frames, no white paper anywhere
- Art and typography look screen-printed on top of the dark paper

COLOR PALETTE:
- Mostly black, deep red, white, chrome silver, and true skin tones
- Red neon accents and white highlights only where needed
- Clean, stylish, high contrast; NOT muddy, NOT sweaty, NOT grimy
- Visible film grain, analog print texture, and slight chromatic fringe on edges

4 FRAMES — same exact people, different energy:
- Frame 1: Direct look, confident, venue clearly visible behind them
- Frame 2: Laughing / candid energy, same group all present, dynamic wide-angle perspective
- Frame 3: Calmer music moment, relaxed pose, background still visible
- Frame 4: Side angle or over-shoulder variation, all people still included if it is a group photo

TOP:
- "BOILING ROOM" in beautiful metallic chrome letters, polished silver / chromed type on the dark paper
- "27.03-29.03" below in clean condensed type

BOTTOM LEFT:
- exact text "VNVNC.RU" — tall condensed white letters inside thin red rectangular border

BOTTOM RIGHT:
- time from personality_context, exact digits as written

SMALL BELOW TIME:
- exact text "КОНЮШЕННАЯ 2В" in ALL CAPS

9:16 VERTICAL. Dark printed club-poster photo booth strip with visible venue background and exact likeness.""",
]

# PHOTOBOOTH SQUARE VARIATIONS - BOILING ROOM theme 1:1 for LED display
# OUTPUT: 1:1 SQUARE aspect ratio for 128x128 LED display preview
# STYLE: Red & black only, chromatic aberration, wide angle, analog texture
PHOTOBOOTH_SQUARE_VARIATIONS = [
    """BOILING ROOM — GRAPHIC CLUB POSTER BOOTH (SQUARE 1:1)

Create a SQUARE 1:1 photo booth grid with 4 illustrated frames in a 2×2 layout.

LIKENESS AND CLOTHING ARE THE TOP PRIORITY:
- These must be the exact people from the source photo
- Same faces, same hair, same clothing, same accessories, same proportions
- Preserve all clothing text and logos letter-for-letter
- If the source photo is a group shot, include ALL people in every frame

STYLE:
- Strictly DRAWN / ILLUSTRATED premium 2D club-poster art, not a photo, not 3D
- Bold black lines, red and white highlights, subtle halftone print texture
- High-end underground flyer aesthetic on dark textured paper
- Chromatic aberration, super wide angle, film grain, analog textures

BACKGROUND:
- Show the real scene behind the people from the source photo
- Keep venue geometry, lights, walls, ceiling lines, and room depth visible
- Convert the real background into the same red/black illustrated style

COMPOSITION:
- Wide-angle lens feel, not tight portrait crops
- People plus visible environment in every frame

COLOR:
- Mostly black, deep red, white, chrome silver, and true skin tones
- Clean, stylish, high contrast, not muddy

4 FRAMES:
- Same exact people in all 4 frames, slight expression / angle changes only

BRANDING:
- exact text "VNVNC" in tall condensed white letters inside a thin red rectangular border

SQUARE 1:1. Dark printed club-poster illustration with visible venue background and exact likeness.""",
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
    """МАЛЬЧИШНИК — POLAROID PHOTO (VERTICAL 9:16)

CRITICAL: LIKENESS IS THE TOP PRIORITY.
Create a Polaroid photo of THESE EXACT PEOPLE from the reference photo.
Maintain their exact faces, hairstyles, and clothing. No generic party characters.
If multiple people are in the reference photo, include all of them exactly as they are.

AESTHETIC — HANGOVER MOVIE STYLE:
- CHAOTIC party energy: people caught mid-action, unposed, candid nightclub moment
- Add FUN CHAOS around the frame: marker doodles, scribbles, hearts, stars, arrows, squiggles
- Handwritten text on the white strip in messy marker style
- Someone might be making a silly face, someone drinking, someone hugging
- Authentic Polaroid: thick white border at bottom with room for doodles
- Lighting: Strong center flash, dark murky background, colored club lights
- Film Look: Heavy grain, warm amber/yellow tones, light leaks, vintage shift
- NO TEXT inside the photo area, only on the white strip

MARKER DOODLES ON WHITE STRIP:
- Add fun hand-drawn elements: hearts, stars, arrows, smiley faces, question marks
- Write "VNVNC.RU" in messy marker handwriting on the left
- Write the time (from personality context) on the right
- "20.02–22.02 · Конюшенная 2В" scribbled below
- Make it look like friends decorated it with markers!

VERTICAL 9:16 format.""",

    """МАЛЬЧИШНИК — CANDID PARTY SNAPSHOT (VERTICAL 9:16)

LIKENESS FIRST:
This must be THIS EXACT person (or people) from the reference photo.
Same face, same hair, same nose, same clothes. Recognize them instantly.
Everyone in the reference photo must appear in this Polaroid.

STYLE — WILD HANGOVER PARTY VIBES:
- Chaotic party energy: mid-laugh, mid-toast, mid-hug, caught off-guard
- Real nightclub environment behind them with colored lights
- Polaroid frame with white borders (thick at bottom for doodles)
- Add RANDOM FUN OBJECTS if fitting: drinks in hands, party props, weird angles
- Heavy film grain, blown flash, warm amber color push
- Someone's eyes half-closed, someone photobombing, pure chaos energy

MARKER DOODLES ON WHITE STRIP (handwritten messy style):
- Add arrows, hearts, stars, squiggles, exclamation marks around the edges
- "VNVNC.RU" on the left in marker
- Time (from context) on the right
- "20.02–22.02 Конюшенная 2В" scribbled below
- Random doodles: lightning bolts, crowns, devil horns drawn on someone
- Make it look decorated by drunk friends with sharpies!

VERTICAL 9:16 format.""",

    """МАЛЬЧИШНИК — LEGENDARY NIGHT POLAROID (VERTICAL 9:16)

CRITICAL LIKENESS:
These must be THE EXACT PEOPLE from the reference photo. Same faces, hair, clothes.
Include everyone visible in the original photo.

HANGOVER MOVIE ENERGY:
- Capture the CHAOS of a legendary bachelor party night
- Unposed, candid, caught-in-the-moment shots
- Wild expressions: laughing, shouting, making faces, doing shots
- Background: club lights, smoke, disco balls, pure party atmosphere
- Film effects: heavy grain, flash overexposure, warm pushed colors, light leaks

POLAROID STYLE:
- Classic Polaroid with thick white border at bottom
- Edges might be slightly bent/worn from being passed around
- White strip decorated with marker doodles and scribbles

MARKER MADNESS ON WHITE STRIP:
- "VNVNC.RU" written in drunk handwriting
- Time scribbled on the right
- "20.02-22.02 · Конюшенная 2В" below
- Random doodles everywhere: stars, hearts, arrows, "ЭТО БЫЛО ЭПИЧНО!", devil horns on people
- Make it look like everyone signed and decorated it!

VERTICAL 9:16 format.""",
]

# МАЛЬЧИШНИК SQUARE VARIATIONS — 1:1 for LED display
MALCHISHNIK_SQUARE_VARIATIONS = [
    """МАЛЬЧИШНИК — SQUARE POLAROID (1:1)

LIKENESS IS ESSENTIAL:
Capture THESE EXACT PEOPLE from the reference photo.
Exact same facial features, hair, and clothes. They must look like themselves.
Include everyone from the reference image.

HANGOVER STYLE:
- Chaotic party vibe: candid, unposed, caught mid-action
- Someone laughing, someone making a face, pure chaos energy
- High flash, dark murky background, club colored lights
- Warm analog film grain, light leaks, overexposed highlights
- White Polaroid border on all sides

MARKER DOODLES ON WHITE STRIP:
- "МАЛЬЧИШНИК" in messy marker handwriting
- "VNVNC.RU · 20.02–22.02" scribbled below
- Add fun doodles: hearts, stars, arrows, squiggles, smiley faces
- Make it look decorated by friends!

SQUARE 1:1 format.""",

    """МАЛЬЧИШНИК — EPIC NIGHT SQUARE (1:1)

CRITICAL LIKENESS:
This must be THE EXACT PEOPLE from the photo. Same faces, same features.

WILD PARTY ENERGY:
- Hangover movie chaos: mid-toast, mid-hug, photobomb
- Unposed, candid, legendary moment captured
- Club atmosphere: colored lights, smoke, party vibes
- Film look: heavy grain, blown flash, warm amber tones

POLAROID STYLE:
- Square with white borders, thick at bottom for doodles
- Marker scribbles all around: "МАЛЬЧИШНИК", stars, arrows
- "VNVNC.RU · 20.02–22.02" in drunk handwriting
- Random doodles: devil horns on someone, hearts, "ЭПИЧНО!"

SQUARE 1:1 format.""",
]


# =============================================================================
# ФЕЙФОРИЯ PHOTOBOOTH VARIATIONS - Enchanted fairy forest party theme
# =============================================================================
# OUTPUT: 9:16 VERTICAL aspect ratio - for label printing
# STYLE: Art Nouveau enchanted vector illustration, rose gold + emerald
# DATES: 06-08.03  VENUE: Конюшенная 2В  BRAND: VNVNC.RU
# NOTE: Moscow time is passed via personality_context and must appear in caption

FEYPHORIA_VARIATIONS = [
    """ФЕЙФОРИЯ — ENCHANTED DOLL PHOTO BOOTH (VERTICAL 9:16)

Create a VERTICAL photo booth strip (9:16 ratio) with 4 portraits of this person in a 2×2 grid on an aged, grungy card.

ABSOLUTE #1 PRIORITY — LIKENESS & CLOTHING:
- The person must look EXACTLY like the reference photo in ALL 4 frames
- SAME face, SAME hair, SAME clothing — including ANY text on clothing (preserve it letter-for-letter)
- The person's outfit, accessories, and every visible detail must match the original photo PRECISELY
- If multiple people in the photo, include ALL of them in every frame

RENDERING STYLE — VINYL COLLECTIBLE DOLL / 3D FIGURINE:
- Make the person look like a high-end vinyl collectible doll or action figure
- Smooth, slightly shiny plastic-like skin with subtle subsurface scattering
- Slightly enlarged eyes (10-15% bigger), refined features, perfect symmetry
- Think: Popmart blind box figure, Mighty Jaxx collectible, Japanese vinyl toy
- The rendering should feel 3D, volumetric, with soft studio-like lighting on the figure
- Hair should look like sculpted plastic hair (slightly stylized, smooth)
- Clothing should look like miniature real fabric on a doll

BACKGROUND — PRESERVE THE ORIGINAL SCENE:
- Keep the EXACT background from the original photo (the venue, lighting, interior)
- Do NOT replace with forest, outdoors, or any other environment
- ADD fairy enchantment elements OVER the existing scene:
  - Golden sparkle dust floating in the air
  - 2-3 tiny glowing flowers or vines growing from frame edges
  - Delicate butterfly silhouettes
  - Magical warm glow enhancement on existing lights
- Keep it subtle — the original vibe STAYS, just with fairy magic sprinkled in
- Do NOT add neon lights or change the existing lighting

CARD/BORDER — GRUNGY AGED POLAROID WITH DOODLES:
- Thick cream/off-white border around the photo grid — weathered, stained, aged paper
- Coffee stains, slight yellowing, crinkled edges
- Hand-drawn MARKER DOODLES covering the borders densely:
  - Flowers, ferns, vine tendrils, butterflies, tiny stars, leaf spirals
  - Drawn in dark forest green and rose-gold metallic ink
  - Confident, quick marker strokes — like someone doodled at the party
  - Some doodles bleed slightly into the photo frames

4 FRAMES — same doll-ified person, different expressions:
- Top-left: Confident direct look, slight smirk, golden sparkle dust
- Top-right: Big laugh, joyful, butterflies nearby
- Bottom-left: Relaxed cool pose, magical glow
- Bottom-right: Mysterious side angle, sparkles

TEXT:
- TOP on border: "ФЕЙФОРИЯ" in elegant rose-gold serif with tiny floral decorations on the letters (like roses and petals woven into the letterforms), "06-08.03" below in smaller text
- NO timestamps on individual frames
- BOTTOM on border: "VNVNC.RU" on the left in marker handwriting, time from personality context on the right, "Конюшенная 2В" below with flower doodles around it

9:16 VERTICAL. Vinyl doll 3D rendering on doodled aged Polaroid card.""",

    """ФЕЙФОРИЯ — FAIRY FIGURINE PHOTO BOOTH (VERTICAL 9:16)

Create a VERTICAL 9:16 photo booth strip — 4 portraits in a 2×2 grid on a grungy vintage card.

LIKENESS IS THE #1 RULE:
- Person must be INSTANTLY recognizable from the reference photo
- EXACT same face, hair, clothing — preserve ALL text on garments letter-by-letter
- If group photo, ALL people must appear in every frame
- Clothing texture, color, and details must match perfectly

3D PLASTIC DOLL STYLE:
- Render the person as a premium collectible vinyl figurine
- Smooth glossy plastic skin, slightly oversized expressive eyes
- Sculpted-looking hair with a plastic sheen
- Think: designer toy meets Barbie — recognizable person but doll-ified
- Soft volumetric 3D lighting, gentle rim light on the plastic surface
- NOT cartoon — still the real person, just with vinyl doll finish

BACKGROUND — KEEP ORIGINAL, ADD MAGIC:
- PRESERVE the actual background environment from the reference photo
- Same venue, same lighting, same atmosphere — do not replace
- Layer fairy elements ON TOP of what's already there:
  - Floating golden sparkle particles (fairy dust)
  - Small glowing wildflowers at edges
  - 1-2 butterfly silhouettes catching the light
  - Warm magical bloom on existing light sources
- Original scene must be clearly recognizable underneath the magic

AGED POLAROID WITH HAND-DRAWN DOODLES:
- Weathered cream paper border — stained, yellowed, worn corners
- DENSE hand-drawn marker doodles on every border surface:
  - Forest ferns, wildflowers, ivy vines, butterflies, stars, tiny leaves
  - Dark green ink + rose-gold metallic marker
  - Loose, confident sketch style — party vibes
  - Doodles sometimes overlap photo edges

4 FRAMES — different expressions of the same person:
- Frame 1: Direct confident gaze, warm smirk, sparkle dust
- Frame 2: Genuine big laugh, butterflies in air
- Frame 3: Chill/relaxed, enchanted glow on lights
- Frame 4: Cool mysterious angle, sparkles floating

TEXT:
- TOP: "ФЕЙФОРИЯ" in elegant rose-gold serif letters adorned with tiny roses and petals woven into the letterforms, "06-08.03" below
- NO timestamps on individual frames
- BOTTOM: "VNVNC.RU" left in marker, time from context on right, "Конюшенная 2В" scribbled below + flower doodles

9:16 VERTICAL. Premium vinyl figurine portraits on doodled vintage Polaroid!""",

    """ФЕЙФОРИЯ — COLLECTIBLE DOLL PHOTO BOOTH (VERTICAL 9:16)

VERTICAL 9:16 photo booth strip. 4 portraits, 2×2 grid, aged grungy card.

CRITICAL — LIKENESS AND CLOTHING FIRST:
- Person MUST look exactly like the reference photo in all 4 frames
- Same face shape, same hair, same clothing with ALL text preserved exactly
- Every detail from the original photo matters — accessories, colors, textures
- Group photos: include EVERYONE in every frame

STYLE — HIGH-END VINYL TOY / DESIGNER DOLL:
- Person rendered as a collectible designer vinyl doll
- Smooth plastic-finish skin with soft sheen and subsurface glow
- Eyes slightly enlarged, features refined but RECOGNIZABLE
- Hair has that sculpted, slightly glossy doll-hair look
- Clothes look like real miniature fabric draped on a figurine
- 3D volumetric feel — soft directional lighting, gentle shadows
- Think: Popmart x Mighty Jaxx premium collectible, NOT cheap toy

BACKGROUND — ORIGINAL SCENE + FAIRY DUST:
- Keep the REAL background from the photo — venue, lights, interior, everything
- Do NOT swap to a different environment
- Overlay subtle enchantment effects:
  - Golden fairy dust particles suspended in air
  - Tiny luminous flowers peeking from corners
  - Butterfly silhouettes in warm tones
  - Gentle magical glow on existing light sources
- Scene stays authentic — magic is an accent, not a replacement

GRUNGY CARD WITH MARKER ART:
- Thick aged cream border — paper texture, coffee rings, worn edges, yellowing
- Hand-drawn doodles EVERYWHERE on borders:
  - Ferns, wildflowers, vine curls, butterflies, small stars, leaves
  - Dark forest green + rose-gold metallic ink
  - Quick energetic marker style — like someone drew at the party
  - Some doodles creep into photo edges

4 FRAMES — different expressions:
- TL: Confident look, slight smile, golden sparkles
- TR: Big joyful laugh, butterflies
- BL: Relaxed pose, enchanted light glow
- BR: Cool side angle, sparkle particles

TEXT:
- TOP: "ФЕЙФОРИЯ" elegant rose-gold serif with floral decorations integrated into the letters (roses, petals, tiny vines on letterforms), "06-08.03" below
- NO timestamps on individual frames
- BOTTOM: "VNVNC.RU" left marker style, time from context on right, "Конюшенная 2В" below + flower doodles

9:16 VERTICAL. Designer doll 3D portraits on grungy doodled Polaroid card!""",
]

# ФЕЙФОРИЯ SQUARE VARIATIONS — 1:1 for LED display
FEYPHORIA_SQUARE_VARIATIONS = [
    """ФЕЙФОРИЯ — SQUARE DOLL BOOTH (1:1)

LIKENESS IS ESSENTIAL:
- The person must look EXACTLY like the reference photo in every frame
- Same face, hair, clothing — preserve ALL text on garments letter-by-letter
- If multiple people, include ALL of them

Create a SQUARE (1:1) photo booth grid with 4 portraits in a 2x2 layout.

3D VINYL DOLL STYLE:
- Person rendered as a premium collectible vinyl figurine
- Smooth glossy plastic skin, slightly oversized eyes, refined features
- Sculpted doll-like hair with plastic sheen
- Think: Popmart / Mighty Jaxx collectible — recognizable but doll-ified
- Soft 3D volumetric lighting, gentle rim light on plastic surface

BACKGROUND — KEEP ORIGINAL, ADD MAGIC:
- PRESERVE the actual background from the reference photo (venue, lighting, interior)
- Do NOT replace — just ADD subtle fairy elements on top:
  - Golden sparkle particles, tiny glowing flowers, butterfly silhouettes
  - Magical bloom on existing light sources
- Original scene stays — magic is accent only

GRUNGY AGED CARD WITH DOODLES:
- Weathered cream border with paper texture, coffee stains, worn edges
- Hand-drawn marker doodles on borders: flowers, ferns, vines, butterflies, stars
- Dark forest green + rose-gold metallic ink, confident marker strokes

4 FRAMES — different expressions of the same doll-ified person:
Frame 1: Confident gaze, sparkle dust
Frame 2: Laughing, butterflies
Frame 3: Relaxed, enchanted glow
Frame 4: Mysterious angle, sparkles

BRANDING: "VNVNC" tall condensed white letters in thin rose-gold rectangular border.

SQUARE 1:1. Vinyl doll 3D portraits on doodled grungy card!""",

    """ФЕЙФОРИЯ — FIGURINE SQUARE BOOTH (1:1)

LIKENESS IS TOP PRIORITY — person must be EXACTLY recognizable from reference photo.
Same clothing, same face, same hair. If multiple people, include ALL of them.

SQUARE 1:1 photo grid — 4 portraits in 2x2 layout.

STYLE: High-end vinyl collectible doll. Smooth plastic skin, slightly enlarged eyes,
sculpted hair. Designer toy aesthetic — Barbie meets Popmart. Still recognizable, just doll-ified.
3D volumetric feel with soft lighting and gentle shadows.

BACKGROUND: Keep the REAL background from the photo — same venue, same lights.
Add subtle fairy magic ON TOP: golden sparkle dust, tiny glowing flowers, butterflies.
Do NOT replace the environment.

CARD: Aged cream paper border with coffee stains, yellowing, worn edges.
Dense hand-drawn marker doodles: wildflowers, ferns, vines, butterflies, stars.
Dark green + rose-gold ink. Party doodle energy.

4 FRAMES — different expressions:
Frame 1: Direct confident look, sparkles
Frame 2: Genuine laugh, butterflies
Frame 3: Chill/relaxed, enchanted glow
Frame 4: Cool side angle, fairy dust

BRANDING: "VNVNC" condensed white in thin rose-gold border.

SQUARE 1:1 format. Designer doll portraits on grungy doodled card!""",
]


# FIESTA VARIATIONS - Realistic Spanish party style with elegant doodles
FIESTA_VARIATIONS = [
    """ФИЕСТА — FERIA POSTER PHOTO BOOTH (VERTICAL 9:16)

VERTICAL 9:16 photo booth strip. 4 portraits, 2x2 grid, tactile printed poster card.

CRITICAL — LIKENESS AND CLOTHING FIRST:
- Person MUST look exactly like the reference photo in all 4 frames
- Same face shape, same hair, same clothing with ALL text preserved exactly
- Every detail from the original photo matters — accessories, colors, textures
- Group photos: include EVERYONE in every frame

STYLE — HIGH-END EDITORIAL PHOTOREALISM:
- Premium realistic club portrait photography, not illustration and not 3D render
- Natural skin, real hair, real fabric, real eyes, no dollification
- Soft cinematic nightlife lighting with warm highlights and rich shadow contrast
- Think: luxury Spanish club photo booth meets feria poster campaign image

BACKGROUND — ORIGINAL SCENE + FIESTA GRAPHICS:
- Keep the REAL background from the photo — venue, lights, interior, everything
- Do NOT swap to a different environment
- The scenery behind the people must stay recognizable as the actual captured place
- Preserve the original composition depth, furniture, walls, light sources, and venue cues behind them
- Spanish styling may tint or decorate the scenery a bit warmer/redder, but the place itself must still clearly read as the same location from the source photo
- Overlay subtle Spanish fiesta elements:
  - Carnation petals, paper confetti, fan silhouettes, tile-border accents
  - Flamenco curve doodles, corrida-poster framing rhythm, feria ornament hints
  - Warm glow on existing light sources, but the real venue must remain visible
- Scene stays authentic — Spanish styling is an accent, not a replacement

PRINTED CARD WITH MARKER ART:
- Thick warm cream border with matte paper grain, poster wear, halftone dust, slight ink spread
- The whole piece must feel like a real physical printed photobooth strip / Polaroid card held in the hand
- Visible paper tooth, matte coating, micro-scratches, soft edge wear, slight curl, pressure marks from handling
- Tiny analog print imperfections are welcome: faint roller marks, subtle registration shift, soft chemical unevenness, gentle light scuffs
- Hand-drawn marker doodles on borders, as if someone decorated the printed photo by hand after it came out:
  - Flamenco flourishes, stars, swirls, carnations, fan shapes, confetti sparks
  - Andalusian tile corners, castanet icons, crescent comb shapes, matador-jacket braid patterns, bull-horn silhouette motifs, sunburst loops
  - Deep red, black ink, aged gold accent feeling
  - Quick expressive marker energy, like custom poster art done at the party
  - Some graphics may creep into the photo edges, but never cover faces
  - NO extra words or lettering inside the doodles

4 FRAMES — different expressions:
- TL: Direct confident gaze, cool half-smile, poster-star energy
- TR: Genuine laugh, warm movement, confetti accents
- BL: Relaxed pose, sensual club mood, soft carnation/petal details
- BR: Side angle, sharper corrida-poster confidence, dramatic light contrast

TEXT:
- ONLY these texts allowed: "ФИЕСТА", "13.03-14.03", "VNVNC.RU", the time from context, "КОНЮШЕННАЯ 2В"
- "ФИЕСТА" must be in RUSSIAN letters, large and unmistakable, styled like an elegant Spanish feria/corrida poster headline
- "ФИЕСТА" should not be plain flat text: integrate it into a long Spanish-flag ribbon / banner / fabric strip motif
- The title can sit on, be woven through, or be cut out from a waving red-yellow-red flag-like strip behind it
- The effect should feel like Spanish flag material incorporated into the headline design, not just colored letters
- "VNVNC.RU" must be exact Latin text as plain letters, not a symbol, not an emblem, not a rewritten word
- NEVER distort, transliterate, or mutate "VNVNC.RU" into anything like "VNAVNC" or Cyrillic variants
- TOP: "ФИЕСТА" in bold Spanish poster lettering with subtle feria/corrida rhythm, "13.03-14.03" below
- NO timestamps on individual frames
- BOTTOM on border: exact text "VNVNC.RU" on the left in stylish marker lettering, time from context on the right, "КОНЮШЕННАЯ 2В" below with carnation / flamenco doodles

9:16 VERTICAL. Premium Spanish feria poster realism on a tactile doodled photobooth card!""",
]


# FIESTA SQUARE VARIATIONS - 1:1 for LED display
FIESTA_SQUARE_VARIATIONS = [
    """ФИЕСТА — SQUARE FERIA POSTER BOOTH (1:1)

LIKENESS IS ESSENTIAL:
- The person must look EXACTLY like the reference photo in every frame
- Same face, hair, clothing — preserve ALL text on garments letter-by-letter
- If multiple people, include ALL of them

Create a SQUARE (1:1) photo booth grid with 4 portraits in a 2x2 layout.

EDITORIAL REALISM:
- Premium realistic club portrait photography, not illustration and not toy-like
- Natural skin, true facial structure, realistic hair, real fabrics
- Warm Spanish nightlife grading with deep red, paprika, olive, cream, and aged-gold accents

BACKGROUND — KEEP ORIGINAL, ADD SPANISH DETAIL:
- PRESERVE the actual background from the reference photo
- Do NOT replace it
- The scenery behind the people must remain recognizable as the real captured venue
- Preserve the same room cues, lighting layout, walls, decor, and spatial depth from the source
- Spanish red/corrida styling can be layered onto the scenery, but the background must still read as the same place
- Add subtle fiesta graphics on top:
  carnation petals, fan silhouettes, tile-border accents, flamenco curve motifs, confetti sparks
- Original scene stays — Spanish styling is accent only

PRINTED CARD:
- Warm cream poster border with matte paper texture, halftone dust, slight ink spread
- The object should feel like a real printed photobooth card / Polaroid square with tactile physical presence
- Add paper tooth, matte coating, subtle edge wear, tiny handling scuffs, faint print-process imperfections
- Hand-drawn marker doodles on the printed photo border:
  carnations, stars, swirls, fan shapes, corrida-poster flourishes,
  Andalusian tile corners, castanet icons, comb shapes, matador braid motifs, bull-horn silhouette curves
- Stylish and graphic, never messy
- NO words inside doodles, only shapes and ornament

4 FRAMES — different expressions of the same real person:
Frame 1: Confident gaze, poster-star energy
Frame 2: Genuine laugh, movement
Frame 3: Relaxed warm club mood
Frame 4: Side angle, dramatic confidence

TEXT RULES:
- ONLY these texts allowed: "ФИЕСТА", "13.03-14.03", "VNVNC.RU", the time from context, "КОНЮШЕННАЯ 2В"
- "ФИЕСТА" must be in RUSSIAN letters only, styled like a bold Spanish feria/corrida poster title
- "ФИЕСТА" should be integrated into a long Spanish-flag ribbon / banner / fabric-strip graphic, not just colored letters
- Use a waving red-yellow-red strip behind or through the word so the title feels physically built from Spanish flag material
- "VNVNC.RU" must be exact Latin letters as text, never mutated, never transliterated

FOOTER: exact text "VNVNC.RU" as a clean left footer mark, time from context on the right, "КОНЮШЕННАЯ 2В" below.

SQUARE 1:1. Realistic fiesta portraits on tactile feria-poster card!""",
]


# BIGCITYLIFE VARIATIONS - 90s NYC graffiti art photobooth (9:16 vertical)
BIGCITYLIFE_VARIATIONS = [
    """НОЧЬ В БОЛЬШОМ ГОРОДЕ — GRAFFITI CHARACTER PHOTOBOOTH (VERTICAL 9:16)

Create a VERTICAL 9:16 photo booth strip with 4 portraits rendered as 2D graffiti mural characters.

CRITICAL RENDERING RULES:
- STRICTLY 2D graffiti character art — flat color fills, bold spray-can outlines, paint drips and fade effects
- NOT photorealistic. NOT 3D. NOT a Pixar render. Like a legendary Bronx wall piece by TATS CRU or COPE2
- Wildstyle energy: thick black outlines, spray fade effects, dripping paint, raw street art texture
- Zero 3D depth or volumetric shading — pure 2D illustration with spray-can texture

LIKENESS (CRITICAL):
- Exact match to the person in the reference photo — face, hair, body proportions preserved
- Preserve ALL clothing text letter-for-letter exactly as it appears
- Preserve all accessories, colors, and recognizable details — rendered in 2D graffiti style

BACKGROUND:
- Keep the original background from the reference photo as base
- Overlay NYC graffiti elements: brick wall texture showing through, spray-painted tags in background, fire escape silhouettes, subway tile patterns at edges

BORDER:
- Aged Polaroid border, slightly yellowed and coffee-stained
- Black ink doodles along edges: tiny fire escapes, yellow taxi cabs, boomboxes, 5-pointed stars, crown graffiti tags
- Scan texture, paper grain, slight crease marks

TEXT (exactly these, no other text):
- TOP of strip: "НОЧЬ В БОЛЬШОМ ГОРОДЕ" + "20.03-21.03" in condensed bold graffiti-tag style lettering
- BOTTOM LEFT: "VNVNC.RU" in graffiti bubble letters — always in English, never Cyrillic
- BOTTOM RIGHT: injected timestamp from personality_context (exact time as written)
- BELOW timestamp: "Конюшенная 2В" in small condensed type
- NO year. NO "МСК". Date appears ONCE at top only. No per-frame timestamps.

4 FRAMES (2x2 grid):
- Frame 1: Direct gaze, confident expression, straight-on pose
- Frame 2: Slight head tilt, relaxed smile, arms natural
- Frame 3: Dynamic energy, body turned, looking at camera
- Frame 4: Candid mood, side angle, cool street energy

PALETTE: NYC cab yellow, graffiti red, concrete grey, night black, neon orange spray — all flat 2D fills

9:16 VERTICAL. Pure 2D graffiti character art photobooth strip. Raw, gritty, NYC street energy.""",

    """BIG CITY LIFE — 90s NYC ГРАФФИТИ ФОТОБУДКА (VERTICAL 9:16)

Создай ВЕРТИКАЛЬНУЮ фотополосу 9:16 с 4 портретами в стиле 2D граффити-арт.

РЕНДЕРИНГ (КРИТИЧНО):
- СТРОГО 2D граффити — плоские заливки, жирные контуры баллончиком, подтёки краски
- НЕ фотореализм. НЕ 3D. Как стенная роспись от TATS CRU или COPE2 в Бронксе
- Wildstyle-энергия: толстые чёрные контуры, фейды баллончиком, капли краски
- Ноль объёмного затенения — чистая 2D иллюстрация с текстурой аэрозоля

СХОДСТВО (КРИТИЧНО):
- Точное совпадение с человеком на фото — лицо, волосы, пропорции сохранены
- Сохранить ВСЕ надписи на одежде буква в букву
- Все детали и аксессуары — в 2D граффити-стиле

ФОН:
- Базовый фон из оригинального фото сохраняется
- Поверх наложить NYC-граффити: текстура кирпичной стены, теги баллончиком, силуэты пожарных лестниц

РАМКА:
- Состаренная рамка Polaroid — пожелтевшая бумага с кофейными пятнами
- Чёрные чернильные дудлы по краям: пожарные лестницы, жёлтые такси, бумбоксы, звёзды, граффити-короны

ТЕКСТ (только эти, никаких других):
- СВЕРХУ: "НОЧЬ В БОЛЬШОМ ГОРОДЕ" + "20.03-21.03" — граффити-шрифт, конденсированный жирный
- СНИЗУ СЛЕВА: "VNVNC.RU" — граффити-буббл леттеринг, всегда латиницей
- СНИЗУ СПРАВА: время из personality_context (точно как написано)
- ПОД ВРЕМЕНЕМ: "Конюшенная 2В" — мелкий конденсированный шрифт
- Год НЕ писать. "МСК" НЕ писать. Дата только один раз сверху.

4 КАДРА (сетка 2x2):
- Кадр 1: Прямой взгляд, уверенная поза
- Кадр 2: Расслабленная улыбка, лёгкий наклон головы
- Кадр 3: Динамичная поза, корпус повёрнут
- Кадр 4: Боковой угол, уличная энергия

ПАЛИТРА: Жёлтый (NYC cab), граффити-красный, бетонный серый, ночной чёрный, оранжевый неон

9:16 ВЕРТИКАЛЬНАЯ. Чистый 2D граффити-арт. Сырая уличная энергия Нью-Йорка.""",

    """BIG CITY LIFE — NYC STREET ART BOOTH (VERTICAL 9:16)

Create a VERTICAL 9:16 photo booth strip with 4 portraits as authentic 2D graffiti mural art.

STYLE MANDATE — 2D GRAFFITI ONLY:
- Pure 2D spray-can character illustration — bold outlines, flat fills, drips, fades
- Reference: TATS CRU style, COPE2 style, classic Bronx/Bushwick wall mural energy
- Absolutely no photorealism, no 3D rendering, no smooth gradients, no Pixar-style
- Every line should feel like it was laid down with a spray can by a master aerosol artist

IDENTITY PRESERVATION:
- The person must be instantly recognizable from the reference photo
- Face structure, hair, clothing reproduced faithfully in 2D graffiti art style
- All text on clothing preserved exactly — rendered as part of the 2D illustration

ENVIRONMENT:
- Base: keep original photo background recognizable beneath graffiti overlay
- NYC elements woven in: subway tile borders, spray-painted throw-ups in background, brick wall sections, fire escapes framing the composition

POLAROID TREATMENT:
- Warm yellowed Polaroid border with age marks
- Hand-drawn black ink annotations at edges: fire escapes, taxi silhouettes, boomboxes, star bursts, crown tags
- Slight scan artifact, paper texture

TEXT RULES (strict):
- TOP: "НОЧЬ В БОЛЬШОМ ГОРОДЕ" + "20.03-21.03" — graffiti tag style, condensed bold
- BOTTOM LEFT: "VNVNC.RU" — bubble letter graffiti, English only
- BOTTOM RIGHT: time from personality_context (copy exactly)
- SMALL BELOW: "Конюшенная 2В" condensed
- No year, no МСК, date once at top, no per-frame time labels

4 EXPRESSIONS:
- Frame 1: Bold front-facing, strong stance, NYC attitude
- Frame 2: Natural smile, relaxed energy
- Frame 3: Turned shoulder, side-eye confidence
- Frame 4: Caught moment, candid power

COLORS: Cab yellow #FFD700, graffiti red #CC1F1F, concrete #7A7A7A, night black #0A0A0A, neon orange #FF6B00

9:16 VERTICAL. 2D spray-can character art. Wildstyle Bronx energy. NOT a photograph.""",
]


# BIGCITYLIFE SQUARE VARIATIONS - 1:1 for LED display
BIGCITYLIFE_SQUARE_VARIATIONS = [
    """BIG CITY LIFE — GRAFFITI SQUARE BOOTH (1:1)

Create a SQUARE (1:1) photo booth grid with 4 portraits rendered as 2D graffiti mural characters.

STYLE: Pure 2D spray-can graffiti character art — flat fills, bold outlines, paint drips
Reference: TATS CRU / COPE2 style. NOT photorealistic. NOT 3D.

LIKENESS: Preserve exact face and clothing from reference photo in 2D graffiti style.
Preserve ALL clothing text letter-for-letter.

BACKGROUND: NYC brick wall texture, spray-painted tags, fire escape silhouettes.

BRANDING: "VNVNC.RU" in graffiti bubble letters at bottom — English only, never Cyrillic.

4 FRAMES: Same person, different expressions and angles. 2D graffiti art throughout.

1:1 SQUARE. Raw NYC street art energy.""",

    """NYC GRAFFITI SQUARE — BIG CITY LIFE (1:1)

SQUARE 1:1 photo booth. 4 graffiti character portraits, 2x2 grid.

RENDER AS: 2D spray-can wall art character — bold outlines, flat color, drips, fades.
Like a Bronx graffiti mural, NOT a photograph, NOT 3D.

Keep the person's likeness exact. Preserve all clothing text exactly.

Background: brick wall with spray tags and fire escapes.

Bottom: "VNVNC.RU" in bubble graffiti letters (English always).

Palette: cab yellow, graffiti red, concrete grey, night black, neon orange.

1:1 SQUARE. Flat 2D wildstyle graffiti character art.""",
]


# BRAINROT VARIATIONS - single-image cringe-party Italian brainrot poster
BRAINROT_VARIATIONS = [
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D meme shark with bright blue sneakers, glossy skin, a stupid grin, and cursed athletic pose while keeping the exact human face from the source photo.
Background: cheap vaporwave seaside gradient, bad Photoshop glow, stretched resave artifacts, ugly star sparkles.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D wooden log-creature with huge eyes, creepy smile, and long awkward limbs while keeping the exact human face from the source photo.
Background: dim dawn street, dirty orange light, repost compression, harsh sharpen halos.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D ballerina with a glossy porcelain cappuccino-cup head, pink tutu, and uncanny beauty-poster energy while keeping the exact human face from the source photo.
Background: pink beauty gradient, cheap glitter, warped mesh backdrop, fake lens flares.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D coffee-cup trickster with chrome lid head, sly eyes, and a dramatic action pose while keeping the exact human face from the source photo.
Background: gritty cafe backroom, steel reflections, overprocessed contrast, greasy glow.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D banana-dolphin hybrid with glossy yellow-blue skin, absurd smile, and cursed elegance while keeping the exact human face from the source photo.
Background: cheap tropical beach, ugly sunset gradient, sea haze, jpeg dirt.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D elephant-sandal hybrid with giant feet and tragic meme stare while keeping the exact human face from the source photo.
Background: dusty desert highway, bad mirage blur, washed-out resize artifacts, hot glow.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D camel-fridge hybrid with long legs, cold expression, and cursed dignity while keeping the exact human face from the source photo.
Background: city heat haze, roadside realism, municipal colors, bad compositing shadows.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D frog-tire hybrid walking upright with glossy rubber body and disgusting-cute internet creature energy while keeping the exact human face from the source photo.
Background: marsh roadside, repost blur, oversharpened edges, ugly glow outline.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D tree-creature with huge human feet, hunched body, and damp forest meme realism while keeping the exact human face from the source photo.
Background: humid forest clearing, fake god-rays, stretched color banding, cursed photobash.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D cat-fish hybrid with underwater fur, glossy fish body, and absurd cute face while keeping the exact human face from the source photo.
Background: aquarium glow, fake bubbles, jelly colors, chromatic aberration, repost artifacts.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D tiny beaked runner with huge sunglasses and ridiculous speed pose while keeping the exact human face from the source photo.
Background: beige road dust, ugly motion streaks, dirty gradient sky, low-quality web sheen.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO 2x2 grid. NO strip. NO separate frames.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Main subject: reinterpret the real person as a surreal semi-realistic 3D giraffe-watermelon hybrid with elegant long legs and glossy fruit body while keeping the exact human face from the source photo.
Background: sunny roadside scene, highway vibe, cracked resize artifacts, terrible meme compositing.

Style: authentic Italian brainrot internet image, semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost jpeg artifacts, wrong proportions, ugly outer glow, over-sharpened edges, width squeeze, dumb sparkles.
Composition: keep all real people together in one centered composition; add only tiny unlabeled cameo creatures or meme doodles at the far edges.

Text and branding:
- The ONLY huge decorative title is "КРИНЖ ПАТИ"
- Use the emblem reference image to keep the exact party title correct
- Keep the required footer text: "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В"
- No character names, no English meme words, no floating sticker text, no "WordArt" text, no extra typography

Preserve exact human likeness, hairstyle, skin tone, and expression. The face stays recognizably human; only the body, costume, silhouette, props, and environment become brainrot.
""",
]


BRAINROT_SQUARE_VARIATIONS = [
    """КРИНЖ ПАТИ — ITALIAN BRAINROT PARTY POSTER (SQUARE 1:1)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO four frames.

Keep the exact faces and every person from the source photo in one shared square composition.
Faces remain human and instantly recognizable. Transform bodies/costumes/background into the approved Italian brainrot canon only:
TRALALERO TRALALA, TUNG TUNG TUNG SAHUR, BALLERINA CAPPUCCINA, CAPPUCCINO ASSASSINO,
BANANITA DOLFINITA, LIRILI LARILA, FRIGO CAMELO, BONECA AMBALABU, BRR BRR PATAPIM,
TRIPPI TROPPI, FRULLI FRULLA, GIRAFA CELESTE.
Do not use Bombardiro Crocodilo or military characters.

If multiple people are present, assign different approved characters while keeping everyone together in one centered scene.
Do not print the character names anywhere.
Use the emblem reference image to keep the exact party title correct.

Visual style: full-bleed cursed semi-realistic 3D brainrot poster, glossy materials, bad Photoshop cutout energy, repost JPEG grime, ugly glow, width-squeezed WordArt, fake glitter, arrows, stars, bad PNG stickers.

Required footer/event text somewhere in the image:
"КРИНЖ ПАТИ", "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В".
No character names, no English meme words, no floating sticker text, no "WordArt" text, and no other text.

Square 1:1, single-image poster, not a photobooth grid.
""",
]


WEDDING_VARIATIONS = [
    """КРИНЖ ПАТИ — СЕЛЬСКАЯ СВАДЕБНАЯ ОТКРЫТКА (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO multi-frame strip.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Preserve the exact faces from the source photo and keep the whole group together in one composition.
If the source photo has multiple people, every person must stay in the final image.
Faces, expressions, hairstyles, and recognizability are critical.

THEME:
- Turn the scene into a painfully cliché 2000s Russian countryside wedding photo
- Cheap banquet glamour, satin drapes, glossy roses, doves, hearts, champagne, fake gold, bad Photoshop halos, plastic flowers, sparkles, wedding rings clipart
- Everything should feel like a provincial wedding photographer and a kiosk postcard designer collaborated badly

STYLE:
- Single-image posed wedding-card / photo-studio montage
- Center the people as the main wedding portrait, large in the middle
- Preserve human likeness first; wardrobe can be lightly glamorized with wedding accessories, veils, ribbons, corsages, shiny jackets, too much satin
- If the image contains two or more men and no women, portray them as fun wedding guests or friends at the banquet, not as a couple
- For male-only groups: think vodka toast, champagne, banquet-table posing, goofy guest energy, brothers/cousins/friends at a wedding
- No kissing, no romantic embrace, no groom-and-groom wedding pairing, no bouquet couple pose for male-only groups
- Add meme doodles and bad decorative overlays around the borders
- Slight glossy print texture, cheap lamination glare, VHS-ish nostalgia, overprocessed beauty-retouch energy

TEXT AND BRANDING:
- Use the emblem reference image to keep the exact party title correct
- The main decorative title should read exactly "КРИНЖ ПАТИ", styled like tacky wedding-card lettering
- Required exact text:
  * "КРИНЖ ПАТИ"
  * "VNVNC.RU"
  * "03.04-05.04"
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- No other text
- No year anywhere

OUTPUT:
- One centered wedding portrait/postcard
- Group preserved, no panels, no grid, meme doodles and tacky wedding decor everywhere
- Vertical 9:16 output
""",
]


WEDDING_SQUARE_VARIATIONS = [
    """КРИНЖ ПАТИ — СЕЛЬСКАЯ СВАДЕБНАЯ ОТКРЫТКА (SQUARE 1:1)

Create one square wedding postcard image with the people centered in the middle.
No grid, no photostrip, no separate frames.

Exact faces and full group inclusion are mandatory.
Turn the scene into a cursed 2000s Russian countryside wedding portrait:
cheap satin backdrops, roses, doves, rings, fake gold, glossy banquet glamour, plastic flowers,
bad Photoshop light rays, champagne glasses, heart clipart, tacky sparkle doodles.

Preserve recognizability first. Wardrobe can be wedding-styled, but never lose the real faces.
If the image contains two or more men and no women, portray them as fun wedding guests or friends at the banquet, not as a couple.
For male-only groups: use toasting, drinking vodka or champagne, banquet-photo energy, and no romantic embrace or groom-and-groom pairing.

Required text somewhere in the design:
"КРИНЖ ПАТИ", "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В".
No other text. Use the emblem reference image to keep the title exact.

Square 1:1 single-image composition, with meme doodles around the border.
""",
]


WHATSAPP_VARIATIONS = [
    """КРИНЖ ПАТИ — БАБУШКИНА FORWARDED-POSTCARD ЭСТЕТИКА (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO photobooth grid. NO panels.
Edge-to-edge full-bleed digital artwork, vertical, print-ready, not framed, not photographed, no white border.

Keep the exact faces from the source photo and preserve the full group together in one scene.
If several people are in the photo, all of them must appear in the final postcard.
Faces stay highly recognizable and human.

THEME:
- Transform the image into an overdecorated WhatsApp greeting postcard that a grandma would forward to the whole family chat
- Glitter roses, gold swans, candles, kittens, sparkles, lace borders, glowing flowers, blessings-card energy, cheap gradients, clip-art abundance
- Slightly absurd, sentimental, tasteless, and extremely sincere

STYLE:
- One centered postcard portrait with the group in the middle
- Bright decorative collage around them, not multiple frames
- Soft heavenly glow, tacky glitter texture, fake rhinestones, reflective foil accents, bright floral overlays
- Add meme doodles and cute-chaotic border stickers without covering faces
- The final image should feel like a forwarded greeting JPEG saved 20 times

TEXT AND BRANDING:
- Use the emblem reference image to keep the exact party title correct
- The main decorative title should read exactly "КРИНЖ ПАТИ", styled like a glittery grandma postcard heading
- Required exact text:
  * "КРИНЖ ПАТИ"
  * "VNVNC.RU"
  * "03.04-05.04"
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- No other text
- No extra long paragraphs of text

OUTPUT:
- One centered grandma-style postcard portrait
- Exact likeness, full group preserved, no grid, meme doodles and absurd decorations everywhere
- Vertical 9:16
""",
]


WHATSAPP_SQUARE_VARIATIONS = [
    """КРИНЖ ПАТИ — БАБУШКИНА FORWARDED-POSTCARD ЭСТЕТИКА (SQUARE 1:1)

One square centered postcard image only. No photostrip, no grid, no four frames.

Preserve the exact human faces and keep every person from the original photo in one shared square composition.
Theme: forwarded grandma WhatsApp greeting card with glitter roses, gold swans, candles, kittens, lace, cheap gradients,
glow effects, flowers, blessing-card sentimentality, meme doodles, and overdecorated sticker clutter.

The portrait/group must stay front-and-center and recognizable while the border/background becomes tacky postcard chaos.

Required text somewhere in the image:
"КРИНЖ ПАТИ", "VNVNC.RU", "03.04-05.04", exact time from personality_context, "КОНЮШЕННАЯ 2В".
No other text. Use the emblem reference image to keep the title exact.

Square 1:1 single-image postcard.
""",
]


SLAVIC_SOUL_VARIATIONS = [
    """СЛАВЯНСКАЯ ДУША — SLAVIC CORE LUXURY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group and exact people count
- Never crop the group down to one hero and never demote extra people into background decoration
- Preserve visible clothing text and logos letter-for-letter
- Faces, skin, eyes, and recognizability stay photoreal and unmistakable

VISUAL DIRECTION:
- Pure black velvet background only, no room interior, no fairy-tale scenery, no bathhouse scenery, no postcard border, no fake photo frame
- Premium Slavic-core editorial still-life collage with warm amber glow, lacquer-red accents, antique gold, amber, fur brown, cranberry crimson
- Hyper-polished luxury-campaign / collectible-object finish for props and styling, while the people remain recognizable humans
- Floating curated objects orbit around the people in a clean balanced composition like a fashion-campaign still life
- Use the extra reference images only as style anchors for the gold ornamental emblem and VNVNC treatment

SLAVIC SOUL OBJECT WORLD:
- jeweled fur ushanka
- Khokhloma-style red lacquer heels
- bottle of perfume in the spirit of "Красная Москва"
- amber prayer beads
- faceted crystal vodka glass
- cranberries, pearls, dried rose petals
- woven burgundy tapestry with golden deer and folk geometry
- small porcelain figurine with floral shawl

WARDROBE / STYLING:
- merge the real outfit with luxe folk-glam touches: kokoshnik jewelry, floral shawl details, fur trim, gold chains, lacquer-red ornament accents
- keep the real body language and exact face, do not turn the subject into a toy
- if multiple people are present, style them as one expensive Slavic-core clique with distinct individual accents for each person
- cool, powerful, expensive, a little ironic, never kitschy in a cheap way

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "СЛАВЯНСКАЯ ДУША"
- title must be rendered in glowing embossed antique-gold ornamental lettering matching the reference style
- required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered Slavic-core luxury poster
- black background, floating props, warm gold glow, exact likeness
- vertical 9:16
""",
]


SLAVIC_SOUL_SQUARE_VARIATIONS = [
    """СЛАВЯНСКАЯ ДУША — SLAVIC CORE LUXURY POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no four frames.

Keep the exact faces and full group from the source photo.
If multiple people are present, keep the exact people count and stage them as one luxury folk-glam ensemble.
Use a pure black background with floating luxury folk props: jeweled ushanka, Khokhloma heels,
amber beads, faceted glass, cranberries, porcelain figurine, burgundy tapestry with golden deer.
The people stay photoreal and recognizable while the styling gains kokoshnik, fur, shawl, and gold-chain glamour.

Huge title exactly "СЛАВЯНСКАЯ ДУША" in glowing embossed antique-gold lettering.
Required text somewhere in the design:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 single-image Slavic-core poster on a black velvet void.
""",
]


SLAVIC_TALES_VARIATIONS = [
    """СЛАВЯНСКИЕ СКАЗКИ — DARK FAIRY-TALE SLAVIC CORE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO separate panels.

CRITICAL LIKENESS:
- Preserve exact human faces, skin, gaze, and expressions from the source photo
- If multiple people are present, preserve the exact full group and exact people count
- Never collapse the scene to a single protagonist; every visible person remains a main character
- Preserve visible clothing text and logos

VISUAL DIRECTION:
- Build a real enchanted fairy-tale world, not a pure black void and not a floating still-life poster
- Slavic fairy-tale luxury: moonlit birch forest, carved terem details, old-gold ornaments, raven-black night, garnet red, ivory snow, ember glow
- Faces remain real and photoreal; transform the setting, wardrobe, and symbolic objects into a premium storybook world
- The composition should feel like an expensive live-action Slavic fantasy scene, not cosplay and not a spa ad

SLAVIC TALES OBJECT WORLD:
- firebird feathers or a glowing firebird aura
- carved terem window or throne details
- enchanted golden apples or ornate silver bowls
- ornate kokoshnik crowns, embroidered shawls, fur capes, red boots, white valenki
- ancient folk talismans, beads, lacquer miniatures, raven feathers, moonlit branches
- deer motifs, berries, chain accents, magical frost, candlelight
- absolutely NO mushrooms

WARDROBE / STYLING:
- turn the people into expensive modern tsarevna / tsarevich / enchanted-court icons
- if multiple people are present, give them complementary fairy-tale roles inside the same scene while preserving all real faces
- embroidered textures, fur, lacquer-red ornament, black boots, dramatic shawls, heroic or mystical hand props
- elegant, magical, storybook, but still editorial and luxurious rather than cosplay

TEXT AND BRANDING:
- the ONLY huge title is exactly "СЛАВЯНСКИЕ СКАЗКИ"
- title is glowing embossed antique-gold ornamental lettering in the same family as the reference images
- required footer text:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no extra text

OUTPUT:
- one centered dark fairy-tale Slavic-core poster
- real enchanted environment, magical objects, exact human likeness
- vertical 9:16
""",
]


SLAVIC_TALES_SQUARE_VARIATIONS = [
    """СЛАВЯНСКИЕ СКАЗКИ — DARK FAIRY-TALE SLAVIC CORE POSTER (SQUARE 1:1)

One square single-image composition only.
Preserve the exact faces and full group from the source photo.
If multiple people are present, keep everyone and make them read as one fairy-tale ensemble rather than one hero plus extras.

Build a real premium fairy-tale setting: moonlit birch forest or carved terem backdrop, firebird feathers,
golden apples, kokoshnik crowns, floral shawls, red boots, white valenki, fur mittens,
gold ornaments, deer motifs, berries, candlelight, magical frost. No mushrooms.

Huge title exactly "СЛАВЯНСКИЕ СКАЗКИ" in glowing embossed antique-gold lettering.
Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 single-image fairy-tale Slavic-core luxury poster.
""",
]


BANYA_CHIC_VARIATIONS = [
    """БАННЫЙ ШИК — DECADENT SLAVIC BATHHOUSE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO multiple panels.

CRITICAL LIKENESS:
- Preserve exact human faces and the full group from the source photo
- If multiple people are present, preserve the exact people count and keep everyone in the same shared scene
- Keep visible clothing text and logos
- People stay recognizable, photoreal, and human

VISUAL DIRECTION:
- Build a decadent bathhouse world, not a pure black void and not a fairy-tale forest
- Decadent banya editorial aesthetic: hot cedar wood, dense steam, brass, champagne foam, caviar gloss, warm gold, amber, pearl, cream, dill green, towel white, lacquer red
- Premium luxury-ad / bathhouse-club finish with photoreal skin, humid air, and tactile steam-room atmosphere
- The composition should feel expensive, funny, decadent, humid, and very Slavic

BANYA CHIC OBJECT WORLD:
- polished brass samovar with a fur ushanka on top
- thick steam ribbons
- black caviar in crystal bowl and red caviar in golden bowl
- champagne bottle with flying cork
- frosted vodka or champagne glasses
- blini stack
- mother-of-pearl spoons
- lemon wedges, dill, berries, towel or linen accents
- elegant birch venik, cedar bucket, brass тазик, tiled or wooden bench details

WARDROBE / STYLING:
- merge the real outfit with decadent bathhouse glamour: embroidered robe or towel accents, fur, gold chains, plush textures, rich spa-lounge energy
- if multiple people are present, style them as one decadent banya crew enjoying the same over-luxurious steam ritual
- not rustic peasant comedy, not spa brochure minimalism
- rich, glossy, steaming, slightly absurd, and intentionally over-luxurious

TEXT AND BRANDING:
- the ONLY huge title is exactly "БАННЫЙ ШИК"
- title must be glowing embossed antique-gold ornamental lettering matching the reference aesthetic
- required footer text:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no extra text

OUTPUT:
- one centered decadent bathhouse poster
- steam-room interior, samovar, caviar, champagne, exact likeness
- vertical 9:16
""",
]


BANYA_CHIC_SQUARE_VARIATIONS = [
    """БАННЫЙ ШИК — DECADENT SLAVIC BATHHOUSE POSTER (SQUARE 1:1)

One square single-image composition only.
Keep the exact real faces and full group from the source photo.
If multiple people are present, keep the whole crew together in one decadent bathhouse scene.

Use a steamy cedar-and-brass bathhouse setting with luxury props: samovar with ushanka, steam,
black and red caviar, champagne bottle, frosted glasses, blini, mother-of-pearl spoons, lemon, dill,
linen/towel accents, birch venik, cedar bucket, and warm gold highlights.

Huge title exactly "БАННЫЙ ШИК" in glowing embossed antique-gold lettering.
Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 single-image Slavic bathhouse luxury poster.
""",
]


VNVNC_BDAY_VARIATIONS = [
    """HAPPY B'DAY VNVNC — LUXURY BIRTHDAY POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group and exact people count
- Never collapse a group into one hero and never turn extra people into background décor
- Preserve visible clothing text and logos letter-for-letter
- Faces, skin, eyes, and recognizability stay photoreal and unmistakable

VISUAL DIRECTION:
- Pure black void only, no room interior, no floor, no reflections, no fake frame
- Premium Octane-style editorial birthday spectacle: matte cream frosting, dark crimson satin, crystal champagne, gold lacquer, pearl accents, candlelight, anthracite luxury materials
- Massive 3-tier ornate birthday cake is the main hero object near the people, with 9 lit candles and warm amber flame glow
- Floating celebration props orbit around the people: crystal coupe, satin crimson balloon, wrapped anthracite gift box, confetti discs, berries, pearl beads, dried rose petals, ribbon curls
- Controlled luxury only: expensive, sharp, material-rich, never childish, never cartoon, never plastic slop
- Use the attached emblem references only as branding anchors; prefer the gift-box 9 emblem, but sometimes echo the chrome oval emblem language in small secondary branding

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "HAPPY B'DAY VNVNC"
- title should feel like premium dark-chrome / crimson-neon birthday branding inspired by the attached emblem references
- required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered luxury birthday editorial poster
- black void, floating premium props, cake hero, candlelight, exact likeness
- vertical 9:16
""",
    """ПОСТОЯННИК ВИНОВНИЦЫ — VIP LICENSE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group and exact people count inside one shared composition
- Preserve visible clothing text and logos letter-for-letter
- Faces must remain photoreal and recognizable, not airbrushed, not doll-like

VISUAL DIRECTION:
- Build the image around one oversized realistic club-membership / driver's-license artifact floating on a pure black void
- The central object is a tactile laminated VIP card with realistic transparent plastic wrap, scuffs, edge wear, holographic foil, embossed numerals, ink texture, barcode-style micro details, pressure marks, shrink-wrap ripples, and subtle fingerprints
- The real person or real group appears as the official portrait printed inside the card, still clearly recognizable
- Surround the card with premium VNVNC birthday props: crimson satin ribbon, chrome edge hardware, small cake crumb accents, confetti, pearls, rose petals, mini candle stubs, luxury gift-tag fragments
- The mood is elite regular / permanent guest / club relic energy — textured, fetishistically realistic, expensive, archival, not parody comedy
- Use the attached emblem references only as small badge / seal branding anchors on the card design; sometimes prefer the chrome oval emblem instead of the gift-box emblem for the seal treatment

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "ПОСТОЯННИК ВИНОВНИЦЫ"
- required supporting text integrated into the card design:
  * "VALID SINCE АПРЕЛЬ 2017"
  * "∞"
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered hyper-real laminated membership-card poster
- black void, tactile plastic, chrome foil, premium wear, exact likeness
- vertical 9:16
""",
    """RAP GOD — HYPER-LUXURY HIP-HOP POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group and exact people count
- Preserve visible clothing text and logos letter-for-letter
- Faces remain human, photoreal, and sharply recognizable

VISUAL DIRECTION:
- Pure black void only, no club interior, no street set, no fake stage floor
- Premium Octane-style hip-hop fantasy with ultra-expensive materials and strong silhouette design — somewhere between Kanye maximalism, Eminem aggression, and MAYOT glossy flex, but without imitating any real person literally
- Build the people as the center of a luxury rap-cover universe with giant chrome microphone hardware, lacquer-red speaker stacks, anthracite trunks, chain jewelry, iced-out typography fragments, crimson satin cords, heavy medallions, glossy vinyl, and sharp rim light
- Floating props should feel collectible and editorial, not cheap urban cliché: studio mic, chain links, red gems, speaker cones, ballistic cases, champagne spray mist, confetti shards, satin bows, money-burst energy
- The whole thing must feel trend-forward, cocky, glossy, cinematic, hard, and cool as hell — no cartoon graffiti, no cheap poster effects, no cringe meme energy
- Use the attached emblem references only as subtle VNVNC badge anchors or chain-medallion branding elements

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "RAP GOD"
- title should feel like luxury chrome-meets-crimson rap-cover lettering
- required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered high-fashion hip-hop birthday poster
- black void, chrome mic world, crimson highlights, exact likeness
- vertical 9:16
""",
]


VNVNC_BDAY_SQUARE_VARIATIONS = [
    """HAPPY B'DAY VNVNC — LUXURY BIRTHDAY POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no four frames.
Keep the exact real faces and full group from the source photo.

Use a pure black void with premium birthday still-life objects: giant cream-and-crimson cake, 9 candles,
crystal champagne, satin balloon, anthracite gift box, confetti, pearls, berries, and rose petals.
The attached emblem references are only branding anchors; prefer the gift-box 9 emblem, but sometimes echo the chrome oval emblem.

Huge title exactly "HAPPY B'DAY VNVNC".
Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 luxury birthday editorial poster.
""",
    """ПОСТОЯННИК ВИНОВНИЦЫ — VIP LICENSE POSTER (SQUARE 1:1)

One square single-image composition only.
Keep the exact real faces and full group from the source photo, printed inside one oversized hyper-real laminated club card.
The card should have tactile plastic-wrap texture, embossed foil, scratches, hologram details, barcode micro-elements, and premium wear.
Use the attached emblem references as small seal/badge anchors on the card, with occasional chrome oval emphasis.

Huge title exactly "ПОСТОЯННИК ВИНОВНИЦЫ".
Required text:
"VALID SINCE АПРЕЛЬ 2017", "∞", "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 luxury VIP-card birthday poster.
""",
    """RAP GOD — HYPER-LUXURY HIP-HOP POSTER (SQUARE 1:1)

One square single-image composition only.
Keep the exact real faces and full group from the source photo.
Place them in a premium black-void rap-cover world with giant chrome microphone hardware, anthracite speaker stacks,
chain jewelry, lacquer-red details, satin cords, medallions, glossy vinyl objects, and razor-sharp rim light.
Use the attached emblem references only as subtle medallion / badge branding anchors.

Huge title exactly "RAP GOD".
Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 hyper-luxury hip-hop birthday poster.
""",
]




MTV_NIGHT_VARIATIONS = [
    """MTV NIGHT — GLOSSY 90S CLUB POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group and exact people count
- Preserve visible clothing text and logos letter-for-letter
- Faces remain unmistakably photoreal, sharp, and alive

VISUAL DIRECTION:
- Build a glossy late-90s MTV promo universe around the people, not a generic nightclub poster
- Use deep black negative space with liquid chrome, translucent candy plastic, glossy acrylic, chrome stars, bubble letters, metallic spheres, lens flares, halftone dots, checker curves, warped grids, and slick Y2K broadcast graphics
- The logo treatment must feel like a premium Octane-style beauty render: ultra-glossy chrome, mirrored metal, deep bevels, thick extrusion, hot pink and electric blue reflections, magenta/cyan neon edge light
- Include a large title reading exactly "MTV NIGHT", but its mark structure must be derived from the supplied real party logo reference, not an invented MTV-like parody
- Reproduce the supplied logo branding language faithfully: same bold blocky TV-network logo attitude, same silhouette logic, same overall mark geometry family as the reference asset
- The scene should feel hyper-designed, expensive, editorial, playful, and iconic — no cheap meme clutter, no ugly AI glow soup
- Use direct-flash fashion photography energy with crisp highlights, polished reflections, and tactile print texture

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "MTV NIGHT"
- The "MTV" part of that title must literally appear as the supplied MTV logo mark itself — not plain text, not a substitute font treatment, not a fake reinterpretation
- Build the full title as one coherent lockup: the real MTV logo for "MTV", plus "NIGHT" typeset beside or beneath it in a matching premium broadcast-brand style
- Typography must feel intentional and designer-made: bold, sharp, balanced spacing, clean silhouette hierarchy, no random AI-font nonsense, no generic club flyer lettering
- title should feel like oversized glossy TV-network branding, chrome-meets-candy, sharp and legible
- Do NOT invent a fake MTV symbol, fake channel mark, or random logo shape: use the supplied real party logo reference as the exact branding anchor
- required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered glossy 90s MTV editorial poster
- black void, chrome/candy-plastic objects, iconic logo energy, exact likeness
- vertical 9:16
""",
    """MTV NIGHT — HYPER-BRANDED LOGO COLLAGE (VERTICAL 9:16)

Create ONE SINGLE CENTERED IMAGE. NO grid. NO strip. NO panels. Full-bleed vertical poster.

CRITICAL LIKENESS:
- Preserve the exact real human faces from the source photo
- If multiple people are present, preserve the exact full group in one shared composition
- Preserve visible clothing text and logos letter-for-letter
- Faces must stay human, not doll-like, not airbrushed plastic

VISUAL DIRECTION:
- Build the composition like a lost 1999 MTV promo key visual with one hero photo of the real people surrounded by oversized branding objects
- Use floating chrome cubes, inflated glossy arrows, jelly stars, translucent vinyl discs, candy-plastic speaker parts, warped TV frames, and metallic droplets
- Let the supplied real party logo language appear as badges, medallions, stickers, and TV-bug style anchors throughout the design
- Every repeated logo badge must stay in the same branding family as the provided logo reference; no substitute fake MTV-inspired marks
- The hero title/logo finish should read as premium 3D Octane-style glossy chrome with hot pink and electric blue reflections, polished mirror metal, and neon rim light
- Keep it slick, fashion-forward, and tactile: lacquer, chrome, acrylic, gel plastic, magazine print, halftone, screen glow
- The vibe is celebratory, clubby, and pop-cultural, never grungy or dirty

TEXT AND BRANDING:
- the ONLY huge decorative title is exactly "MTV NIGHT"
- The "MTV" portion must use the supplied MTV logo mark as the actual title element, while "NIGHT" must be custom-set to match it as one unified lockup
- Make the typography look premium and deliberate: proper hierarchy, spacing, alignment, and brand-fit — not generic AI text, not random rave fonts, not sloppy sticker lettering
- required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- no other text

OUTPUT:
- one centered logo-heavy glossy MTV campaign poster
- exact likeness, branded object collage, premium 90s TV identity energy
- vertical 9:16
""",
]


MTV_NIGHT_SQUARE_VARIATIONS = [
    """MTV NIGHT — GLOSSY 90S CLUB POSTER (SQUARE 1:1)

One square single-image composition only.
Keep the exact real faces and full group from the source photo.

Use a deep black studio void with glossy MTV-era broadcast objects: chrome stars, metallic spheres, jelly arrows, acrylic blocks, warped grids, halftone dots, and a huge crisp title exactly "MTV NIGHT".
Use the supplied real party logo reference as the exact branding anchor. The logo family must clearly read as the real MTV-based mark from that logo reference, not a newly invented MTV-like symbol.
The title/logo finish should be premium 3D Octane-style chrome with deep bevels, mirror reflections, and hot pink plus electric blue neon light.
The "MTV" part of the title must literally be the MTV logo mark itself, with "NIGHT" typeset as a matching lockup rather than generic text.

Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 glossy MTV editorial poster.
""",
    """MTV NIGHT — HYPER-BRANDED LOGO COLLAGE (SQUARE 1:1)

One square single-image composition only.
Keep the exact real faces and full group from the source photo.

Build a premium Y2K TV-network collage around them with chrome cubes, inflated plastic icons, translucent discs, liquid-metal droplets, TV bug graphics, and sharp logo badges.
Huge title exactly "MTV NIGHT".
Use the supplied real party logo reference for every logo badge and title treatment. Do not improvise a different MTV-like icon or alternate fake mark.
The main logo treatment should read like an expensive Octane 3D glossy chrome object with hot pink and electric blue reflections on black.
The "MTV" portion of the title must literally be the MTV logo mark itself, with a deliberate matching "NIGHT" lockup.

Required text:
"VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text.

Square 1:1 MTV logo-fever poster.
""",
]



# SHADOW KINGDOM VARIATIONS - Gothic chrome castle poster (9:16 vertical)
SHADOW_KINGDOM_VARIATIONS = [
    """КОРОЛЕВСТВО ТЕНЕЙ — EMBLEM-LED GOTHIC CASTLE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. NO 2x2 grid. NO strip. NO split panels. NO black-and-white output.

ABSOLUTE #1 PRIORITY — EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real human faces from the source photo; faces must look like the original people, not generic fantasy models.
- If multiple people are present, preserve the exact full group and exact people count in one shared hero composition.
- Keep real facial structure, eyes, nose, mouth, hairline, hairstyle, facial hair, glasses, makeup, and proportions recognizable.
- Preserve visible clothing text/logos letter-for-letter unless transformed into black royal wardrobe on top while keeping identity intact.
- Do not over-beautify, do not plasticize, do not turn them into dolls; human skin must remain real and alive.

BRANDING — USE THE ATTACHED EMBLEM AS-IS:
- A supplied extra reference image is the official КОРОЛЕВСТВО ТЕНЕЙ / SHADOW KINGDOM emblem.
- Use that attached emblem/logo lockup as the title/branding anchor as directly as possible: crown, shield, sword point, red jewel, chrome bevels, black void, Cyrillic wording.
- Do NOT invent a new title/logo style from scratch. Do NOT replace it with plain generated "SHADOW KINGDOM" text.
- The big top/hero branding should preserve the attached emblem's design language and wording; if text is rendered, it should follow the supplied emblem, not a random AI font.
- The emblem is branding only; never replace the real people with the emblem.

VISUAL DIRECTION:
- Premium full-color cinematic dark fantasy key art, super clean rendering, not messy AI fantasy.
- Gothic stone castle backdrop at night, moonlit storm clouds, deep parallax: distant castle towers, midground banners/fire braziers, foreground people and chrome frame.
- Glossy black steel armor, black leather cloaks, dark royal wardrobe, polished chrome trim, beveled sword/crown details.
- Red royal banners, blue jewel corner accents, ruby/candle/fire accents, ember particles, cinematic depth.
- Expensive black-metal/chrome frame, sharp bevels, controlled cinematic contrast, high depth.

MANDATORY EVENT FOOTER — MUST APPEAR ON THE POSTER:
- Include exactly "VNVNC.RU".
- Include the exact Russian weekday from personality_context.
- Include the exact time from personality_context.
- Include exactly "КОНЮШЕННАЯ 2В".
- Footer should be elegant metallic event text at the bottom of the poster.
- No fake dates, no year, no per-frame timestamps, no "МСК", no extra random text.

LAYOUT:
- Top/crest area: attached official emblem/logo lockup integrated into the frame.
- Center: exact people from photo as rulers/knights of the shadow kingdom, upper-body hero group composition, faces unobstructed and photoreal.
- Background: gothic castle with towers, moon/storm sky, red banners, fire braziers, depth and parallax.
- Frame: ornate black-steel/chrome border with angular gothic corners, blue jewels, subtle red glints, premium depth.
- Bottom: mandatory footer with VNVNC.RU + weekday + time + КОНЮШЕННАЯ 2В.

QUALITY / NEGATIVES:
- FULL COLOR ONLY. No monochrome, no black-and-white, no thermal-printer look.
- No waxy/plastic skin, no generic AI glow soup, no muddy faces, no malformed eyes, no random unreadable typography.
- No cartoon, no anime, no cheap game UI, no collage, no sticker clutter.

OUTPUT: vertical 9:16 single premium gothic castle poster, exact likeness, official attached emblem branding, mandatory event footer.""",

    """КОРОЛЕВСТВО ТЕНЕЙ — ROYAL BLACK STEEL HERO POSTER (VERTICAL 9:16)

Create ONE single full-color 9:16 poster. Not a grid, not a photobooth strip, not a collage, not black-and-white.

CRITICAL LIKENESS:
- The people must remain the exact people from the input photo; preserve face identity above everything else.
- Include every person from the photo if it is a group, with equal presence and no missing faces.
- Keep eyes, facial hair, hair color/style, expression, skin texture, and body proportions recognizable.
- Clothing may become dark royal armor/cloaks, but identity and any visible clothing text must not be lost if it remains visible.

OFFICIAL EMBLEM / BRANDING:
- Use the attached КОРОЛЕВСТВО ТЕНЕЙ emblem as the actual title/branding source.
- Preserve the emblem's crown, shield, sword, ruby, chrome bevels, black steel mood, and Cyrillic title language.
- Do not create a generic "SHADOW KINGDOM" wordmark; the attached emblem is the visual reference and should drive the title area.
- It may be integrated as a crest/top plaque/metal medallion, but the design must clearly come from the supplied emblem.

STYLE:
- Ultra-premium full-color dark fantasy event poster: black steel, chrome silver, glass jewels, red rubies, firelight, moonlit castle atmosphere.
- People are staged like a royal court / knight order, with realistic faces and black leather/armor wardrobe.
- Strong parallax: foreground ornate border and weapons, midground people, background castle and storm moon.
- High-end beauty lighting: cool moon rim light plus warm fire accents, crisp specular highlights, no haze covering faces.

MANDATORY EVENT TEXT:
- Footer must include exactly "VNVNC.RU".
- Footer must include the exact Russian weekday from personality_context.
- Footer must include the exact time from personality_context.
- Footer must include exactly "КОНЮШЕННАЯ 2В".
- No fake date, no year, no per-frame timestamps, no "МСК", no extra words.

FRAME / CARD:
- Ornate black iron and polished chrome rectangular frame, angular gothic corners, crown/sword motif, red ruby center accent, blue jewel corners.
- The poster should feel like an expensive fantasy event key visual printed on glossy black metal/card stock.

NEGATIVE CONSTRAINTS:
- No 2x2 layout, no four frames, no comic strip, no generic fantasy game loading screen.
- No plastic doll faces, no over-smoothing, no face replacement, no unreadable extra text.
- FULL COLOR ONLY; never convert to black and white.

Vertical 9:16. Official attached emblem branding. Exact human likeness. Mandatory event footer.""",
]


SHADOW_KINGDOM_SQUARE_VARIATIONS = [
    """КОРОЛЕВСТВО ТЕНЕЙ — EMBLEM-LED GOTHIC POSTER (SQUARE 1:1)

This square prompt is retained only as a fallback; the live photobooth should not call it for paid generation.
If used, create one full-color square single-image composition only. NO grid, NO panels, NO black-and-white.

Keep the exact real faces and full group from the source photo. Human faces must stay photoreal, sharp, recognizable, and unobstructed.

Use the attached КОРОЛЕВСТВО ТЕНЕЙ emblem as the actual branding/title source, preserving its chrome gothic crown/shield/sword/ruby language. Do not invent a generic SHADOW KINGDOM title.

Include mandatory event text: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, and "КОНЮШЕННАЯ 2В".

Full-color premium gothic castle poster: black steel, chrome bevels, moonlit castle, red banners, fire braziers, blue jewels, ruby accents.""",

    """КОРОЛЕВСТВО ТЕНЕЙ — ROYAL BLACK STEEL PORTRAIT (SQUARE 1:1)

This square prompt is retained only as a fallback; the live photobooth should not call it for paid generation.
One square hero poster, full color only. Preserve exact likeness and all people from the input photo.

Use the attached official emblem as the title/branding anchor: crown, shield, sword point, red jewel, chrome bevels, Cyrillic wording.
Transform the scene into a gothic Shadow Kingdom royal court: black cloaks, black leather, polished steel armor accents, moonlit castle, red banners, firelight, angular metallic frame.

Footer/event text must include: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No random extra words. No black-and-white.""",
]


# CANDY SHOP VARIATIONS - Pure white pink Octane 3D candy boutique poster (9:16 vertical)
CANDY_SHOP_VARIATIONS = [
    """CANDY SHOP - WHITE PINK CANDY BOUTIQUE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. NO grid. NO strip. NO panels.

ABSOLUTE #1 PRIORITY - EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real human faces from the source photo; faces must look like the original people, not generic models or improved lookalikes.
- If multiple people are present, preserve the exact full group and exact people count in one shared hero composition.
- Keep eyes, nose, mouth, jawline, face shape, skin tone, skin texture, hairline, hairstyle, hair color, facial hair, glasses, expression, height relationship, and body proportions the same as the source.
- Preserve the real clothing silhouette, color, visible text, and logos letter-for-letter; do not replace the outfit with a costume.
- Style the scene and props only; do not beautify, age, slim, widen, gender-swap, ethnicity-shift, change hair, change skin tone, change expression, or otherwise redesign any person.
- People remain photoreal and human, not dolls, not cartoons, not airbrushed plastic.

VISUAL DIRECTION:
- Pure white background only: clean #FFFFFF studio void, no black background, no gray wall, no room, no floor line.
- Premium Octane-style 3D candy still-life around the people, kept minimal: glossy pink hard candy, one or two glass lollipops, translucent sugar shards, wrapped bonbons, sugar pearls, pale chrome candy scoops, soft rose reflections.
- Use the strong single-image luxury layout discipline of the best previous photobooth themes: exact likeness, centered hero group, polished editorial object placement, clean hierarchy, elegant footer, no visual clutter.
- Composition should feel expensive, modern, sweet, sharp, and tactile - never childish clip art, never messy AI clutter, never folk-themed.
- Keep the white negative space beautiful and intentional, with only a few candy objects floating around the people like a luxury perfume campaign.

WARDROBE / STYLING:
- Keep each person's real outfit from the source photo intact. Add only light candy-shop accessories or nearby props: glossy pink candy jewelry, sugar-glass brooches, pearl accents, white satin accents, soft chrome highlights, pale-pink ribbon details.
- If multiple people are present, keep their real styling distinct; unify the poster with surrounding boutique details, not by changing their identities.
- Real faces stay unobstructed and readable.

TEXT AND BRANDING:
- The supplied candy-shop emblem reference is the official party emblem. Use that emblem as the actual huge decorative title/logo, not just as inspiration.
- The ONLY huge decorative title is exactly "CANDY SHOP", matching the supplied emblem's layout, bubble-letter shapes, candy-swirl details, awning/header shape, border language, and pink/white/chrome material treatment as closely as possible.
- Do not invent alternate CANDY SHOP lettering, do not remove the emblem shape, and do not replace it with plain text.
- Required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- Do not write "VNVNC PHOTOBOOTH". Do not write "PHOTOBOOTH". No extra text, no fake dates, no year, no per-frame timestamps, no "МСК".

OUTPUT:
- one centered candy-shop luxury poster
- pure white background, minimal glossy pink candy still-life, exact likeness
- vertical 9:16
""",
    """CANDY SHOP - WHITE GLOSS CANDY ALTAR (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No grid, no strip, no separate frames.

CRITICAL LIKENESS:
- Preserve exact real faces and the full group from the input photo; no generic replacement faces and no improved lookalikes.
- Every person remains photoreal, recognizable, and equal in importance.
- Keep hair, hair color, skin tone, face shape, expression, body proportions, pose, and real outfit identity from the source.
- Preserve visible clothing logos and text letter-for-letter.
- Do not over-beautify, do not make waxy faces, do not change apparent age, do not change ethnicity, do not replace people with candy characters.

VISUAL DIRECTION:
- Absolute pure white #FFFFFF background, museum-clean, bright, high-key, no shadows swallowing the white.
- Build a luxurious candy-shop altar around the people using Octane 3D material realism: glass sugar, pale chrome wrappers, pink candy drops, milky white porcelain, pearl sprinkles, transparent lollipops, ribbon candy, caramel spirals, marshmallow blocks.
- Keep the object world minimal and modern: no folk motifs, no red lacquer, no gold filigree, no busy collage.
- The scene must read as an expensive product-campaign poster, not a kid birthday flyer.
- Keep object placement balanced and airy so the white background remains pure and the people remain the hero.

TEXT:
- The supplied candy-shop emblem reference is mandatory branding. Recreate it as the top emblem/title as closely as possible.
- Huge title exactly "CANDY SHOP", preserving the reference emblem's overall shape, bubble lettering, candy-swirl "O" logic, awning/header feel, and pink glossy material.
- Do not invent a different title design and do not use plain generic text.
- Include exactly "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, and "КОНЮШЕННАЯ 2В" in a neat footer.
- No other words. No "photobooth" wording. No fake dates. No "МСК".

OUTPUT:
- premium white-background candy-core poster, exact likeness, glossy Octane materials
- vertical 9:16
""",
]


CANDY_SHOP_SQUARE_VARIATIONS = [
    """CANDY SHOP - WHITE PINK CANDY BOUTIQUE POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no panels.
Keep the exact real faces and full group from the source photo. Preserve hair, skin tone, face shape, expression, body proportions, clothing silhouette, and visible clothing text exactly; style only the surrounding scene and added props.

Use a pure white #FFFFFF background with premium Octane 3D candy objects around the people:
glass lollipops, hard candy, sugar shards, wrapped bonbons, pearl sprinkles, ribbon candy, pale pink drops,
soft chrome wrappers, white enamel, and lots of clean negative space.
The people stay photoreal and recognizable; add candy jewelry, pearl accents, white satin, and pale-pink ribbons only as light accessories without replacing faces, hair, bodies, or outfits.

Huge title exactly "CANDY SHOP" using the supplied candy-shop emblem reference as the actual top logo; preserve its overall shape, lettering style, candy-swirl detail, and pink glossy material as closely as possible.
Required text: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text and no "photobooth" wording.

Square 1:1 single-image candy-shop poster on a pure white background.
""",
    """CANDY SHOP - WHITE GLOSS CANDY ALTAR (SQUARE 1:1)

One square full-color poster. Preserve exact likeness and every person from the input photo: same face, hair, skin tone, expression, body proportions, clothing silhouette, and visible clothing text.

Pure white studio void. Premium candy still-life: translucent lollipops, caramel spirals, marshmallow blocks,
pink candy drops, pearl sugar, porcelain white surfaces, soft chrome wrappers, minimal boutique object placement,
and balanced high-key product-campaign lighting.

Huge title exactly "CANDY SHOP", based directly on the supplied candy-shop emblem reference rather than invented lettering.
Footer text must include: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No random words, no fake dates, no "photobooth" wording.

Square 1:1 white-background luxury candy poster.
""",
]


# STREET HEAT VARIATIONS - White background west coast polaroid luxury (9:16 vertical)
STREET_HEAT_VARIATIONS = [
    """STREET HEAT - WEST COAST POLAROID PASS (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No grid. No strip. No panels.

ABSOLUTE #1 PRIORITY - EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real human faces from the source photo; faces must remain the same people, not improved lookalikes or glamorized replacements.
- If multiple people are present, preserve the exact full group in one shared composition.
- Keep hairline, hair texture, hair color, eyebrow shape, eye spacing, eyelids, nose width, lips, jawline, cheek volume, skin texture, skin tone, body proportions, and visible clothing text/logos exactly.
- Do not beautify, slim, age-shift, ethnicity-shift, makeup-shift, expression-shift, or costume-swap the people.
- The real face identity is more important than stylistic embellishment. If there is any tradeoff, keep the exact face and reduce styling instead.

VISUAL DIRECTION:
- Pure white background only: bright premium white studio void, no black background, no room, no wall vignette, no floor line.
- The image must feel like a premium tactile Polaroid / instant-film campaign, not a pink candy boutique, not a pastel beauty poster, not a glossy toy still-life.
- Primary accent colors are YELLOW and PURPLE. Small controlled support accents may include basketball orange, chrome silver, asphalt black, and tiny hits of warm gold. Pink should be absent or near-zero.
- Add a curated West Coast street still-life around the people with restraint: traffic cones, basketball cues, chrome palm details, graffiti tag energy, lowrider chrome flashes, dice, chain details, yellow-and-purple street objects.
- Graffiti should appear as real graphic tags / mural accents, not cute stickers and not random decorative scribbles.
- The Polaroid object itself must feel amazing and tactile: creamy off-white instant-film border, slightly warm paper tone, subtle fiber texture, fine print grain, real glossy photo chemistry, gentle edge wear, believable instant-photo depth.
- Keep it super neat and premium, like a collector's fashion Polaroid pinned into a white studio campaign layout.

HARD NEGATIVES:
- No pink palette drift.
- No blush, rose, candy pink, pastel pink, baby pink, or hot-pink object world.
- No random text on props, walls, signs, balloons, stickers, or objects.
- No Cyrillic words on objects. No English warning signs. No stray labels. No fake signage text.
- The ONLY allowed readable text in the whole image is the official STREET HEAT title/logo plus the required footer text.
- No speech bubbles. No decorative octagons with words. No floating signs with extra copy.
- No disco ball. No lollipops. No candy props. No boutique objects.

STYLING / ATTITUDE:
- West Coast street style hip hop attitude: confident, cool, athletic, sexy, clean, expensive, no parody.
- Preserve the real outfits, but allow light additions in surrounding props only.
- No gang cosplay, no caricature tattoos, no cheap clip-art graffiti, no overdone urban clichés.
- Think white-background fashion street campaign with GTA San Andreas / LA / basketball / traffic-cone / mural energy, but premium and very controlled.

TEXT AND BRANDING:
- The supplied STREET HEAT emblem reference is the official party emblem. Use it as the actual top emblem/title, matching its silhouette and blackletter/palm logic as closely as possible.
- Huge title exactly "STREET HEAT" based on the supplied emblem, not generic text.
- Required footer text somewhere elegant in the composition:
  * "VNVNC.RU"
  * exact Russian weekday from personality_context
  * exact time from personality_context
  * "КОНЮШЕННАЯ 2В"
- No extra text. No fake dates. No "photobooth" wording. No "МСК".

OUTPUT:
- one centered white-background west coast Polaroid poster
- exact likeness, premium tactile instant-film texture, yellow/purple/graffiti/traffic-cone accents
- vertical 9:16
""",
    """STREET HEAT - LA COURT POLAROID (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No strip. No four-frame booth layout.

CRITICAL LIKENESS:
- Preserve the exact real faces and full people count from the input photo.
- Keep hair, skin, expression, body proportions, and visible clothing text/logos exactly.
- People remain photoreal and human. No waxy skin, no mannequin faces, no game-character redesign.

VISUAL DIRECTION:
- Absolute pure white #FFFFFF background, clean and editorial.
- Make the image feel like an expensive instant-photo / Polaroid keepsake from a fictional West Coast night: subtle warm print cast, creamy paper borders, slightly embossed instant-film edge, believable flash falloff, tactile analog photo surface.
- Accent palette must be controlled around yellow and purple first, with basketball orange and chrome as support. Pink should be absent.
- Add a minimal world of West Coast props around the people: polished basketball, traffic cone, chrome palm details, graffiti tags, lowrider metal reflections, dice, chain details.
- It should nod to LA street courts, GTA San Andreas mood, and hip-hop flyer energy without becoming gamer fan-art.
- Keep the composition airy, super neat, premium, and white.

TEXT:
- Recreate the supplied STREET HEAT emblem as the huge top title/logo as closely as possible.
- Use the supplied STREET HEAT scene reference image as the persistent composition/world reference: keep the same overall scene language, same white-background Polaroid presentation, same family of objects, same mood, and same yellow/purple West Coast court energy.
- Include exactly "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, and "КОНЮШЕННАЯ 2В" in a neat footer.
- No other words anywhere in the image.
- No fake signs, no object labels, no warning text, no random graffiti words.

OUTPUT:
- premium white-background west coast instant-film poster
- exact likeness and polished analog Polaroid feel
- vertical 9:16
""",
]


STREET_HEAT_SQUARE_VARIATIONS = [
    """STREET HEAT - WEST COAST POLAROID PASS (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no panels.
Keep the exact real faces and full group from the source photo. Preserve hair, skin tone, face shape, expression, body proportions, clothing silhouette, and visible clothing text exactly.

Use a pure white background with premium West Coast still-life props kept minimal: traffic cone, basketball cues, chrome palm details, graffiti tag energy, dice, chain jewelry reflections, lowrider metal flashes. Primary accents are yellow and purple; pink should be absent.
Make the image feel like a tactile premium Polaroid object: creamy white instant-film border, subtle fiber texture, glossy print chemistry, gentle analog grain.

Huge title exactly "STREET HEAT" using the supplied emblem reference as the actual top logo.
Required text: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No extra text and no "photobooth" wording. No random object text.

Square 1:1 white-background west coast luxury Polaroid poster.
""",
    """STREET HEAT - LA COURT POLAROID (SQUARE 1:1)

One square full-color poster. Preserve exact likeness and every person from the input photo: same face, hair, skin tone, expression, body proportions, clothing silhouette, and visible clothing text.

Pure white studio void. Premium West Coast still-life with traffic cone, basketball, chrome palm details, graffiti accents, dice, chain motifs, lowrider reflections, and tactile analog instant-film texture. Keep everything neat, restrained, expensive, and yellow/purple-led.

Huge title exactly "STREET HEAT", based directly on the supplied emblem reference rather than invented lettering.
Footer text must include: "VNVNC.RU", exact Russian weekday from personality_context, exact time from personality_context, "КОНЮШЕННАЯ 2В".
No random words, no fake dates, no "photobooth" wording, no text on props.

Square 1:1 premium white-background West Coast Polaroid poster.
""",
]


# OFFICE CORE VARIATIONS - pure white pixelated office object poster (9:16 vertical)
OFFICE_CORE_VARIATIONS = [
    """OFFICE CORE - PURE WHITE PIXEL OFFICE POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No grid. No strip. No separate frames.

ABSOLUTE #1 PRIORITY - EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real faces and full people count from the source photo.
- Keep hair, skin tone, expression, body proportions, pose, clothing silhouette, and visible clothing text/logos exactly.
- People remain recognizable and human; do not replace them with generic office workers.
- Apply the theme to the surrounding scene, props, border, and light accessories only.

VISUAL DIRECTION:
- Pure white #FFFFFF background only. No black background, no gray wall, no room, no floor line.
- Pixelated 2D office-core style inspired by 1990s desktop UI and clean pixel-art object sheets.
- Use crisp square pixels, limited palette, sharp black outlines, chunky dithering, and retro PC icon logic.
- Surround the people with straight office objects in this style: red corded telephone, beige CRT computer, old keyboard, fax machine, dot-matrix printer, copier paper, manila folders, floppy disks, stapler, calculator, mouse cursor, error dialog, paper jam strips.
- Keep the object placement neat, cool, graphic, and readable. The background must stay mostly white.
- No dark cyber tunnel, no black void, no cluttered collage, no photorealistic 3D props.

TEXT AND BRANDING:
- Use the supplied OFFICE CORE emblem reference as the official top logo/title.
- Huge title exactly "OFFICE CORE", matching the emblem's pixel-office lockup and red/blue/green accent language as closely as possible.
- Leave the bottom 12-15% of the poster as clean pure white empty space for a system-rendered footer.
- Do not write VNVNC.RU, weekday, time, venue, fake dates, year, or "МСК" anywhere. The app adds the real footer after generation.
- No other readable words except the OFFICE CORE title and tiny UI glyphs that are not text.

OUTPUT:
- one centered pure-white pixelated office-core poster
- exact likeness, crisp 2D pixel office objects, premium clean layout
- vertical 9:16
""",
    """OFFICE CORE - WHITE DESKTOP ICON SHEET POSTER (VERTICAL 9:16)

Create a single vertical 9:16 poster on a pure white background.

IDENTITY LOCK:
- Preserve exact likeness and every person from the input photo.
- Same face, hair, skin tone, expression, body proportions, and real outfit identity.
- Preserve visible clothing text and logos letter-for-letter.
- Do not beautify, costume-swap, cartoon-replace, or turn people into generic avatars.

STYLE:
- Clean pixelated 2D office-core art, like a premium 1990s computer icon set expanded into a party poster.
- People may be lightly pixel-rendered while remaining unmistakably the same real people.
- Office objects are the hero styling: red telephone with coiled cord, beige CRT monitor, old printer, fax machine, paper trays, file folders, floppy disks, calculator, stapler, chunky mouse cursor, tiny error-window shapes.
- Pure white negative space is mandatory. Use blue, green, red, beige, and black accents with tight control.
- Make it cool and graphic, not corporate, not clip art, not messy AI clutter.

BRANDING:
- Recreate the supplied OFFICE CORE emblem as the huge top logo/title as closely as possible.
- Leave the bottom 12-15% of the poster as clean pure white empty space for the system footer.
- Do not write VNVNC.RU, weekday, time, venue, fake UI messages, fake dates, or "photobooth" wording. The app adds the real footer after generation.
- No other readable text beyond the OFFICE CORE title.

OUTPUT:
- pure white office-core pixel poster, exact likeness, straight office equipment objects
- vertical 9:16
""",
]


OFFICE_CORE_SQUARE_VARIATIONS = [
    """OFFICE CORE - PURE WHITE PIXEL OFFICE POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no panels.
Preserve exact real faces, full group, hair, skin tone, expression, body proportions, clothing silhouette, and visible clothing text exactly.

Use a pure white #FFFFFF background with crisp pixelated 2D office objects around the people:
red corded telephone, beige CRT computer, old keyboard, fax machine, dot-matrix printer, copier paper, folders, floppy disks, stapler, calculator, mouse cursor, and tiny 1990s desktop UI shapes.
Keep the composition clean, cool, and mostly white. No black void and no 3D render.

Huge title exactly "OFFICE CORE" using the supplied emblem reference as the actual top logo.
Do not write VNVNC.RU, weekday, time, venue, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
No extra readable text beyond the OFFICE CORE title.

Square 1:1 pure-white pixel office-core poster.
""",
    """OFFICE CORE - WHITE DESKTOP ICON POSTER (SQUARE 1:1)

One square full-color poster. Preserve exact likeness and every person from the input photo.
Pure white studio void. Premium pixelated 2D object-sheet style with blue, green, red, beige, and black accents.

Surround the people with straight office equipment: red telephone, CRT monitor, fax, printer, paper stack, folders, floppy disks, calculator, stapler, keyboard, and cursor icons.
The office objects should be crisp, readable, and cool; no messy collage, no dark background, no photorealistic 3D props.

Huge title exactly "OFFICE CORE", based directly on the supplied emblem reference rather than invented lettering.
Do not write VNVNC.RU, weekday, time, venue, random words, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
No extra readable text beyond the OFFICE CORE title.

Square 1:1 white-background pixel office poster.
""",
]


# 2K17 VARIATIONS - pure white pixelated street-style throwback poster (9:16 vertical)
TWO_K17_VARIATIONS = [
    """2K17 - PURE WHITE PIXEL STREET POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No grid. No strip. No separate frames.

ABSOLUTE #1 PRIORITY - EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real faces and full people count from the source photo.
- Keep hair, skin tone, expression, body proportions, pose, clothing silhouette, and visible clothing text/logos exactly.
- People remain recognizable and human; do not replace them with generic models.
- Apply the 2K17 theme to the surrounding scene, props, border, and light accessories only.

VISUAL DIRECTION:
- Pure white #FFFFFF background only. No black background, no gray wall, no room, no floor line.
- Pixelated 2D poster style inherited from Office Core and Summer Camp: crisp square pixels, sharp black outlines, chunky dithering, premium object-sheet layout.
- Surround the people with 2017 street-style objects: fidget spinners, rosé bottle and plastic cups, iPhone 7, wired white EarPods/AirPods-style cables, cracked phone screen sticker shapes, skate stickers, disposable vape-like silhouettes, metal chain details, black chokers, fishnet-tights pattern fragments, Vans-style checkerboard shoes, track pants stripes, oversized hoodie folds, flame skate-shirt graphics, yellow caution strap details.
- Use the supplied black-label reference for the text treatment: flat black rectangular padding strips with bold white blocky pixel font, like a 2017 VK/club dresscode meme graphic.
- Women's styling cues may include chokers, fishnet tights, black skirts, flame shirts, heavy eyeliner, Vans, pink hair streaks, without covering faces or changing bodies.
- Men's styling cues may include Gosha Rubchinskiy-era streetwear, track pants, socks-and-sneakers styling, black puffers, chain belts, skate tees, off-white/yellow industrial strap accents.
- Palette: pure white, black pixel outlines, flame red, hot yellow, acid lime, deep royal blue, worn asphalt gray, small rosé pink highlights.
- Keep object placement neat, stylish, graphic, and readable. The background must stay mostly white.
- No office props, no sports camp props, no dark club void, no photorealistic 3D props, no messy collage.

TEXT AND BRANDING:
- Use the supplied 2K17 flame emblem reference as the official top logo/title.
- Huge title exactly "2K17", matching the supplied flame emblem's red/yellow fire shape, bold pixel-party attitude, and visual hierarchy as closely as possible.
- Secondary label blocks, if needed, must follow the supplied black-padding style: white pixel text on solid black rectangles with square corners and no glow.
- Leave the bottom 12-15% of the poster as clean pure white empty space for a system-rendered footer.
- Do not write VNVNC.RU, weekday, time, venue, fake dates, or "МСК" anywhere. The app adds the real footer after generation.
- If any year appears anywhere in the design, it must be 2017. Never show 2026.
- No other readable words except the 2K17 title and tiny non-readable sticker/UI glyphs.

OUTPUT:
- one centered pure-white pixelated 2K17 street-style poster
- exact likeness, crisp 2D 2017 props, premium clean layout
- vertical 9:16
""",
    """2K17 - WHITE THROWBACK ICON POSTER (VERTICAL 9:16)

Create a single vertical 9:16 poster on a pure white background.

IDENTITY LOCK:
- Preserve exact likeness and every person from the input photo.
- Same face, hair, skin tone, expression, body proportions, and real outfit identity.
- Preserve visible clothing text and logos letter-for-letter.
- Do not beautify, costume-swap, cartoon-replace, or turn people into generic avatars.

STYLE:
- Clean pixelated 2D 2K17 street poster, like a premium 1990s icon-sheet language applied to 2017 club kids and streetwear.
- People may be lightly pixel-rendered while remaining unmistakably the same real people.
- 2K17 objects are the hero styling: fidget spinners, rosé, iPhone 7, wired white earbud cables, chokers, fishnet pattern strips, flame skate shirts, Vans/checkerboard shoe details, track pants stripes, puffer jacket folds, chain belts, yellow industrial strap accents, skate stickers, phone-camera flash sparkles.
- The supplied black-label reference is the official typography style for this theme: solid black rectangular bars behind bold white blocky pixel letters, square corners, high contrast.
- Pure white negative space is mandatory. Use flame red, hot yellow, black, royal blue, acid lime, asphalt gray, and tiny rosé pink with tight control.
- Make it cool and graphic, not clip art, not messy AI clutter, not a generic fashion ad.

BRANDING:
- Recreate the supplied 2K17 flame emblem as the huge top logo/title as closely as possible.
- Any secondary design labels must be black padded strips with white pixel lettering, matching the supplied typography reference.
- Leave the bottom 12-15% of the poster as clean pure white empty space for the system footer.
- Do not write VNVNC.RU, weekday, time, venue, fake sticker slogans, fake dates, or "photobooth" wording. The app adds the real footer after generation.
- If any year appears anywhere in the design, it must be 2017. Never show 2026.
- No other readable text beyond the 2K17 title.

OUTPUT:
- pure white 2K17 pixel street poster, exact likeness, streetwear/camera-party props
- vertical 9:16
""",
]


TWO_K17_SQUARE_VARIATIONS = [
    """2K17 - PURE WHITE PIXEL STREET POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no panels.
Preserve exact real faces, full group, hair, skin tone, expression, body proportions, clothing silhouette, and visible clothing text exactly.

Use a pure white #FFFFFF background with crisp pixelated 2D 2017 street-style objects around the people:
fidget spinners, rosé bottle, iPhone 7, wired white earbud cables, chokers, fishnet pattern strips, Vans/checkerboard shoe details, flame skate-shirt graphics, track pants stripes, puffer jacket folds, chain belts, yellow industrial strap accents, and skate sticker shapes.
Keep the composition clean, stylish, graphic, and mostly white. No office props, no sports camp props, no black void, and no 3D render.
Use the supplied black-label reference for typography: black rectangular padding strips with bold white pixel lettering, square corners, no glow.

Huge title exactly "2K17" using the supplied flame emblem reference as the actual top logo.
Do not write VNVNC.RU, weekday, time, venue, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
If any year appears anywhere in the design, it must be 2017. Never show 2026.
No extra readable text beyond the 2K17 title.

Square 1:1 pure-white pixel 2K17 street poster.
""",
    """2K17 - WHITE STREETWEAR ICON POSTER (SQUARE 1:1)

One square full-color poster. Preserve exact likeness and every person from the input photo.
Pure white studio void. Premium pixelated 2D object-sheet style with flame red, hot yellow, black, royal blue, acid lime, and small rosé pink highlights.

Surround the people with 2K17 street-party props: spinners, rosé, iPhone 7, wired white earbuds, chokers, fishnet fragments, flame shirts, Vans/checkerboard shoes, track pants, puffer jacket shapes, chain belts, industrial yellow strap details, skate stickers.
The objects should be crisp, readable, and cool; no messy collage, no dark background, no photorealistic 3D props.
Use the supplied black-label reference for typography: black rectangular padding strips with bold white pixel lettering, square corners, no glow.

Huge title exactly "2K17", based directly on the supplied flame emblem reference rather than invented lettering.
Do not write VNVNC.RU, weekday, time, venue, random words, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
If any year appears anywhere in the design, it must be 2017. Never show 2026.
No extra readable text beyond the 2K17 title.

Square 1:1 white-background pixel street-style poster.
""",
]


# SUMMER CAMP VARIATIONS - pure white pixelated elite sports camp poster (9:16 vertical)
SUMMER_CAMP_VARIATIONS = [
    """SUMMER CAMP - PURE WHITE PIXEL SPORTS POSTER (VERTICAL 9:16)

Create ONE SINGLE CENTERED FULL-COLOR 9:16 poster. No grid. No strip. No separate frames.

ABSOLUTE #1 PRIORITY - EXACT PEOPLE, EXACT FACES, EXACT CLOTHING:
- Preserve the exact real faces and full people count from the source photo.
- Keep hair, skin tone, expression, body proportions, pose, clothing silhouette, and visible clothing text/logos exactly.
- People remain recognizable and human; do not replace them with generic athletes.
- Apply the theme to the surrounding scene, props, border, and light accessories only.

VISUAL DIRECTION:
- Pure white #FFFFFF background only. No black background, no gray wall, no room, no floor line.
- Pixelated 2D style inherited from the Office Core theme: crisp square pixels, sharp outlines, chunky dithering, premium object-sheet layout.
- Replace all office objects with elite summer sports camp objects: tennis balls, white tennis rackets, lime-green yoga mat, basketball, soccer ball, whistle, sweatbands, sport socks, sunscreen tube, water bottle, folded polo shirt, score card shapes, palm leaves, hedge texture strips, and country-club lawn accents.
- Palette: tennis-ball neon yellow-green, deep athletic forest green, cream white, navy shadow accents, tiny sunset peach highlights.
- Keep object placement neat, expensive, graphic, and readable. The background must stay mostly white.
- No office props, no CRTs, no red telephones, no printers, no desk items, no corporate vibe, no photorealistic 3D props.

TEXT AND BRANDING:
- Use the supplied SUMMER CAMP emblem reference as the official top logo/title.
- Huge title exactly "SUMMER CAMP", matching the emblem's varsity sports lockup and tennis-ball green palette as closely as possible.
- Leave the bottom 12-15% of the poster as clean pure white empty space for a system-rendered footer.
- Do not write VNVNC.RU, weekday, time, venue, fake dates, year, or "МСК" anywhere. The app adds the real footer after generation.
- No other readable words except the SUMMER CAMP title and tiny non-readable scoreboard glyphs.

OUTPUT:
- one centered pure-white pixelated elite summer sports camp poster
- exact likeness, crisp 2D sports objects, premium clean layout
- vertical 9:16
""",
    """SUMMER CAMP - WHITE TENNIS CLUB ICON POSTER (VERTICAL 9:16)

Create a single vertical 9:16 poster on a pure white background.

IDENTITY LOCK:
- Preserve exact likeness and every person from the input photo.
- Same face, hair, skin tone, expression, body proportions, and real outfit identity.
- Preserve visible clothing text and logos letter-for-letter.
- Do not beautify, costume-swap, cartoon-replace, or turn people into generic tennis players.

STYLE:
- Clean pixelated 2D summer sports camp art, like a premium 1990s icon set expanded into a country-club party poster.
- People may be lightly pixel-rendered while remaining unmistakably the same real people.
- Sports camp objects are the hero styling: tennis balls, white rackets, rolled lime yoga mat, basketball, soccer ball, whistle, water bottle, sweatbands, sunglasses, sunscreen, socks, palm leaves, ivy hedge strips, and tiny court-line geometry.
- Pure white negative space is mandatory. Use tennis yellow-green, forest green, cream, navy, and small peach highlights with tight control.
- Make it cool and graphic, not clip art, not messy AI clutter, not a generic fitness ad.

BRANDING:
- Recreate the supplied SUMMER CAMP emblem as the huge top logo/title as closely as possible.
- Leave the bottom 12-15% of the poster as clean pure white empty space for the system footer.
- Do not write VNVNC.RU, weekday, time, venue, fake scoreboard text, fake dates, or "photobooth" wording. The app adds the real footer after generation.
- No other readable text beyond the SUMMER CAMP title.

OUTPUT:
- pure white Summer Camp pixel poster, exact likeness, elite sports-camp objects
- vertical 9:16
""",
]


SUMMER_CAMP_SQUARE_VARIATIONS = [
    """SUMMER CAMP - PURE WHITE PIXEL SPORTS POSTER (SQUARE 1:1)

One square single-image composition only. No grid, no strip, no panels.
Preserve exact real faces, full group, hair, skin tone, expression, body proportions, clothing silhouette, and visible clothing text exactly.

Use a pure white #FFFFFF background with crisp pixelated 2D elite sports camp objects around the people:
tennis balls, white tennis rackets, lime yoga mat, basketball, soccer ball, whistle, sweatbands, socks, sunscreen tube, water bottle, palm leaves, hedge strips, and court-line shapes.
Keep the composition clean, expensive, graphic, and mostly white. No office props, no black void, and no 3D render.

Huge title exactly "SUMMER CAMP" using the supplied emblem reference as the actual top logo.
Do not write VNVNC.RU, weekday, time, venue, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
No extra readable text beyond the SUMMER CAMP title.

Square 1:1 pure-white pixel summer sports camp poster.
""",
    """SUMMER CAMP - WHITE TENNIS CLUB ICON POSTER (SQUARE 1:1)

One square full-color poster. Preserve exact likeness and every person from the input photo.
Pure white studio void. Premium pixelated 2D object-sheet style with tennis-ball yellow-green, deep forest green, cream white, and navy accents.

Surround the people with elite sports camp objects: tennis balls, rackets, yoga mat, basketball, soccer ball, whistle, water bottle, sunscreen, sweatbands, palm leaves, ivy hedge strips, and court lines.
The sports objects should be crisp, readable, and cool; no messy collage, no dark background, no photorealistic 3D props.

Huge title exactly "SUMMER CAMP", based directly on the supplied emblem reference rather than invented lettering.
Do not write VNVNC.RU, weekday, time, venue, random words, fake dates, or "photobooth" wording. Leave clean white bottom space for the app's real footer.
No extra readable text beyond the SUMMER CAMP title.

Square 1:1 white-background pixel sports-camp poster.
""",
]


# CIRCUS MAXIMUS VARIATIONS - Octane 3D Creepy Circus (9:16 vertical)
CIRCUS_MAXIMUS_VARIATIONS = [
    """CIRCUS MAXIMUS — CREEPY CIRCUS POSTER (VERTICAL 9:16)

Octane 3D render style. Premium photorealistic 3D quality — NOT cartoon, NOT flat illustration.

STYLE: Haunted carnival poster come to life. Red and white candy-stripe tent pattern elements frame the edges. 
Slightly sinister atmosphere — creepy clowns, twisted balloons, flickering carnival lights.
Dark shadows with volumetric uplighting from below casting eerie illumination.

SUBJECT: Person from the reference photo rendered as a creepy ringmaster / carnival performer. 
Preserve EXACT facial likeness and ALL text on clothing letter-for-letter.
If multiple people, include ALL of them as circus performers together.

BACKGROUND: Pure black (#000000) void with floating circus elements — torn tickets, balloon animals, spotlight beams.

CARD/BORDER: Vintage circus poster frame with ornate red-and-white striped border. 
Slightly weathered paper texture, gold foil accents. Faint creepy clown silhouettes in the border corners.

TEXT:
TOP: "CIRCUS MAXIMUS" in bold theatrical 3D chrome-red circus lettering with slight glow
BOTTOM: "VNVNC.RU" left, time right, "Конюшенная 2В" below

NO per-frame timestamps. Date appears once only. No МСК suffix.
Strictly single-image composition — no grid, no strip, no four-frame layout.
BRANDING: "VNVNC" tall condensed white letters in thin red rectangular border.""",

    """CIRCUS MAXIMUS — DARK CARNIVAL PORTRAIT (VERTICAL 9:16)

Octane 3D render. Premium dark-toy style — glossy vinyl skin, enlarged glassy eyes, unnervingly perfect.

STYLE: Nightmarish carnival diorama. Red and white striped tent canopy overhead. 
Creepy clown dolls peering from shadows. Twisted carousel horses. Flickering neon ticket booth glow.
Deep crimson, bone white, and absolute black palette. Eerie volumetric fog.

SUBJECT: Reference photo person as a vinyl collectible doll carnival performer — ringmaster coat, top hat with playing cards tucked in band.
Preserve EXACT likeness and ALL clothing text. All people from source included.

BACKGROUND: Pure black void. Floating playing cards, torn circus posters, balloon strings dangling down.

CARD: Thick worn circus poster border. Red candy stripes with tarnished gold trim. 
Faded blood splatter pattern around the inner frame edge. Stamped admission ticket in corner.

TEXT:
TOP: "CIRCUS MAXIMUS" in cracked blood-red marquee lettering
BOTTOM: "VNVNC.RU" left, time right, "Конюшенная 2В" below

NO per-frame timestamps. Single image. No grid.
BRANDING: "VNVNC" tall condensed white letters in thin red rectangular border.""",

    """CIRCUS MAXIMUS — FUNHOUSE MIRROR POSTER (VERTICAL 9:16)

Octane 3D render. Photorealistic funhouse mirror aesthetic.

STYLE: Twisted carnival funhouse — distorted mirrors, creaking floorboards, flickering Edison bulbs.
Red and white tent stripes wrapping around the frame like a candy wrapper. 
Haunted circus atmosphere with subtle menace — a clown's painted grin in the shadows.
Predominantly black with blood-red and bone-white accents.

SUBJECT: Person from reference photo as a haunted funhouse attraction — slightly distorted mirror effect on edges, normal in center.
Preserve EXACT facial likeness and ALL clothing text letter-for-letter. Keep full group if multiple people.

BACKGROUND: Pure black (#000000). Scattered juggling pins, a unicycle wheel, floating confetti frozen mid-air.

CARD: Distressed carnival admission ticket style border. Red and white stripes with torn edges.
Rustic rope border detail. Old-fashioned perforated edge on one side.

TEXT:
TOP: "CIRCUS MAXIMUS" in vintage circus woodblock print lettering
BOTTOM: "VNVNC.RU" left, time right, "Конюшенная 2В" below

NO per-frame timestamps. Date once only. Single image composition. No grid.
BRANDING: "VNVNC" tall condensed white letters in thin red rectangular border.""",
]

# CIRCUS MAXIMUS SQUARE VARIATIONS - Octane 3D Creepy Circus (1:1 square)
CIRCUS_MAXIMUS_SQUARE_VARIATIONS = [
    """CIRCUS MAXIMUS — CREEPY CIRCUS (SQUARE 1:1)

Octane 3D render style. Premium photorealistic 3D.

Haunted carnival portrait. Red and white candy-stripe frame elements. 
Eerie clown motifs in the border. Deep crimson, bone white, pure black.
Person from reference photo as a creepy ringmaster — preserve EXACT likeness and ALL clothing text.

Pure black background. Floating circus elements — balloons, spotlight beams, torn tickets.
Vintage circus poster border with red stripes and gold trim. Weathered paper texture.

BRANDING: "VNVNC" tall condensed white letters in thin red rectangular border.
Single image — no grid, no strip, no collage.""",

    """CIRCUS MAXIMUS — DARK TOY CIRCUS (SQUARE 1:1)

Octane 3D render. Dark vinyl collectible doll style.

Glossy doll-skin figure of the reference person as a creepy circus performer.
Red and white striped big top elements. Haunted carnival atmosphere.
Bone white, blood red, absolute black palette.

Pure black void background. Floating balloon animals, playing cards, carousel lights.
Ornate circus poster frame with candy-stripe border. Tarnished gold edge detail.

BRANDING: "VNVNC" tall condensed white letters in thin red rectangular border.
Single image — no grid, no collage, no split panels.""",
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
    # PHOTOBOOTH ФЕЙФОРИЯ MODE - 9:16 vertical enchanted fairy forest theme
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_FEYPHORIA: "FEYPHORIA_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH ФЕЙФОРИЯ SQUARE MODE - 1:1 square fairy forest for LED
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_FEYPHORIA_SQUARE: "FEYPHORIA_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH FIESTA MODE - 9:16 vertical Spanish realism party style
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_FIESTA: "FIESTA_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH FIESTA SQUARE MODE - 1:1 square Spanish realism for LED
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE: "FIESTA_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH BIG CITY LIFE MODE - 9:16 vertical 90s NYC graffiti theme
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE: "BIGCITYLIFE_VARIATION",  # 9:16 for label

    # =========================================================================
    # PHOTOBOOTH BIG CITY LIFE SQUARE MODE - 1:1 square NYC graffiti for LED
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE_SQUARE: "BIGCITYLIFE_SQUARE_VARIATION",  # 1:1 for display

    # =========================================================================
    # PHOTOBOOTH BRAINROT MODE - 9:16 vertical single-image brainrot poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BRAINROT: "BRAINROT_VARIATION",

    # =========================================================================
    # PHOTOBOOTH BRAINROT SQUARE MODE - 1:1 square single-image brainrot poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BRAINROT_SQUARE: "BRAINROT_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH WEDDING MODE - 9:16 vertical single-image wedding postcard
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_WEDDING: "WEDDING_VARIATION",

    # =========================================================================
    # PHOTOBOOTH WEDDING SQUARE MODE - 1:1 square single-image wedding postcard
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_WEDDING_SQUARE: "WEDDING_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH WHATSAPP MODE - 9:16 vertical single-image WhatsApp postcard
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_WHATSAPP: "WHATSAPP_VARIATION",

    # =========================================================================
    # PHOTOBOOTH WHATSAPP SQUARE MODE - 1:1 square single-image WhatsApp postcard
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_WHATSAPP_SQUARE: "WHATSAPP_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SLAVIC SOUL MODE - 9:16 vertical slavic-core luxury poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL: "SLAVIC_SOUL_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SLAVIC SOUL SQUARE MODE - 1:1 square slavic-core luxury poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL_SQUARE: "SLAVIC_SOUL_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SLAVIC TALES MODE - 9:16 vertical slavic fairy-tale poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES: "SLAVIC_TALES_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SLAVIC TALES SQUARE MODE - 1:1 square slavic fairy-tale poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES_SQUARE: "SLAVIC_TALES_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH BANYA CHIC MODE - 9:16 vertical decadent bathhouse poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BANYA_CHIC: "BANYA_CHIC_VARIATION",

    # =========================================================================
    # PHOTOBOOTH BANYA CHIC SQUARE MODE - 1:1 square decadent bathhouse poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_BANYA_CHIC_SQUARE: "BANYA_CHIC_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH VNVNC B'DAY MODE - 9:16 vertical luxury birthday poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY: "VNVNC_BDAY_VARIATION",

    # =========================================================================
    # PHOTOBOOTH VNVNC B'DAY SQUARE MODE - 1:1 square luxury birthday poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY_SQUARE: "VNVNC_BDAY_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH CIRCUS MAXIMUS MODE - 9:16 vertical creepy circus poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS: "CIRCUS_MAXIMUS_VARIATION",

    # =========================================================================
    # PHOTOBOOTH CIRCUS MAXIMUS SQUARE MODE - 1:1 square creepy circus poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS_SQUARE: "CIRCUS_MAXIMUS_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH MTV NIGHT MODE - 9:16 vertical glossy MTV poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_MTV_NIGHT: "MTV_NIGHT_VARIATION",

    # =========================================================================
    # PHOTOBOOTH MTV NIGHT SQUARE MODE - 1:1 square glossy MTV poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_MTV_NIGHT_SQUARE: "MTV_NIGHT_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SHADOW KINGDOM MODE - 9:16 vertical gothic chrome castle poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM: "SHADOW_KINGDOM_VARIATION",

    # =========================================================================
    # PHOTOBOOTH SHADOW KINGDOM SQUARE MODE - 1:1 square gothic chrome castle poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM_SQUARE: "SHADOW_KINGDOM_SQUARE_VARIATION",

    # =========================================================================
    # PHOTOBOOTH CANDY SHOP MODE - 9:16 vertical white candy luxury poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_CANDY_SHOP: "CANDY_SHOP_VARIATION",

    # =========================================================================
    # PHOTOBOOTH CANDY SHOP SQUARE MODE - 1:1 square white candy luxury poster
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH_CANDY_SHOP_SQUARE: "CANDY_SHOP_SQUARE_VARIATION",
    CaricatureStyle.PHOTOBOOTH_STREET_HEAT: "STREET_HEAT_VARIATION",
    CaricatureStyle.PHOTOBOOTH_STREET_HEAT_SQUARE: "STREET_HEAT_SQUARE_VARIATION",
    CaricatureStyle.PHOTOBOOTH_OFFICE_CORE: "OFFICE_CORE_VARIATION",
    CaricatureStyle.PHOTOBOOTH_OFFICE_CORE_SQUARE: "OFFICE_CORE_SQUARE_VARIATION",
    CaricatureStyle.PHOTOBOOTH_2K17: "TWO_K17_VARIATION",
    CaricatureStyle.PHOTOBOOTH_2K17_SQUARE: "TWO_K17_SQUARE_VARIATION",
    CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP: "SUMMER_CAMP_VARIATION",
    CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP_SQUARE: "SUMMER_CAMP_SQUARE_VARIATION",

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
        extra_reference_images: Optional[List[Tuple[bytes, str]]] = None,
        prompt_variation_index: Optional[int] = None,
    ) -> Optional[Caricature]:
        """Generate a caricature based on a reference photo.

        Sends the photo directly to Gemini 3 Pro Image Preview which
        can generate styled images based on reference photos.

        Args:
            reference_photo: User's photo as bytes
            style: Caricature style to use
            size: Output size (width, height)
            personality_context: Optional personality traits from questions
            extra_reference_images: Additional branding or style reference images

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
                "FEYPHORIA_VARIATION": FEYPHORIA_VARIATIONS,
                "FEYPHORIA_SQUARE_VARIATION": FEYPHORIA_SQUARE_VARIATIONS,
                "FIESTA_VARIATION": FIESTA_VARIATIONS,
                "FIESTA_SQUARE_VARIATION": FIESTA_SQUARE_VARIATIONS,
                "BIGCITYLIFE_VARIATION": BIGCITYLIFE_VARIATIONS,
                "BIGCITYLIFE_SQUARE_VARIATION": BIGCITYLIFE_SQUARE_VARIATIONS,
                "BRAINROT_VARIATION": BRAINROT_VARIATIONS,
                "BRAINROT_SQUARE_VARIATION": BRAINROT_SQUARE_VARIATIONS,
                "WEDDING_VARIATION": WEDDING_VARIATIONS,
                "WEDDING_SQUARE_VARIATION": WEDDING_SQUARE_VARIATIONS,
                "WHATSAPP_VARIATION": WHATSAPP_VARIATIONS,
                "WHATSAPP_SQUARE_VARIATION": WHATSAPP_SQUARE_VARIATIONS,
                "SLAVIC_SOUL_VARIATION": SLAVIC_SOUL_VARIATIONS,
                "SLAVIC_SOUL_SQUARE_VARIATION": SLAVIC_SOUL_SQUARE_VARIATIONS,
                "SLAVIC_TALES_VARIATION": SLAVIC_TALES_VARIATIONS,
                "SLAVIC_TALES_SQUARE_VARIATION": SLAVIC_TALES_SQUARE_VARIATIONS,
                "BANYA_CHIC_VARIATION": BANYA_CHIC_VARIATIONS,
                "BANYA_CHIC_SQUARE_VARIATION": BANYA_CHIC_SQUARE_VARIATIONS,
                "VNVNC_BDAY_VARIATION": VNVNC_BDAY_VARIATIONS,
                "VNVNC_BDAY_SQUARE_VARIATION": VNVNC_BDAY_SQUARE_VARIATIONS,
                "CIRCUS_MAXIMUS_VARIATION": CIRCUS_MAXIMUS_VARIATIONS,
                "CIRCUS_MAXIMUS_SQUARE_VARIATION": CIRCUS_MAXIMUS_SQUARE_VARIATIONS,
                "MTV_NIGHT_VARIATION": MTV_NIGHT_VARIATIONS,
                "MTV_NIGHT_SQUARE_VARIATION": MTV_NIGHT_SQUARE_VARIATIONS,
                "SHADOW_KINGDOM_VARIATION": SHADOW_KINGDOM_VARIATIONS,
                "SHADOW_KINGDOM_SQUARE_VARIATION": SHADOW_KINGDOM_SQUARE_VARIATIONS,
                "CANDY_SHOP_VARIATION": CANDY_SHOP_VARIATIONS,
                "CANDY_SHOP_SQUARE_VARIATION": CANDY_SHOP_SQUARE_VARIATIONS,
                "STREET_HEAT_VARIATION": STREET_HEAT_VARIATIONS,
                "STREET_HEAT_SQUARE_VARIATION": STREET_HEAT_SQUARE_VARIATIONS,
                "OFFICE_CORE_VARIATION": OFFICE_CORE_VARIATIONS,
                "OFFICE_CORE_SQUARE_VARIATION": OFFICE_CORE_SQUARE_VARIATIONS,
                "TWO_K17_VARIATION": TWO_K17_VARIATIONS,
                "TWO_K17_SQUARE_VARIATION": TWO_K17_SQUARE_VARIATIONS,
                "SUMMER_CAMP_VARIATION": SUMMER_CAMP_VARIATIONS,
                "SUMMER_CAMP_SQUARE_VARIATION": SUMMER_CAMP_SQUARE_VARIATIONS,
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
                variations = variation_map[style_prompt]
                if prompt_variation_index is None:
                    style_prompt = random.choice(variations)
                else:
                    style_prompt = variations[prompt_variation_index % len(variations)]

            # Build personality-aware prompt
            personality_hint = ""
            if personality_context:
                personality_hint = f"""
PERSONALITY INSIGHT (use to inform the artwork's expression and energy):
{personality_context}

Express their personality through the art - confident people get powerful poses,
introverts get serene expressions, risk-takers get dynamic energy, etc.
"""

            reference_asset_hint = ""
            if extra_reference_images:
                reference_asset_hint = """
ADDITIONAL REFERENCE IMAGES:
- Extra reference images are official style or branding anchors, not extra people.
- The first extra reference image is the official party emblem/logo for this theme. Treat it as a brand lockup, not loose inspiration.
- Reproduce the emblem's exact wording, layout, typography attitude, border/shape language, and visual hierarchy as closely as the model allows.
- Do not invent a new event logo or substitute generic lettering when an official emblem reference is attached.
- Never replace the real people from the photo with the emblem or logo.
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
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA,
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_FIESTA,
                CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BRAINROT,
                CaricatureStyle.PHOTOBOOTH_BRAINROT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_WEDDING,
                CaricatureStyle.PHOTOBOOTH_WEDDING_SQUARE,
                CaricatureStyle.PHOTOBOOTH_WHATSAPP,
                CaricatureStyle.PHOTOBOOTH_WHATSAPP_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC,
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC_SQUARE,
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY,
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY_SQUARE,
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS,
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS_SQUARE,
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT,
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM,
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM_SQUARE,
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP,
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP_SQUARE,
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT,
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE,
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE_SQUARE,
                CaricatureStyle.PHOTOBOOTH_2K17,
                CaricatureStyle.PHOTOBOOTH_2K17_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP,
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP_SQUARE,
            )
            is_boilingroom_style = style in (
                CaricatureStyle.PHOTOBOOTH,
                CaricatureStyle.PHOTOBOOTH_SQUARE,
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
            is_fiesta_style = style in (
                CaricatureStyle.PHOTOBOOTH_FIESTA,
                CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE,
            )
            is_bigcitylife_style = style in (
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE_SQUARE,
            )
            is_brainrot_style = style in (
                CaricatureStyle.PHOTOBOOTH_BRAINROT,
                CaricatureStyle.PHOTOBOOTH_BRAINROT_SQUARE,
            )
            is_wedding_style = style in (
                CaricatureStyle.PHOTOBOOTH_WEDDING,
                CaricatureStyle.PHOTOBOOTH_WEDDING_SQUARE,
            )
            is_whatsapp_style = style in (
                CaricatureStyle.PHOTOBOOTH_WHATSAPP,
                CaricatureStyle.PHOTOBOOTH_WHATSAPP_SQUARE,
            )
            is_slavic_soul_style = style in (
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL_SQUARE,
            )
            is_slavic_tales_style = style in (
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES_SQUARE,
            )
            is_banya_chic_style = style in (
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC,
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC_SQUARE,
            )
            is_vnvnc_bday_style = style in (
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY,
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY_SQUARE,
            )

            is_circus_maximus_style = style in (
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS,
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS_SQUARE,
            )
            is_mtv_night_style = style in (
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT,
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT_SQUARE,
            )
            is_shadow_kingdom_style = style in (
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM,
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM_SQUARE,
            )
            is_candy_shop_style = style in (
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP,
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP_SQUARE,
            )
            is_street_heat_style = style in (
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT,
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT_SQUARE,
            )
            is_office_core_style = style in (
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE,
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE_SQUARE,
            )
            is_2k17_style = style in (
                CaricatureStyle.PHOTOBOOTH_2K17,
                CaricatureStyle.PHOTOBOOTH_2K17_SQUARE,
            )
            is_summer_camp_style = style in (
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP,
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP_SQUARE,
            )

            if is_brainrot_style:
                color_instruction = """- FULL COLOR — cursed meme palette: toxic lime, oversaturated cyan, tomato red, fake gold, candy magenta, JPEG-white glow
- Single centered poster composition only, no grid and no separate frames
- Exact human faces are mandatory; do not replace faces with animal heads
- Bodies, costumes, props, and silhouettes can become Italian brainrot hybrid creatures while keeping the real people recognizable
- Meme doodles, ugly WordArt, sticker clutter, fake glitter, repost-JPEG ugliness are required
- If multiple people are present, keep the full group together in one shared composition"""
            elif is_wedding_style:
                color_instruction = """- FULL COLOR — cheap wedding palette: bubblegum pink, satin white, fake gold, burgundy roses, champagne beige, over-soft skin tones
- Single centered postcard composition only, no grid and no separate frames
- Preserve exact faces and whole-group likeness first
- Allow wardrobe/accessory wedding styling, but never lose recognizability
- Add tacky wedding decorations, glossy print texture, bad Photoshop glow, and meme doodles"""
            elif is_whatsapp_style:
                color_instruction = """- FULL COLOR — forwarded-postcard palette: bright emerald, sky blue gradient, glitter gold, rose pink, candle amber, floral neon
- Single centered postcard composition only, no grid and no separate frames
- Preserve exact faces and the full group together in one image
- Add grandma-WhatsApp postcard decor: glitter flowers, swans, kittens, lace, glow, stickers, foil effects, and meme doodles"""
            elif is_slavic_soul_style:
                color_instruction = """- FULL COLOR — slavic-core luxury palette: velvet black, lacquer red, antique gold, amber, champagne ivory, cranberry crimson, fur brown
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Pure black luxury background, floating curated props, and rich warm amber lighting are mandatory
- Human faces must stay photoreal and exact; props and styling may become hyper-polished luxury still life
- If multiple people are present, keep the full group together as one fashion-campaign clique
- Huge ornamental gold title lettering and elegant footer branding are required"""
            elif is_slavic_tales_style:
                color_instruction = """- FULL COLOR — enchanted Slavic fairy-tale palette: moonlit indigo, raven black, old gold, garnet red, birch white, ember orange, icy ivory
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Build a real fairy-tale environment with atmosphere, depth, and magical objects; not a pure black void
- Human faces must stay photoreal and exact while the world becomes luxurious storybook fantasy
- If multiple people are present, keep the full group together as an ensemble cast with equal presence
- Huge ornamental gold title lettering and elegant footer branding are required"""
            elif is_banya_chic_style:
                color_instruction = """- FULL COLOR — decadent bathhouse palette: cedar honey, steam white, brass gold, towel cream, dill green, caviar black, cranberry red, warm amber skin tones
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Build a humid steam-room or bathhouse interior; not a pure black void and not a fairy-tale scene
- Human faces must stay photoreal and exact while props, styling, and atmosphere become glossy decadent bathhouse editorial
- If multiple people are present, keep the full group together in one shared bathhouse ritual scene
- Huge ornamental gold title lettering and elegant footer branding are required"""
            elif is_vnvnc_bday_style:
                color_instruction = """- FULL COLOR — luxury birthday palette: matte cake cream, velvet black, lacquer crimson, chrome silver, pearl white, candle amber, champagne gold
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Prefer pure black void or black editorial negative space with floating premium props
- Human faces must stay photoreal and exact; birthday objects may become hyper-polished luxury still life
- If multiple people are present, keep the full group together in one shared hero composition
- Huge title lettering, elegant footer branding, and emblem-driven VNVNC visual language are required"""
            elif is_circus_maximus_style:
                color_instruction = """- FULL COLOR — creepy circus palette: blood crimson, bone white, pitch black, tarnished gold, candy-stripe red-and-white
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Prefer pure black void background with floating circus elements
- Octane 3D premium render quality — glossy materials, volumetric eerie uplighting, cinematic shadows
- Red and white candy-stripe border pattern, vintage circus poster frame aesthetic
- Haunted carnival atmosphere — slightly sinister, never cute or whimsical
- If multiple people are present, keep the full group together in one shared circus scene
- Bold theatrical "CIRCUS MAXIMUS" title lettering in chrome-red circus font is required"""
            elif is_mtv_night_style:
                color_instruction = """- FULL COLOR — glossy 90s MTV palette: liquid chrome, LCD white, electric magenta, deep-space black, candy purple, cyan highlights
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Prefer black editorial negative space with floating chrome, acrylic, and gel-plastic broadcast objects
- Human faces must stay photoreal and exact while props and layout become hyper-designed TV-network pop spectacle
- If multiple people are present, keep the full group together in one shared hero composition
- Huge sharp MTV-style title lettering, premium logo language, and elegant footer branding are required
- No AI slop: no waxy skin, no muddy glow fog, no generic club flyer clutter"""
            elif is_shadow_kingdom_style:
                color_instruction = """- FULL COLOR — Shadow Kingdom palette: moonlit black, gunmetal, mirror chrome, cold silver, ruby red, dark wine banners, blue jewel highlights, fire amber
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Premium Octane 3D gothic castle poster: black steel, chrome bevels, crown/sword motifs, storm sky, castle towers, red banners, fire braziers, deep parallax
- Human faces must stay photoreal and exact; wardrobe/frame/environment may become polished dark fantasy royal key art
- If multiple people are present, keep the full group together in one shared royal hero composition
- Huge clean chrome gothic title lettering reading exactly SHADOW KINGDOM and elegant footer branding are required
- No AI slop: no waxy skin, no muddy fog over faces, no random extra text, no generic fantasy-game clutter"""
            elif is_candy_shop_style:
                color_instruction = """- FULL COLOR — pure white and pink candy boutique palette: #FFFFFF background, soft pink, blush, pearl white, pale chrome, rose reflections
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Pure white studio background is mandatory; no black void, no room, no heavy texture
- Human appearance is identity-locked: exact face, hair, skin tone, expression, body proportions, pose, and outfit identity from the source photo must stay unchanged
- Props, surrounding objects, typography, background, lighting, and light accessories may become a polished modern candy-boutique campaign
- Keep objects minimal: a few lollipops, sugar glass, wrapped candies, pearl sprinkles, soft chrome; no folk motifs and no busy collage
- If multiple people are present, keep the full group together in one shared hero composition
- Use the supplied candy-shop emblem reference as the official top logo/title; match its layout and candy-boutique emblem shape as closely as possible
- Huge clean title lettering reading exactly CANDY SHOP and elegant footer branding are required
- No AI slop: no waxy skin, no muddy glow, no random extra text, no childish flyer clutter"""
            elif is_street_heat_style:
                color_instruction = """- FULL COLOR — premium West Coast palette on a pure white background: creamy white, warm paper white, rich denim blue, basketball orange, polished gold, pale chrome, deep asphalt accents
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Photoreal people with tactile instant-film / Polaroid object realism: creamy border, subtle fiber paper texture, soft analog grain, glossy flash chemistry
- West Coast street-luxury props only as restrained still-life accents: chrome palms, basketball, polished dice, chain motifs, lowrider chrome flashes
- White negative space must stay clean and premium
- No AI slop: no waxy skin, no cartoon game-art faces, no cheap graffiti clip-art, no random extra text, no muddy clutter
"""
            elif is_office_core_style:
                color_instruction = """- FULL COLOR — pure white pixel office palette: #FFFFFF background, IBM blue, error red, terminal green, beige plastic, copier-paper white, black pixel outlines
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Pure white studio background is mandatory; no black void, no gray wall, no room, no dark cyber tunnel
- Crisp pixelated 2D office-object art is mandatory: red corded telephone, beige CRT, old keyboard, fax, printer, paper stacks, folders, floppy disks, calculator, stapler, mouse cursor
- Human identity stays exact; theme changes only the rendered art style, props, typography, and non-obscuring accessories
- Keep the layout clean, mostly white, and premium; no messy collage and no random extra text
- Use the supplied office-core emblem reference as the official top logo/title; match its pixel-office lockup as closely as possible
"""
            elif is_2k17_style:
                color_instruction = """- FULL COLOR — pure white 2K17 street palette: #FFFFFF background, black pixel outlines, flame red, hot yellow, acid lime, royal blue, asphalt gray, tiny rosé pink highlights
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Pure white studio background is mandatory; no black void, no gray wall, no dark club room
- Crisp pixelated 2D 2017 street-object art is mandatory: fidget spinners, rosé, iPhone 7, wired white earbuds, chokers, fishnet patterns, Vans/checkerboard shoe details, track pants, puffer jackets, chains, yellow industrial strap accents, skate stickers
- Typography treatment must use the supplied black-label reference: solid black rectangular padding behind bold white blocky pixel letters, square corners, high contrast
- Human identity stays exact; theme changes only the rendered art style, props, typography, and non-obscuring accessories
- Keep the layout clean, mostly white, stylish, and premium; no messy collage and no random extra text
- Use the supplied 2K17 flame emblem reference as the official top logo/title; match its flame lockup as closely as possible
"""
            elif is_summer_camp_style:
                color_instruction = """- FULL COLOR — pure white elite summer sports palette: #FFFFFF background, tennis-ball neon yellow-green, deep athletic forest green, cream white, navy outline accents, small sunset peach highlights
- Strictly single-image composition (no grid, no strip, no four-frame photobooth layout)
- Pure white studio background is mandatory; no black void, no gray wall, no generic gym, no dark field
- Crisp pixelated 2D sports-camp object art is mandatory: tennis balls, white rackets, yoga mat, basketball, soccer ball, whistle, water bottle, sweatbands, sunscreen, palm leaves, ivy hedge strips, court-line shapes
- Human identity stays exact; theme changes only the rendered art style, props, typography, and non-obscuring accessories
- Keep the layout clean, mostly white, elite, and premium; no messy collage and no random extra text
- Use the supplied SUMMER CAMP emblem reference as the official top logo/title; match its varsity sports lockup as closely as possible
"""
            elif is_bigcitylife_style:
                color_instruction = """- FULL COLOR — 90s NYC palette: NYC cab yellow, graffiti red, concrete grey, night black, spray-can neon orange
- Strictly 2D graffiti character art — flat fills, bold spray-can outlines, paint drips and fades
- NOT photorealistic. NOT 3D. Like a legendary Bronx graffiti mural by TATS CRU or COPE2
- Wildstyle energy, raw and gritty, thick black outlines, spray fade effects, dripping paint
- 2D illustration with visible brushstroke/spray-can texture, zero 3D depth or shading"""
            elif is_boilingroom_style:
                color_instruction = """- FULL COLOR — mostly black, deep red, white, chrome silver, and true skin tones
- Strictly premium 2D illustrated club-poster art, NOT photorealistic, NOT 3D, NOT plastic
- Chromatic aberration, super wide angle, film grain, analog textures
- Strong likeness and exact clothing from the reference photo are mandatory
- Dark printed-paper feel, halftone traces, visible venue background, polished chrome headline"""
            elif is_fiesta_style:
                color_instruction = """- FULL COLOR — distinctly Spanish mediterranean print palette: deep red, paprika, burnt orange, olive, aged gold, warm cream
- High-end photorealistic editorial output with natural skin tones and realistic lighting
- No 3D render or toy doll treatment, no cartoon look, no plastic textures
- Preserve original scene and likeness while applying elegant Spanish nightlife mood
- Add tactile printed-material feel: matte paper grain, halftone traces, ink spread, poster texture, subtle registration imperfection
- Spanish visual motifs should be obvious but tasteful: feria poster energy, flamenco curves, tile-border accents, fan/carnation ornament language"""
            elif is_malchishnik_style:
                color_instruction = """- FULL COLOR — analog film palette: pushed warm yellows/ambers, boosted reds, slight green in shadows
- Disposable camera / Polaroid aesthetic — heavy film grain, blown center flash, chemical color shift
- Overexposed highlights, underexposed dark corners, light leaks at edges (orange/red burn)
- Authentic party photography feel — High likeness, real people, NOT an illustration"""
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

            prompt = f"""Create an artistic portrait OF THIS EXACT PERSON OR EXACT GROUP from the reference photo.

CRITICAL REQUIREMENTS:
- IDENTITY LOCK: preserve THE EXACT REAL PERSON OR REAL GROUP IN THE PHOTO. The output must look like the same people, not prettier substitutes, generic models, characters, or lookalikes.
- Preserve face shape, eyes, nose, mouth, jawline, skin tone, skin texture, hairline, hairstyle, hair color, facial hair, glasses, expression, height relationship, body proportions, pose, clothing silhouette, and visible clothing text/logos from the source photo.
- Style modifications are allowed only in the environment, color palette, lighting, typography, props, and non-obscuring accessories. Do not change personal appearance.
- Do not beautify, age, de-age, slim, widen, gender-swap, ethnicity-shift, change hair, change skin tone, change expression, change outfit identity, or cover/replace faces.
- If the reference photo contains multiple people, preserve the exact people count and keep every visible person in the final image with equal importance.
- Never crop a group photo down to one hero, never merge two people into one, and never replace a person with a prop or logo.
{color_instruction}
- TEXT LANGUAGE RULES (CRITICAL!!!):
  * The brand name "VNVNC" must ALWAYS stay in ENGLISH letters: V-N-V-N-C
  * NEVER translate or transliterate VNVNC to Russian (НЕ писать ВНВНЦ или что-то подобное!)
  * All OTHER text (labels, annotations, decorations) must be in RUSSIAN, ALL CAPS
  * NEVER add any year (2024, 2025, 2026, etc.) - just "VNVNC" alone if adding branding
  * Example: "VNVNC" is correct, "ВНВНЦ" or "VNVNC 2026" is WRONG!
{personality_hint}
{reference_asset_hint}
{style_prompt}

The result should be recognizable as THIS specific person, transformed artistically.
UNIQUENESS TOKEN: {uniqueness_token}
"""

            # Determine aspect ratio based on style
            # Photobooth uses 9:16 vertical format for better label layout
            if style in (
                CaricatureStyle.PHOTOBOOTH,
                CaricatureStyle.PHOTOBOOTH_VENICE,
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA,
                CaricatureStyle.PHOTOBOOTH_FIESTA,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,
                CaricatureStyle.PHOTOBOOTH_BRAINROT,
                CaricatureStyle.PHOTOBOOTH_WEDDING,
                CaricatureStyle.PHOTOBOOTH_WHATSAPP,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES,
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC,
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY,
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS,
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT,
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM,
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP,
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT,
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE,
                CaricatureStyle.PHOTOBOOTH_2K17,
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP,
            ):
                aspect_ratio = "9:16"
            else:
                aspect_ratio = "1:1"

            # Send photo directly to Gemini 3 Pro Image Preview
            # The model understands to use the photo as reference
            if is_brainrot_style:
                image_style = "Full-bleed Italian brainrot meme poster, surreal semi-realistic cursed 3D render, glossy materials, bad Photoshop cutout energy, repost JPEG artifacts, ugly outer glow, width-squeezed WordArt, dumb sparkles, exact human faces preserved"
            elif is_wedding_style:
                image_style = "Cheesy Russian countryside wedding postcard portrait, tacky glossy studio montage, satin drapes, fake gold, roses, doves, bad Photoshop glow, sentimental print texture"
            elif is_whatsapp_style:
                image_style = "Grandma WhatsApp greeting-card collage, glitter postcard portrait, flowers, swans, kittens, lace, glowing clip-art, forwarded JPEG aesthetic"
            elif is_slavic_soul_style:
                image_style = "Luxurious slavic-core fashion editorial poster, pure black velvet background, floating lacquered and gilded props, embossed gold lettering, premium still-life glamour, clique-like group staging, exact photoreal human faces preserved"
            elif is_slavic_tales_style:
                image_style = "Cinematic Slavic fairy-tale fashion tableau, enchanted moonlit environment, carved terem and forest magic details, premium live-action storybook fantasy, ensemble cast staging, exact photoreal human faces preserved"
            elif is_banya_chic_style:
                image_style = "Decadent Slavic bathhouse editorial portrait, steamy cedar-and-brass interior, humid luxury atmosphere, caviar-and-champagne absurd glamour, shared group scene, exact photoreal human faces preserved"
            elif is_mtv_night_style:
                image_style = "Glossy late-90s MTV network campaign poster, direct-flash fashion photography, liquid chrome and translucent candy-plastic objects, Y2K broadcast graphics, halftone print texture, exact photoreal human faces preserved"
            elif is_shadow_kingdom_style:
                image_style = "Premium Octane 3D gothic dark-fantasy castle poster, black steel and mirror chrome frame, beveled silver typography, crown and sword emblem, ruby red banners, blue jewel accents, firelight, storm moon, deep parallax, exact photoreal human faces preserved"
            elif is_candy_shop_style:
                image_style = "Premium Octane 3D modern candy boutique poster, pure white studio background, soft pink glossy candy objects, pale chrome and pearl accents, minimal luxury campaign layout, exact photoreal human faces preserved"
            elif is_street_heat_style:
                image_style = "Premium white-background West Coast instant-film campaign poster, tactile Polaroid object realism, creamy paper border, subtle analog grain, polished chrome palm and lowrider still-life accents, basketball energy, luxe dice, chain details, exact photoreal human faces preserved"
            elif is_office_core_style:
                image_style = "Pure white pixelated 2D office-core poster, crisp 1990s desktop UI icon style, chunky dithering, beige CRT computers, red corded telephone, fax machine, printer paper, folders, exact human likeness preserved"
            elif is_2k17_style:
                image_style = "Pure white pixelated 2D 2K17 street-style poster, black padded label typography with bold white pixel letters, chunky dithering, fidget spinners, rose wine, iPhone 7, wired earbuds, chokers, fishnets, Vans, track pants, exact human likeness preserved"
            elif is_summer_camp_style:
                image_style = "Pure white pixelated 2D elite summer sports camp poster, crisp tennis-club icon style, chunky dithering, tennis balls, white rackets, lime yoga mat, basketball, soccer ball, whistle, palm leaves, exact human likeness preserved"
            elif is_bigcitylife_style:
                image_style = "90s New York City graffiti character art, 2D spray-can illustration, wildstyle graffiti mural, raw and gritty NYC street art, TATS CRU / COPE2 style"
            elif is_boilingroom_style:
                image_style = "Premium 2D underground club poster illustration, drawn graphic art, chromatic aberration, super wide angle, film grain, analog textures, visible venue background, metallic chrome headline, exact likeness and exact clothing from reference photo"
            elif is_malchishnik_style:
                image_style = "Analog disposable camera photography, Polaroid film photo, heavy film grain, blown flash, warm pushed colors, party chaos, Hangover movie aesthetic"
            elif style == CaricatureStyle.PHOTOBOOTH_FIESTA or style == CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE:
                image_style = "Cinematic editorial photorealistic portrait photography, natural skin tones, premium nightlife club lighting, subtle filmic grain"
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
                extra_reference_images=extra_reference_images,
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
