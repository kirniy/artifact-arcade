"""Tropical Thai photo direction, isolated from the legacy 2D theme prompts."""
import random

SCENES = (
    "A sunlit Krabi limestone lagoon: luminous mint-turquoise water, ivory limestone islands, "
    "a small distant Thai longtail boat, spacious turquoise palms and orchids at the edges.",
    "An airy Thai jungle sanctuary: sunlit banana leaves and layered monstera, pale jade "
    "mist, a gentle waterfall and cream limestone, with a wide bright opening behind the guests.",
    "A dreamy Thai island garden: pearly sand, translucent aqua shallows, sculptural teal palms, "
    "pink orchids, one small mango and coconut arrangement low in the foreground.",
    "A luminous tropical orchid lagoon: oversized glossy orchid petals at the far edges, "
    "pale peach sky, emerald karst islands, soft cyan water caustics and sunlit palm leaves.",
)


def build_prompt(variation_index=None):
    index = random.randrange(len(SCENES)) if variation_index is None else variation_index % len(SCENES)
    return f"""Create one extraordinary TROPICAL THAI event portrait, a polished Octane-style 3D render.
IMAGE ROLES: Image 1 is the only source of people and their clothing. Image 2 is the exact
canonical TROPICAL THAI party emblem. Images 3+ are identity crops of those SAME people,
never extra guests. Keep exactly the original guest count, individual facial geometry,
skin tones, age, hair, expressions, glasses, accessories and distinctive asymmetry,
translated into sculpted animated-character features rather than photographic faces.
CLOTHING LOCK: Preserve every person's original clothes exactly: garment type, cut,
coverage, colors, patterns, visible logos and layering. Do not replace outfits with
Thai costumes, swimwear, resort clothing or invented accessories. Do not beautify,
slim, sexualize, average faces, swap identities or add people. Keep each guest equally recognizable.

ART DIRECTION: Dimensional, luxurious Octane 3D, physically based materials, exquisite
ray-traced global illumination, soft contact shadows, glossy sculptural tropical foliage,
translucent petals, realistic fabric texture, subtle water caustics and cinematic depth.
CHARACTER RENDERING IS MANDATORY: Turn EVERY guest, including the entire face, hair,
body and clothing, into a premium stylized 3D cartoon character from an animated feature.
Use modeled facial planes, softly rounded sculpted cheeks and noses, expressive eyes,
sculpted hair clumps, stylized skin with soft subsurface scattering and dimensional
fabric folds. Render people and scenery together with the same Octane-style ray-traced
lighting and physically based shading. Preserve each real person's recognizable facial
proportions, expression, age and distinguishing features within that cartoon treatment.
Do not paste real photographic faces onto CGI bodies. No live-action skin, photo cutouts,
hyperreal humans, flat 2D illustration, baby-face makeover, generic identical characters,
waxy mannequins or plastic toy-doll faces. The people themselves MUST visibly be 3D
cartoon characters; making only the tropical background 3D is not sufficient.
REPLACE the original room/background completely with a Thai tropical paradise:
{SCENES[index]}
Use the event video's turquoise palms, coral/cream accents, orchid pink and mango yellow
as restrained art direction. At least 70% of the background is light or mid-tone.
Bright high-key pearly daylight, pale aqua/cream negative space and readable shadows;
no black video background, dark jungle canopy, muddy greens, night scene or neon club.

COMPOSITION: One cohesive waist-up portrait, all guests clearly visible, faces large and
unobscured in the upper-middle frame. Hands anatomically correct. Put the complete exact
winged TROPICAL THAI emblem naturally above the guests, preserving the supplied script,
navy plaque, cream/coral trim and red-white-blue wings. Use the emblem itself, not its
square reference-image backdrop. No additional brands or signs. Keep emblem and faces
inside the central square-safe area in the upper portion of the portrait so the booth's
square display crop retains them. Use leaves and flowers around edges, never across faces.
Continue the tropical world full bleed to the bottom. Keep faces outside the bottom 13%,
where the app adds verified venue/day/time information. Do not generate any footer,
date, time, URL, watermark, placeholder bar or text beyond the exact emblem wording.
"""


async def generate_tropical_thai(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    # Fail closed: never substitute a hallucinated emblem if a caller bypasses booth preflight.
    if not extra_reference_images:
        raise ValueError("Tropical Thai requires the canonical emblem as Image 2")
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type="image/jpeg", aspect_ratio="1:1" if square else "9:16",
        image_size="1K", style="Premium Octane-rendered stylized 3D cartoon characters of every real guest, sculpted expressive faces and hair, full CGI animated-feature portrait, no photographic faces, bright high-key tropical daylight, original clothing and recognizable identity",
        extra_reference_images=extra_reference_images,
    )
