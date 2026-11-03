"""Deterministic 16-direction gaze from the original front pixels only.

Requires Pillow. No external image/texture is used. Build: --build; check: --validate.
An inverse smooth displacement moves eye texture while the aperture boundary stays
fixed. Original RGBA bytes are retained everywhere outside the two eye interiors.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'apps/web/src/assets/mascot/expressions-v2'
RING = ('e','ene','ne','nne','n','nnw','nw','wnw','w','wsw','sw','ssw','s','sse','se','ese')
EYES = ((158.5,228.5,30.5,32.5),(300.0,239.5,28.0,30.5))
AMPLITUDE = (9.0,8.0)
BAND = (83,160,363,320)
SIZE = (420,540)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eye_pixels():
    for cx,cy,rx,ry in EYES:
        for y in range(math.floor(cy-ry), math.ceil(cy+ry)+1):
            for x in range(math.floor(cx-rx),math.ceil(cx+rx)+1):
                if ((x-cx)/rx)**2+((y-cy)/ry)**2 < 1:
                    yield x,y,cx,cy,rx,ry


def displacement(index):
    angle=math.radians(index*22.5)
    return AMPLITUDE[0]*math.cos(angle), -AMPLITUDE[1]*math.sin(angle)


def frame(base,index):
    source=base.load()
    result=base.copy(); target=result.load()
    dx,dy=displacement(index)
    for x,y,cx,cy,rx,ry in eye_pixels():
        sx,sy=float(x),float(y)
        # Contraction mapping: max gradient*displacement < 1, no foldovers.
        for _ in range(24):
            r2=((sx-cx)/rx)**2+((sy-cy)/ry)**2
            weight=max(0.,1.-r2)**2
            sx,sy=x-dx*weight,y-dy*weight
        x0,y0=math.floor(sx),math.floor(sy)
        ax,ay=sx-x0,sy-y0
        weights=((1-ax)*(1-ay),ax*(1-ay),(1-ax)*ay,ax*ay)
        samples=(source[x0,y0],source[x0+1,y0],source[x0,y0+1],source[x0+1,y0+1])
        rgb=tuple(round(sum(s[k]*w for s,w in zip(samples,weights))) for k in range(3))
        target[x,y]=(*rgb,source[x,y][3])
    return result


def base_image(out):
    with Image.open(out/'front.png') as im:
        if im.mode!='RGBA' or im.size!=SIZE or im.format!='PNG':
            raise ValueError('front.png must be PNG RGBA 420x540')
        return im.copy()


def inspect(out=OUT):
    base=base_image(out)
    expected_names={f'gaze-{d}.png' for d in RING}
    if {p.name for p in out.glob('gaze-*.png')}!=expected_names:
        raise ValueError('Gaze filenames must contain exactly the 16 compass directions')
    allowed=Image.new('1',SIZE,0)
    for x,y,*_ in eye_pixels(): allowed.putpixel((x,y),1)
    entries=[]
    for i,direction in enumerate(RING):
        path=out/f'gaze-{direction}.png'
        with Image.open(path) as im:
            if im.mode!='RGBA' or im.size!=SIZE or im.format!='PNG':
                raise ValueError(f'{path.name}: expected PNG RGBA 420x540')
            current=im.copy()
        if path.stat().st_size>5_000_000: raise ValueError('File exceeds 5 MB')
        if current.getchannel('A').tobytes()!=base.getchannel('A').tobytes():
            raise ValueError(f'{direction}: alpha changed')
        diff=ImageChops.difference(base,current)
        mask=Image.new('L',SIZE,0); changed=mask.load()
        outside=0; inside=0
        for y in range(SIZE[1]):
            for x in range(SIZE[0]):
                if diff.getpixel((x,y))!=(0,0,0,0):
                    changed[x,y]=255; inside+=1
                    if not allowed.getpixel((x,y)): outside+=1
        if outside or not inside: raise ValueError(f'{direction}: changed pixels outside eyes or empty frame')
        if current.tobytes()!=frame(base,i).tobytes():
            raise ValueError(f'{direction}: pixels do not match the declared gaze direction')
        dx,dy=displacement(i)
        entries.append({'name':f'gaze-{direction}','full':path.name,'angle_degrees':i*22.5,
            'eye_displacement_xy':[round(dx,6),round(dy,6)],'changed_bbox_xyxy_exclusive':list(mask.getbbox()),
            'changed_pixels':inside,'outside_eye_changed_pixels':0,'outside_face_changed_pixels':0,
            'alpha_matches':True,'sha256':sha(path)})
    offsets=[displacement(i) for i in range(16)]
    step=max(math.dist(offsets[i],offsets[(i+1)%16]) for i in range(16))
    return {'schema_version':1,'base':'front.png','base_sha256':sha(out/'front.png'),
        'canvas_size':list(SIZE),'face_band_canvas_xyxy_exclusive':list(BAND),
        'eye_apertures_cx_cy_rx_ry':[list(e) for e in EYES],
        'method':'inverse smooth eye-texture displacement, w=(1-r^2)^2, fixed eye boundary',
        'amplitude_xy':list(AMPLITUDE),'direction_order':list(RING),
        'expected_frame_count':16,'actual_frame_count':len(entries),'complete':True,
        'max_adjacent_displacement_px':round(step,6),'frames':entries}


def validate(out=OUT):
    expected=inspect(out)
    saved=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    if saved.get('gaze')!=expected: raise ValueError('Gaze manifest missing/stale; validation never repairs it')
    report={'set':'front-gaze','frames':16,'canvas':[420,540],'outside_eye_changed_pixels':0,
            'outside_face_changed_pixels':0,'alpha_matches':True,'direction_check':'passed',
            'max_adjacent_displacement_px':expected['max_adjacent_displacement_px']}
    return report


def build(out=OUT):
    base=base_image(out)
    frames=[]
    for i,d in enumerate(RING):
        im=frame(base,i); im.save(out/f'gaze-{d}.png',optimize=True); frames.append(im)
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    manifest['gaze']=inspect(out)
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sheet=Image.new('RGB',(840,1200),'#F5F3ED');draw=ImageDraw.Draw(sheet)
    eye_sheet=Image.new('RGB',(960,480),'#F5F3ED');ed=ImageDraw.Draw(eye_sheet)
    for i,(im,d) in enumerate(zip(frames,RING)):
        thumb=im.resize((210,270),Image.Resampling.LANCZOS)
        x,y=(i%4)*210,(i//4)*300; sheet.paste(thumb,(x,y),thumb)
        draw.text((x+12,y+278),f'gaze-{d}',fill='#22301F')
        crop=im.crop((116,187,342,282)).convert('RGB')
        ex,ey=(i%4)*240,(i//4)*120;eye_sheet.paste(crop,(ex,ey));ed.text((ex+12,ey+101),f'gaze-{d}',fill='#22301F')
    sheet.save(out/'gaze-contact-sheet.jpg',quality=92)
    eye_sheet.save(out/'gaze-eye-contact-sheet.jpg',quality=95)
    return validate(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--build',action='store_true');group.add_argument('--validate',action='store_true')
    args=parser.parse_args()
    print(json.dumps(build() if args.build else validate(),ensure_ascii=False))
