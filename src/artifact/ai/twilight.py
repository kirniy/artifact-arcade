"""TWILIGHT: identity-locked romantic 2D portraits in a luminous misty forest."""
import random

SCENES = (
    'A luminous misty conifer forest clearing with tall fir silhouettes, silver-blue fog and a soft moon behind distant branches.',
    'A romantic forest path with layered evergreen trees, pale sage foliage and pearl mist illuminated by a soft twilight sky.',
    'A quiet woodland lake with reflected fir trees, luminous blue-green mist and a delicate silver crescent above the distant canopy.',
)


def build_prompt(variation_index=None):
    index = random.randrange(len(SCENES)) if variation_index is None else variation_index % len(SCENES)
    return f'''Create one premium TWILIGHT / VNVNC romantic photobooth portrait.
REFERENCE ROLES: Image 1 contains ALL actual guests; image 2 is the exact approved
oval TWILIGHT emblem; image 3 is the forest campaign wallpaper, BACKGROUND ONLY.
Images 4+ are identity closeups of the SAME guests, not additional people.

IDENTITY AND POSE LOCK: Preserve the exact guest count and every individual's
facial geometry, eye shape and spacing, nose, lips, jaw, ethnicity, skin tone, gender,
age, haircut, hairline, facial hair, glasses, natural asymmetry and body build.
Preserve their actual expressions, eye opening, mouth shape, head angle, gaze,
posture, hand gestures, relative size, spacing and overlap. No invented smiles,
angry grimaces, longer hair, beards, muscles or thinner bodies. No added crowd,
no duplicated face-crop guests. Do not replace anybody with Twilight actors,
Edward, Bella, Jacob, stock models or generic attractive characters. Likeness
outranks glamour. Each adult keeps natural adult facial proportions, not big anime eyes.

ART: Beautiful fully DRAWN 2D romantic visual-novel character art in the spirit
of Romance Club / «Клуб Романтики»: refined painted faces, delicate clean contours,
soft controlled shading, believable anatomy and elegant fabric folds. Faces,
hands, clothes and scenery all share this illustrated style. NOT pixel art,
NOT 3D/Octane, NOT photoreal photography, NOT chibi or plastic dolls. Translate
actual facial features faithfully into drawing instead of applying a beauty template.
Dress the guests in elegant contemporary woodland-romance outfits: pearl shirts,
soft sage/blue-gray jackets, flowing light fabrics and small silver details,
adapted to their original poses. No helmets, face paint or hoods hiding hair/faces.

SCENE: {SCENES[index]}
Use image 3's layered misty conifer forest, but SUBSTANTIALLY LIGHTER. Pearl gray,
silver blue, pale sage and luminous fog dominate; retain real forest depth and
recognizable trees. Atmospheric twilight, not a blank white studio. Most backdrop
and fabric should be light/mid-light with sparse dark tree trunks and crisp facial
contours, suitable for black-and-white thermal paper. Bright clear faces, no fog
across faces, deep black forest, heavy vignette, dirty grain or dense dark clothing.

BRANDING: Integrate the supplied exact oval TWILIGHT emblem above the guests,
complete inside the upper square-safe area, no taller than 15% of the portrait.
Keep the original lowercase lettering, spiral g, oval shape and forest-green/ivory
palette. Do not reinterpret the emblem. Ignore all repeated sideways lettering
in wallpaper image 3: do not repeat it over people or along the image edges.
No actor names, movie credits, extra brands, watermark, fake text or captions.

COMPOSITION: One cohesive full-bleed vertical illustrated scene, large recognizable
unobscured guests in the upper square-safe area, no poster grid or separate header.
No surplus empty sky. Preserve group arrangement and gestures. Keep faces and
important details above the bottom 13%, reserved for the app's verified footer.
Never generate URL, QR, venue, date, timestamp or footer text. Full COLOR digital
art; printing is performed separately by the app.
'''


async def generate_twilight(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images or len(extra_reference_images) < 2:
        raise ValueError('TWILIGHT requires the approved emblem and forest references')
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type='image/jpeg', aspect_ratio='1:1' if square else '9:16',
        image_size='1K', style='Romantic fully illustrated 2D visual novel, faithfully recognizable real guests, luminous misty evergreen forest, silver blue and pale sage, elegant contemporary outfits; no pixels or 3D',
        extra_reference_images=extra_reference_images,
    )
