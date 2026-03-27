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
                "FEYPHORIA_VARIATION": FEYPHORIA_VARIATIONS,
                "FEYPHORIA_SQUARE_VARIATION": FEYPHORIA_SQUARE_VARIATIONS,
                "FIESTA_VARIATION": FIESTA_VARIATIONS,
                "FIESTA_SQUARE_VARIATION": FIESTA_SQUARE_VARIATIONS,
                "BIGCITYLIFE_VARIATION": BIGCITYLIFE_VARIATIONS,
                "BIGCITYLIFE_SQUARE_VARIATION": BIGCITYLIFE_SQUARE_VARIATIONS,
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
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA,
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_FIESTA,
                CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE_SQUARE,
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

            if is_bigcitylife_style:
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
            if style in (
                CaricatureStyle.PHOTOBOOTH,
                CaricatureStyle.PHOTOBOOTH_VENICE,
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA,
                CaricatureStyle.PHOTOBOOTH_FIESTA,
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,
            ):
                aspect_ratio = "9:16"
            else:
                aspect_ratio = "1:1"

            # Send photo directly to Gemini 3 Pro Image Preview
            # The model understands to use the photo as reference
            if is_bigcitylife_style:
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
