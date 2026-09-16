"""Small CPU-only capture selector; never invents or restores facial features."""
from functools import lru_cache
import numpy as np

@lru_cache(maxsize=1)
def _detector():
    import cv2
    return cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')


def evaluate(frame, boxes=None):
    import cv2
    h,w=frame.shape[:2]
    scale=min(1.0,640/w)
    small=cv2.resize(frame,(max(1,int(w*scale)),max(1,int(h*scale))))
    gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
    if boxes is None:
        detector=_detector()
        boxes=detector.detectMultiScale(cv2.equalizeHist(gray),1.1,4,minSize=(28,28)) if not detector.empty() else []
    # Box coordinates are in the downsampled evaluation image.
    regions=[small[y:y+bh,x:x+bw] for x,y,bw,bh in boxes]
    if not regions:
        regions=[small[int(small.shape[0]*.15):int(small.shape[0]*.85),int(small.shape[1]*.15):int(small.shape[1]*.85)]]
    scores=[];clips=[]
    for region in regions:
        if not region.size:continue
        region=cv2.resize(region,(96,96))
        luminance=cv2.cvtColor(region,cv2.COLOR_RGB2GRAY)
        # Blur lightly before measuring to reduce preference for sensor noise.
        smooth=cv2.GaussianBlur(luminance,(3,3),0)
        sharp=float(cv2.Laplacian(smooth,cv2.CV_32F).var())
        clipped=float(np.mean(np.max(region,axis=2)>=250))
        dark=float(np.mean(np.max(region,axis=2)<20))
        scores.append(float(np.log1p(sharp))-4*clipped-2*dark)
        clips.append(clipped)
    return {'faces':len(boxes),'score':min(scores) if scores else -100.0,
            'clipped':max(clips) if clips else 1.0}


def choose(candidates):
    """Prefer preserving the most detected guests, then the weakest face's quality."""
    return max(range(len(candidates)),key=lambda i:(candidates[i]['faces'],candidates[i]['score']))
