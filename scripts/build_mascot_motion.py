"""Normalize authored mascot motion frames, compress WebP and write contact sheets.

Requires Pillow, numpy and opencv-python. Raw PNGs remain outside runtime assets.
The ground registration anchor stays fixed; hop has explicit vertical clearances.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"apps/web/src/assets/mascot/motion"
CANVAS = (360,480)
ANCHOR = (180,447)
SETS = {"walk":(8,10), "hop":(6,10), "look-around":(6,6), "tail-wag":(4,6)}
LIFTS = [0,0,26,55,0,10]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(image):
    a = np.asarray(image.convert("RGBA")).copy()
    binary = (a[:,:,3]>32).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if count < 2:
        raise ValueError("Empty mascot")
    main = 1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    keep = cv2.dilate((labels==main).astype(np.uint8), np.ones((5,5),np.uint8)) > 0
    a[:,:,3][~keep | (a[:,:,3]<16)] = 0
    a[a[:,:,3]==0] = 0
    return Image.fromarray(a)


def head_center(image):
    a = np.asarray(image)[:,:,3]
    ys,xs = np.nonzero(a>32)
    cutoff = ys.min()+int((ys.max()-ys.min())*.45)
    yy,xx = np.nonzero((a>128)&(np.indices(a.shape)[0]<cutoff))
    return float(xx.mean())


def head_span(image):
    a=np.asarray(image)[:,:,3]>128
    ys,xs=np.nonzero(a)
    cutoff=ys.min()+int((ys.max()-ys.min())*.60)
    widths=[]
    for row in a[ys.min():cutoff]:
        occupied=np.flatnonzero(row)
        if len(occupied):
            widths.append(int(occupied[-1]-occupied[0]+1))
    return max(widths)


def prepare(inputs, name):
    count,_ = SETS[name]
    raw=[]
    for i in range(count):
        with Image.open(inputs/name/f"{i:02}.png") as opened:
            if opened.mode!="RGBA":
                raise ValueError("Expected transparent RGBA input")
            im=clean(opened)
        if raw and im.size!=raw[0].size:
            fitted=ImageOps.contain(im.convert("RGBa"),raw[0].size,Image.Resampling.LANCZOS).convert("RGBA")
            im=Image.new("RGBA",raw[0].size)
            im.paste(fitted,((im.width-fitted.width)//2,(im.height-fitted.height)//2))
        raw.append(im)
    bboxes=[im.getchannel("A").getbbox() for im in raw]
    max_height=max(b[3]-b[1] for b in bboxes)
    max_width=max(b[2]-b[0] for b in bboxes)
    scale=min((360-40)/max_width, (395-(55 if name=="hop" else 0))/max_height)
    # Reserve margins relative to the registered body axis, not an off-centre
    # tail's bounding-box centre. The whole silhouette must fit without clipping.
    for im,b in zip(raw,bboxes):
        cx=head_center(im)
        scale=min(scale,164/(cx-b[0]),164/(b[2]-cx))
    scales=[scale]*count
    if name=="hop":
        # Keep head size stable through squash/takeoff/tuck poses rather than
        # making the entire character shrink when the legs extend.
        spans=[head_span(im) for im in raw]
        target=280.
        for i,(im,b,span) in enumerate(zip(raw,bboxes,spans)):
            cx=head_center(im)
            target=min(target,(420-LIFTS[i])*span/(b[3]-b[1]),
                       164*span/(cx-b[0]),164*span/(b[2]-cx))
        scales=[target/span for span in spans]
    frames=[]
    registrations=[]
    for i,im in enumerate(raw):
        scale=scales[i]
        scaled=im.convert("RGBa").resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS).convert("RGBA")
        bbox=scaled.getchannel("A").getbbox()
        lift=LIFTS[i] if name=="hop" else 0
        dx=round(ANCHOR[0]-head_center(scaled))
        dy=ANCHOR[1]+1-lift-bbox[3]
        full=Image.new("RGBA",CANVAS)
        full.paste(scaled,(dx,dy))
        frames.append(full)
        registrations.append({"scale":scale,"translation":[dx,dy],"source_size":list(im.size)})
    # Head turns and tail wags must never move the feet/body. Preserve the
    # approved neutral body and only copy the motion region from authored frames.
    if name=="look-around":
        base=frames[0]
        # Smooth neck seam; all lower-body/foot pixels remain the same.
        mask=Image.new("L",CANVAS)
        ImageDraw.Draw(mask).rectangle((0,0,359,292),fill=255)
        mask=mask.filter(ImageFilter.GaussianBlur(3))
        frames=[base]+[Image.composite(f,base,mask) for f in frames[1:]]
    elif name=="tail-wag":
        base=frames[0]
        mask=Image.new("L",CANVAS)
        ImageDraw.Draw(mask).polygon([(274,258),(359,258),(359,416),(226,416),
                                      (244,391),(260,353),(268,299)],fill=255)
        # This region stays behind the torso and never includes the feet.
        mask=mask.filter(ImageFilter.GaussianBlur(1))
        frames=[base]+[Image.composite(f,base,mask) for f in frames[1:]]
    return frames,registrations


def encode(image,path):
    # Alpha is lossless in WebP. A quality search keeps each texture crisp
    # while respecting the stricter decimal 60 KB cap.
    for quality in (82,78,74,70,66,62,58,54):
        image.save(path,format="WEBP",quality=quality,method=6,exact=True)
        if path.stat().st_size<=42000:
            return quality
    if path.stat().st_size>60000:
        raise ValueError(f"Frame exceeds60KB: {path}")
    return quality


def build(inputs,out=OUT,preview_dir=None):
    out.mkdir(parents=True,exist_ok=True)
    for name,(count,fps) in SETS.items():
        folder=out/name
        folder.mkdir(exist_ok=True)
        frames,registrations=prepare(inputs,name)
        entries=[]
        decoded=[]
        for i,frame in enumerate(frames):
            path=folder/f"{i:02}.webp"
            quality=encode(frame,path)
            with Image.open(path) as im:
                loaded=im.convert("RGBA")
            decoded.append(loaded)
            entries.append({"file":path.name,"anchor":list(ANCHOR),
                            "ground_clearance_px":LIFTS[i] if name=="hop" else 0,
                            "alpha_bbox":list(loaded.getchannel("A").getbbox()),
                            "sha256":digest(path),"bytes":path.stat().st_size,
                            "webp_quality":quality,"registration":registrations[i]})
        sheet=Image.new("RGB",(180*count,260),"#f5f3ed")
        draw=ImageDraw.Draw(sheet)
        for i,im in enumerate(decoded):
            thumb=im.resize((180,240),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(i*180,0),thumb)
            draw.line((i*180+10,224,i*180+170,224),fill="#b6bda9")
            draw.text((i*180+8,244),f"{name} / {i:02}",fill="#22301f")
        sheet.save(folder/"contact-sheet.jpg",quality=72,optimize=True)
        manifest={"schema_version":1,"name":name,"canvas_size":list(CANVAS),
                  "frame_count":count,"fps":fps,"loop":True,"anchor":list(ANCHOR),
                  "anchor_semantics":"fixed ground registration; feet lift only during hop",
                  "frames":entries}
        (folder/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8",newline="\n")
        if preview_dir:
            preview_dir.mkdir(parents=True,exist_ok=True)
            decoded[0].save(preview_dir/f"{name}.webp",save_all=True,append_images=decoded[1:],
                            duration=round(1000/fps),loop=0,quality=74,method=6)
    return {"motion_bytes":sum(p.stat().st_size for p in out.rglob("*") if p.is_file())}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--preview-dir",type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.inputs,preview_dir=args.preview_dir)))
