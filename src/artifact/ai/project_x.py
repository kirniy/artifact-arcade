"""Project X: identity-preserving college party portraits for light thermal prints."""
import random

SCENES = (
    "A victorious cup-pong celebration: guests cheering behind a pale table, cups tipping into the air, a small squirrel mascot celebrating at the edge.",
    "A campus pep rally: guests jumping and waving pennants, a friendly goat mascot with a megaphone, sparse oversized confetti frozen in midair.",
    "A ridiculous dorm-room victory parade: guests holding a silver trophy made of stacked cups, flying popcorn and a foam finger, faint lockers outlined behind them.",
    "A fraternity lawn-party team photo gone hilariously wrong: guests laughing and high-fiving, a squirrel stealing a pennant, a small silver keg at the edge, loose ribbons overhead.",
)


def build_prompt(variation_index=None):
    index = random.randrange(len(SCENES)) if variation_index is None else variation_index % len(SCENES)
    return f"""Create a PROJECT X / VNVNC UNIVERSITY college-party souvenir portrait.
IMAGE ROLES: Image 1 supplies ALL real guests. Image 2 is the exact canonical oval
PROJECT X / VNVNC UNIVERSITY emblem. Images 3+ are identity crops of the SAME guests.
Preserve exactly the guest count and each recognizable face, age, skin tone, hair,
glasses and distinctive features. No strangers or human crowd. Animal mascots are small
supporting props, never substitutes for guests. Do not beautify or homogenize faces.
COSTUMES: Replace clothes with playful collegiate varsity jackets, athletic jerseys,
frat-bro polos and adult cheerleader uniforms with comfortable full coverage. Respect
presentation; do not change bodies, sexualize guests or make adult guests look like children.
Keep eyes and faces unobscured; realistic hands, no duplicated limbs. Playful expressive poses.
SCENE: {SCENES[index]}
ART: Premium stylized illustrated 3D with tactile embroidered patches, chenille varsity
letters, satin ribbons, soft leather trim and crisp paper-cut edges. Blue Mountain State
college-comedy energy, original VNVNC branding, no television actors or borrowed logos.
PRINT-FIRST: This image is printed on BLACK AND WHITE thermal paper. Use a pure WHITE
background covering at least 75% of the background; very pale sparse campus outlines.
High-key light faces, airy pale clothing with small royal-blue/red accents only. Crisp
contours and separated silhouettes survive monochrome dithering. No black backdrop,
night lighting, solid dark jackets, heavy shadows, gray fog, dense hatching or dark frame.
Keep tactile detail restrained rather than coating the page in texture. Fun and energetic,
not a passport portrait. One cohesive scene, not a collage or multiple photo panels.
COMPOSITION: Large recognizable waist-up guests for the cup-pong portrait; lively full-body
compositions are welcome for the pep rally, keeping faces recognizable and unobscured.
Emblem compact above heads, faithfully
preserve its lettering and oval shape, no giant dark logo plate. Keep emblem and ALL faces
within the upper square-safe region of the vertical image. Sparse props at edges only.
Bottom 13% is white, empty of faces/props for the app's verified footer. No generated
footer, dates, time, QR, URL, watermarks or additional lettering.
"""


async def generate_project_x(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images:
        raise ValueError("Project X requires the canonical emblem as Image 2")
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type="image/jpeg", aspect_ratio="1:1" if square else "9:16",
        image_size="1K", style="Airy white-background collegiate party illustration, recognizable guests, tactile varsity costumes, crisp grayscale-friendly contours",
        extra_reference_images=extra_reference_images,
    )
