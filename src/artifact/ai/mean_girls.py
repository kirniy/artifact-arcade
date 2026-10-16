"""MEAN GIRLS: identity-first tactile editorial CG, approved event emblem."""


def build_prompt(variation_index=None):
    return '''Create one MEAN GIRLS / VNVNC photobooth portrait.
Image 1 is the actual guests. Image 2 is the EXACT supplied event emblem.
Further images are identity crops of the SAME guests, never additional people.
IDENTITY FIRST: preserve ALL people, exact facial features, ethnicity, age,
gender, hair, expression, body build, clothing text letter-for-letter, posture,
spacing and hand gestures. Never replace guests with actors or stock models.
Adults stay adults with natural proportions. No enlarged eyes, thin faces,
beauty-template faces, invented smile, altered nose or changed skin tone.
STYLE: tactile editorial CG with natural adult faces and subtle designed volume,
fine skin detail, satin weave, velour and delicate metal accessories. Y2K couture,
cherry satin, restrained pink quilted diary details, heart padlock and rhinestones
at the edges. Keep guests' actual clothing and poses; do not force dresses or
feminize men. No caricature, Bratz/Pixar dolls, anime or exaggerated anatomy.
LIGHT: ivory key on readable faces, blush bounce, separated pink/cherry/ivory
materials. A cinematic Y2K editorial set with dimensional props, not a flat
poster. Digital colour is electric magenta #F505F6, black, white and chrome; restrained ivory for print. Leave most printed surfaces light/mid-light
and keep ink-heavy black areas small. No fog or sparkles over faces.
COMPOSITION: one cohesive portrait, large unobscured guests, no repeated frames,
no extra crowd. The supplied ornamental MEAN GIRLS emblem is large, intact,
clearly readable, above guests inside the upper square-safe area. Keep its
lettering, heart lock, diamonds and proportions exactly; do not typeset a
replacement. Sparse pearl/rose photographic border. Avoid huge empty fields.
Reserve the bottom 13% for the application's verified footer. Do not generate
QR codes, captions, quest invitations, dates, timestamps, venue or website text.
'''


async def generate_mean_girls(client, reference_photo, extra_reference_images, *, square=False, variation_index=None):
    if not extra_reference_images:
        raise ValueError('MEAN GIRLS requires the approved emblem')
    return await client.generate_image(
        prompt=build_prompt(variation_index), reference_photo=reference_photo,
        photo_mime_type='image/jpeg', aspect_ratio='1:1' if square else '9:16',
        image_size='1K', style='Identity-first tactile editorial CG, natural adult faces, Y2K satin and pearl rose, exact MEAN GIRLS event emblem',
        extra_reference_images=extra_reference_images,
    )
