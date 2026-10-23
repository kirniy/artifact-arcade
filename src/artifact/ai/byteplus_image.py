"""Bounded Seedream Flash image generation. No Gemini fallback or paid retries."""
import base64
import io
import logging
import os

import aiohttp
from PIL import Image, ImageOps

logger=logging.getLogger(__name__)
MODEL='dola-seedream-5-0-flash-260915'
ENDPOINT='https://ark.ap-southeast.bytepluses.com/api/v3/images/generations'


async def generate_image(prompt, reference_photo=None, photo_mime_type='image/jpeg',
                         aspect_ratio='1:1', image_size='1K', style=None,
                         extra_reference_images=None):
    key=os.getenv('BYTEPLUS_MODELARK_API_KEY','').strip()
    if not key:
        logger.error('BytePlus image key missing; refusing alternate paid providers')
        return None
    refs=[]
    if reference_photo:
        refs.append((reference_photo,photo_mime_type))
    refs.extend(extra_reference_images or [])
    if len(refs)>10:
        logger.error('BytePlus image request exceeds ten references')
        return None
    sizes={'1:1':'1024x1024','9:16':'864x1536','16:9':'1536x864','3:4':'960x1280'}
    if aspect_ratio not in sizes:
        logger.error('Unsupported BytePlus image aspect ratio')
        return None
    payload={'model':MODEL,'prompt':prompt,'size':sizes[aspect_ratio],
             'output_format':'png','response_format':'b64_json','watermark':False}
    if refs:
        payload['image']=[]
        for index,(raw,mime) in enumerate(refs):
            # Match the successful trials: bounded references avoid multi-MB PNG
            # uploads stalling the club uplink. No cropping or face alteration.
            with Image.open(io.BytesIO(raw)) as source:
                image=ImageOps.exif_transpose(source).convert('RGB')
                limit=1536 if index==0 else 1024
                image.thumbnail((limit,limit),Image.Resampling.LANCZOS)
                encoded=io.BytesIO();image.save(encoded,format='JPEG',quality=92)
            payload['image'].append('data:image/jpeg;base64,'+base64.b64encode(encoded.getvalue()).decode('ascii'))
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=75)) as session:
            async with session.post(ENDPOINT,headers={'Authorization':'Bearer '+key},json=payload) as response:
                if response.status!=200:
                    logger.error('BytePlus image HTTP %s; no automatic retry/fallback',response.status)
                    return None
                data=await response.json()
        items=data.get('data',[])
        if len(items)!=1 or not items[0].get('b64_json'):
            logger.error('BytePlus did not return one inline image; no regeneration')
            return None
        raw=base64.b64decode(items[0]['b64_json'],validate=True)
        if len(raw)>25*1024*1024:
            raise ValueError('Generated image too large')
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        return raw
    except Exception as exc:
        # Avoid logging request bodies, inline guest photos, credentials or URLs.
        logger.error('BytePlus image failed (%s); no retry/fallback',type(exc).__name__)
        return None
