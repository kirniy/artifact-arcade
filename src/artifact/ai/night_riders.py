"""NIGHT RIDERS: recognizable guests in gritty nocturnal pixel-rendered 3D biker art."""
import random

SCENES = (
    "A midnight biker garage: massive Harley-Davidson-style V-twin cruisers behind the guests, wet concrete, industrial steel, guitar amplifier stacks, red furnace glow and cobalt lightning.",
    "A nocturnal heavy-metal backstage: chrome motorcycles, electric guitars and towering speaker cabinets, hot amber flames in the distance, cold blue spotlights through atmospheric smoke.",
    "A gritty outlaw motorcycle clubhouse after dark: two chrome V-twin cruisers behind the guests, studded black leather, chains, weathered metal and red neon reflections on wet asphalt.",
    "A thunderstorm highway pit stop at midnight: a chrome V-twin cruiser, storm clouds, branching electric-blue lightning, distant fire and heavy-metal stage lights against charcoal darkness.",
)


def build_prompt(variation_index=None):
    index = random.randrange(len(SCENES)) if variation_index is None else variation_index % len(SCENES)
    return f"""Create one premium NIGHT RIDERS / VNVNC biker-rock photobooth portrait.
IMAGE ROLES: Image 1 is the fixed underdrawing for ALL real guests. Image 2 is the
exact approved NIGHT RIDERS winged shield emblem. Images 3+ are closeups of those
same guests. Identity outranks style: preserve the exact guest count, individual
facial geometry, eye shape and spacing, nose, lips, jaw, ethnicity, skin tone, age,
hair, facial hair, glasses, expressions and natural asymmetry. Never replace them
with generic handsome bikers, models, strangers or an added crowd. No ethnicity
shift, face averaging or beauty template. Draw their actual faces, not anime faces.
HAIR AND BODY LOCK: Trace the source hairline, exact haircut and hair length for
each person, including buzz cuts and bald areas. No invented mohawks, long hair,
beards, tattoos, muscles, broadened shoulders or thinner bodies to make them bikers.
Keep their real body build. Preserve each eye opening, mouth shape and expression:
no invented angry biker grimaces, smiles, exposed teeth or widened eyes. If someone
looks down or has closed eyes, keep that exact expression and head pitch.
POSE LOCK: Keep each guest's original head angle, gaze, body posture, hand gestures,
relative scale, spacing and overlap. Do not seat standing guests on bikes or invent
raised arms, instruments in their hands or different expressions. Bikes and stage
props are beside or behind them, never over their faces or body silhouettes.

SCENE: {SCENES[index]}
Heavy metal, rock clubs, motorcycle brotherhood, chrome wings and electricity.
EVERY guest MUST wear a BLACK LEATHER MOTORCYCLE JACKET with substantial lapels,
zippers, belts and silver studs, fitted to their unchanged original pose and build.
No pale denim jackets, ivory shirts as the main costume or ordinary polo shirts.
Keep faces unobscured; no helmets or sunglasses hiding identity. No invented tattoos.
Motorcycle and guitar props stay behind/beside guests, not miniature sticker clipart.

ART: Premium PIXELATED 3D: fully dimensional sculpted characters, believable facial
volumes, tactile distressed leather and machined chrome, rendered like a meticulously
art-directed late-1990s/modern retro 3D heavy-metal game cinematic. Controlled visible
square pixel clusters, crisp stepped silhouettes, selective ordered dithering and
limited charcoal/cobalt/oxblood/amber palette. Volumetric cinematic lighting, real
material depth, strong sculptural forms. Pixel styling must be deliberate and refined,
not a blurry low-resolution photo or a generic filter. Keep enough facial resolution
for unmistakable likeness; use coarser pixel clusters on scenery and costume shadows.
No flat 2D illustration, visual-novel painting, anime, comic outlines, cartoon big
eyes, glossy toy dolls or photoreal photography. Adult natural facial proportions.

LIGHTING: IT IS NIGHT. Dark charcoal sky, gritty shadowy garage, wet black asphalt,
cold cobalt rim light and warm fire bounce. Strong directional light reveals each
actual face clearly, while black leather retains seams, folds and specular highlights.
Smoke and sparks behind people, never masking faces. Powerful contrast and rock
energy, with real environmental depth. No white studio, pale empty background,
cream paper backdrop, pastel daylight or white outline-only garage.

BRANDING: Recreate the exact supplied compact winged NIGHT RIDERS shield naturally
above the guests. Preserve its two-line lettering, chrome wings, oxblood backing
and copper trim. Keep the complete wings and shield inside the image, not cropped.
Emblem height at most 18% of the image; the people, not the logo, are the main subject.
No substitute emblem or extra Harley-Davidson text/logos, dates or invented text.

OUTPUT: This is the full-color digital NIGHT RIDERS artwork. Make the actual scene
nocturnal and cinematic; the app separately adapts it for monochrome thermal paper.
Do not lighten the entire scene for printing. Distinct illuminated faces, jacket
highlights and chrome edges must remain readable against the night atmosphere.

COMPOSITION: One cohesive full-bleed portrait, not a poster grid. Large unobscured
recognizable faces and the compact emblem in the upper square-safe area. All real
guests remain visible. Integrated cinematic environment; no heavy outer frame. Keep faces and important
props out of the bottom 13%, where the app adds its verified venue/date/time footer. Never generate a footer,
QR, URL, date, timestamp, watermark or additional lettering.
"""


async def generate_night_riders(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images:
        raise ValueError("NIGHT RIDERS requires the approved winged emblem as Image 2")
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type="image/jpeg", aspect_ratio="1:1" if square else "9:16",
        image_size="1K", style="Gritty midnight heavy-metal pixelated 3D cinematic, dimensional recognizable real guest faces, every guest in black leather biker jackets, chrome V-twin motorcycles, cobalt lightning, fire, wet asphalt, charcoal night background",
        extra_reference_images=extra_reference_images,
    )
