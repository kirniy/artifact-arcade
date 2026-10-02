"""NIGHT RIDERS: recognizable illustrated guests and bright biker-rock artwork."""
import random

SCENES = (
    "A polished Harley-Davidson-style V-twin cruiser parked beside the unchanged guests; silver engine fins, warm copper pipes, a pale garage backdrop and small flame ribbons at the outer edges.",
    "A heavy-metal backstage with a chrome motorcycle at one side, electric guitars and amplifier outlines at the edges; pale lightning arcs behind the guests, sparse checkerboard accents.",
    "An airy biker clubhouse with two compact chrome cruisers behind the unchanged guest group, denim, leather patches, silver chains and a few copper sparks at the sides.",
    "A stylized pale highway pit stop, one large chrome V-twin motorcycle beside the unchanged guests, small guitar and checkered-flag props, crisp lightning and controlled flames around the frame edges.",
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
POSE LOCK: Keep each guest's original head angle, gaze, body posture, hand gestures,
relative scale, spacing and overlap. Do not seat standing guests on bikes or invent
raised arms, instruments in their hands or different expressions. Bikes and stage
props are beside or behind them, never over their faces or body silhouettes.

SCENE: {SCENES[index]}
Heavy metal, rock clubs, motorcycle brotherhood, chrome wings, red leather and
electricity. Dress guests in tasteful biker jackets/vests over fully covering tops,
pale denim, bandanas and small silver studs/chains, fitted to their original poses.
Use light stonewashed denim, ivory shirts, pale gray leather with small oxblood
patches; black leather is a restrained trim only, not a giant black area. Keep hair
and eyes visible. Realistic anatomy, hands, joints and plausible motorcycle parts.

ART: Premium fully illustrated 2D romance visual-novel character art, expressive
painted faces evocative of «Клуб Романтики», refined clean contours, subtle painterly
shading, tactile chrome and leather details. Every face, hand, costume, bike and
background must share the drawn style. No photoreal faces, photographs, Octane 3D,
plastic dolls or oversized anime eyes. Recognizable real guests come first.

BRANDING: Recreate the exact supplied compact winged NIGHT RIDERS shield naturally
above the guests. Preserve its two-line lettering, chrome wings, oxblood backing
and copper trim. Keep the complete wings and shield inside the image, not cropped.
No substitute emblem or extra Harley-Davidson text/logos, dates or invented text.

PRINT FIRST: The receipt is BLACK AND WHITE thermal paper. At least 75% of the
background must be pure white or very pale ivory, with sparse pale garage/highway
outlines. Make faces bright with clear contours and separated silhouettes. Chrome
is mostly white with precise dark edges. Flames are small pale gold/copper edge
accents; lightning is thin and crisp against a very light backdrop. No black night
sky, dense smoke, dark walls, heavy shadows, glowing haze over faces or solid dark
jackets. Rock energy must come from props, costumes and graphics, not dark lighting.

COMPOSITION: One cohesive full-bleed portrait, not a poster grid. Large unobscured
recognizable faces and the compact emblem in the upper square-safe area. All real
guests remain visible. Sparse props at edges; no heavy outer frame. Bottom 13% is
clean white space for the app's venue/date/time footer. Never generate a footer,
QR, URL, date, timestamp, watermark or additional lettering.
"""


async def generate_night_riders(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images:
        raise ValueError("NIGHT RIDERS requires the approved winged emblem as Image 2")
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type="image/jpeg", aspect_ratio="1:1" if square else "9:16",
        image_size="1K", style="Bright fully illustrated 2D biker-rock visual novel, accurately recognizable real guest faces, chrome V-twin motorcycles, light denim and leather, small flames and lightning, white thermal-print background",
        extra_reference_images=extra_reference_images,
    )
