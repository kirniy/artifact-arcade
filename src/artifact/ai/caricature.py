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
# BLACK AND WHITE for both LED display and thermal printer
# (Camera captures grayscale to avoid NoIR purple tint)
# TEXT RULES: Russian language, ALL CAPS, VERY LARGE readable
# NO example labels - model copies them literally
# VARIETY: Each prompt has multiple variations to avoid repetition
# =============================================================================

# ROAST VARIATIONS - Reddit/r/RoastMe style (18+) - BLACK AND WHITE
# Style: Isolated portrait, stunning minimal B&W, speech bubbles, club-themed doodles
# CRITICAL: DO NOT use example texts literally! Create ORIGINAL content for THIS PERSON!
ROAST_VARIATIONS = [
    """ISOLATE THE PERSON. Perfect BLACK AND WHITE drawing - stunning and MINIMAL.
r/RoastMe energy - BRUTAL but CREATIVE. What would Reddit say about THIS face?
Add HANDWRITTEN TEXT as SPEECH BUBBLES with savage RUSSIAN roasts.
DOODLES and SCRIBBLES of CLUB OBJECTS around: cocktails, disco balls, bottles, shot glasses.

Think "top comment on Reddit" - personal, specific, DEVASTATING but hilarious.
The roast must be SPECIFIC to THIS PERSON's actual appearance!
Look at their face, hair, expression, vibe - and roast THAT.
Black ink on white. Square. The kind of roast that makes you say "damn" and laugh.""",

    """STUNNING MINIMAL B&W PORTRAIT. Isolate this person, draw them PERFECTLY.
BRUTAL HONEST ROAST like r/RoastMe - find what's ACTUALLY roastable about THIS SPECIFIC PERSON.
SPEECH BUBBLES with YOUR OWN savage labels in RUSSIAN - be ORIGINAL, don't copy anything.
CLUB DOODLES scattered around: martini glasses, vinyl records, strobe lights, champagne.

NO GENERIC INSULTS - be SPECIFIC to THIS person's unique flaws.
You are a comedy WRITER. Don't copy - CREATE. Look at this person and
find what's ACTUALLY funny about them. Original observations only.
Clean portrait, chaotic party doodles. Square. Make it hurt (in a funny way).""",

    """ISOLATED PORTRAIT - perfect B&W, super minimal. ROAST BATTLE energy.
What would a standup comedian IMMEDIATELY notice about THIS person? Draw that.
HANDWRITTEN SPEECH BUBBLES in RUSSIAN with standup-worthy burns.
SCRIBBLE club themed objects: cocktail shakers, glow sticks, speakers, VIP wristbands.

BE ORIGINAL: Study the photo. What's weird? What's tryhard? What screams "roast me"?
Create roasts that are SPECIFIC to this face. No templates, no copying.
Like a mean caricature artist at a carnival who tells the TRUTH.
Stunning drawing meets savage comedy. Square.""",

    """PERFECT BLACK AND WHITE SKETCH. Isolate this person BEAUTIFULLY.
INTERNET ROAST DOODLE energy - what would Reddit say about THIS SPECIFIC face?
SPEECH BUBBLES with YOUR ORIGINAL savage humor in RUSSIAN - internet troll energy.
CLUB DOODLES around: beer bottles, dice, cards, ashtrays, party objects.

Find the MEME potential unique to THIS person. Exaggerate what makes THEM roastable.
CREATIVITY REQUIRED: Every person has something unique to roast. Find it.
Don't use any pre-written labels. Observe and create fresh burns for THIS face.
Beautiful portrait meets chaotic nightlife. Square. Original savage commentary only.""",
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

# PHOTOBOOTH VARIATIONS - Brazil/Copacabana theme photo booth grid
# NOTE: These prompts handle both single person AND groups - include ALL people from the photo!
# BRANDING: "VNVNC" appears ONCE as a banner at the bottom, NOT in each frame!
PHOTOBOOTH_VARIATIONS = [
    """Create a FUN BRAZIL PARTY PHOTO BOOTH 2x2 GRID image!

IMPORTANT: Look at the reference photo carefully!
- If there is ONE person: show that person in 4 different playful poses
- If there are MULTIPLE people: show the WHOLE GROUP together in all 4 frames!
ALL people from the reference MUST appear in each frame!

LAYOUT: A 2x2 grid of 4 photo booth frames:
- Frame 1: Big smiles, carnival energy, party vibes
- Frame 2: Silly faces, samba poses, fun expressions
- Frame 3: Peace signs, celebration poses, thumbs up
- Frame 4: Dancing poses, excited expressions, party energy

CRITICAL: Preserve EVERY person's likeness!
Each person's face, hair, and distinctive features must be recognizable in ALL 4 frames.

BRAZIL THEME DECORATIONS: Tropical frame border with palm leaves, exotic flowers, carnival feathers.
Colors: Brazilian flag (green, yellow, blue), tropical bright colors, carnival vibes!
Think Copacabana beach, Rio carnival, samba energy!

BRANDING: Add "VNVNC" as a SINGLE BANNER at the very bottom of the entire grid.
NOT in each photo frame - just ONE text banner below all 4 frames!
Tropical party style lettering with Brazilian flair.

High quality, joyful, professional photo booth aesthetic. Square aspect ratio.""",

    """BRAZIL CARNIVAL PHOTO BOOTH STRIP - 2x2 grid of fun poses!

FIRST: Count how many people are in the reference photo.
- ONE person? Show them solo in 4 different poses
- TWO or MORE people? Include the ENTIRE GROUP in each frame!
Never leave anyone out!

Create a classic photo booth layout:
- 4 frames arranged in a 2x2 grid
- Each frame shows THE SAME PEOPLE from the reference photo
- Poses: happy, dancing, excited, samba vibes

ESSENTIAL: EVERY person in the reference must appear in ALL 4 frames!
Same faces, same hair, same clothing - just different expressions.

TROPICAL FRAME: Palm leaves, exotic flowers, carnival feathers border.
BRIGHT COLORS: Green, yellow, blue (Brazil colors), tropical vibes!
Copacabana beach party energy, Rio carnival atmosphere!

BRANDING: "VNVNC" text appears ONCE as a decorative banner BELOW the 4-frame grid.
Do NOT put text inside each photo frame - only ONE banner at the bottom!
Tropical party font with Brazilian carnival elements.

Fun party atmosphere, professional photo booth quality. Square aspect ratio.""",

    """COPACABANA PARTY PHOTO BOOTH GRID - 4 fun poses!

CHECK THE REFERENCE: How many people are there?
- Single person: 4 different solo poses
- Group photo: ALL people together in each of the 4 frames!

2x2 photo booth layout:
- Top left: Genuine smiles, beach party vibes
- Top right: Funny faces, carnival expressions
- Bottom left: Dancing poses, samba energy
- Bottom right: Excited, tropical party mood

CRITICAL REQUIREMENT: EVERYONE from the reference appears in ALL 4 frames!
Same facial features, hairstyles, and outfits - just different expressions.
Do NOT omit anyone from the group!

BRAZIL DECORATIONS: Palm trees, tropical flowers, carnival feathers, beach vibes border.
COLORS: Brazilian green, yellow, blue with tropical accents.
Rio de Janeiro carnival energy, Copacabana beach party atmosphere!

BRANDING: Add "VNVNC" as a SINGLE banner text at the bottom of the entire image.
This text should appear ONLY ONCE, below all 4 photo frames - NOT inside each frame!
Tropical party style, Brazilian carnival font.

Joyful Brazil party photo booth energy! Square aspect ratio.""",
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
    # PHOTOBOOTH MODE - Christmas 2x2 photo booth grid (uses PHOTOBOOTH_VARIATIONS)
    # =========================================================================
    CaricatureStyle.PHOTOBOOTH: "PHOTOBOOTH_VARIATION",  # Will be replaced with random variation

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
