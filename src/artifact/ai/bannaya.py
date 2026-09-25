"""БАННАЯ: bright, print-friendly portraits using the approved wooden emblem."""

import random


SCENES = (
    "Pale cedar steam-room wall and two clearly visible tiers of wooden sauna benches behind the unchanged guest group; birch veniki hang at the side, with folded linen and a copper samovar at the frame edges.",
    "Two tiers of light wooden sauna benches behind the unchanged guest group, with a glimpse of a furako tub to one side; birch leaves and soft steam stay away from faces.",
    "Airy Russian bathhouse interior with unmistakable upper and lower cedar sauna benches behind the unchanged guest group, a polished brass ladle and felt hats as edge props, and pearly steam behind them.",
    "Open cedar steam-room doorway with two visible tiers of wooden sauna benches immediately behind the unchanged guest group; a distant pale-blue lake is glimpsed only through a small side window, with white towels at the edges.",
)


def build_prompt(variation_index=None):
    index = random.randrange(len(SCENES)) if variation_index is None else variation_index % len(SCENES)
    return f"""Create one premium БАННАЯ / VNVNC photobooth portrait.
REFERENCE ROLES: Image 1 is the FIXED UNDERDRAWING for the ONLY guests: trace the
same individuals in the same positions. Image 2 is the exact approved wooden БАННАЯ
sign. Images 3+ are closeups of those SAME guests for facial identity, not additional
people. IDENTITY OUTRANKS STYLE: accurately retain each person's actual facial
geometry and ethnic features: eye shape and spacing, eyelids, nose, lips, jaw,
cheekbones, skin tone and texture, hairline, hairstyle, facial hair, glasses,
apparent age, expression and natural asymmetry. No ethnicity shift or generic
beauty template. In particular, do not impose stereotyped anime/East Asian
facial features on guests who do not have them; if a guest actually has those
features, preserve them faithfully. Never average faces, beautify, swap identities,
or cover eyes. Keep exactly the original guest count and group arrangement.
POSE LOCK: Preserve each source person's head angle, gaze, body posture, arm and hand
positions, gestures, relative scale, distance and overlap. Do not invent jumping,
raised arms, props in hands or different expressions to fit a scene variation.

SCENE (BACKGROUND AND EDGE PROPS ONLY; NEVER REPOSE THE GUESTS): {SCENES[index]}
Build a playful contemporary Russian bathhouse party, inspired by the actual event's
cedar photo zone, felt VNVNC sauna hat, birch venik, stove and furako.
Keep the upper and lower wooden sauna benches visibly running across the BACKGROUND
behind the guests in every variation; their horizontal tiers should read instantly
as real банные полки, never as a plain wall, outdoor scene, or furniture in front
of the people. Add a small bath stove and bucket at a side edge where space allows.
Do not let benches, steam or props cover heads, faces or the approved wooden sign.
Dress EVERY guest
in a modest, fully closed, belted bathrobe (халат) with sleeves and tasteful red woven
trim, fitted to the ORIGINAL body pose and silhouette. Robes can be cream or pale
linen; retain distinctive hair, jewelry and glasses. Optional felt sauna hats may
sit above the hairline but never hide hairline or faces. No exposed
torsos, towel-only outfits or sexualized posing.

VISUAL NOVEL ART DIRECTION: A polished 2D illustrated romance visual novel, evocative
of the expressive character portraits and painted scenes in «Клуб Романтики».
Hand-painted digital character art, elegant drawn facial planes, precisely observed
REAL eye shapes (never enlarged anime eyes), refined clean linework, softly layered
cel/painterly shading, detailed robe folds,
subtle storybook lighting and atmospheric painted background. Draw EVERY PERSON fully
in the same 2D style, including their faces, hair, hands and robes. Preserve each
guest's recognizable features within the illustration. Not a photographic face on a
painted body. Absolutely no photorealism, live-action skin, 3D render, Octane,
Pixar-like cartoon, plastic doll or generic beauty-model face. No historical folk
costume, bear mascot, drunken caricature or crowded props.

BRANDING: Recreate the COMPLETE supplied wooden БАННАЯ plaque naturally above the
guests, with its carved Cyrillic letters, dark timber silhouette and red embroidery.
Use the sign itself rather than its white reference-image backdrop. No alternative
gold SLAVIC CORE / БАННЫЙ ШИК title and no fabricated VNVNC wordmarks. No other text.

PRINT: The color original must also work on a BLACK-AND-WHITE thermal label.
At least 70% of the background should be genuinely light: pale honey wood, ivory linen
and white steam. Make illustrated faces and robes bright, contours crisp, shapes separated.
Never create a dark brown wall, black void, thick gray haze, heavy woodgrain across
faces, blown highlights or dense shadow masses. Keep the sign dark enough to read,
but compact; it must not dominate the print. Restrained, lively, funny and expensive.

COMPOSITION: One full-bleed vertical image, not a collage or grid. Large clear faces in
the upper-middle. Put the plaque and all faces within the upper square-safe area for
the booth display crop. Keep props at the edges and steam behind the faces. Reserve
the bottom 13% as light clean space for the app's verified venue/date/time footer.
Do not generate a footer, QR, date, watermark, poster border or extra lettering.
"""


async def generate_bannaya(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images:
        raise ValueError("БАННАЯ requires the approved wooden emblem as Image 2")
    return await client.generate_image(
        prompt=build_prompt(variation_index),
        reference_photo=reference_photo,
        photo_mime_type="image/jpeg",
        aspect_ratio="1:1" if square else "9:16",
        image_size="1K",
        style="Premium 2D illustrated romance visual novel character art, fully drawn recognizable guest faces, modest belted bathrobes, high-key pale cedar and ivory steam, crisp grayscale-friendly contours, approved carved wooden БАННАЯ plaque; never photoreal or 3D",
        extra_reference_images=extra_reference_images,
    )
