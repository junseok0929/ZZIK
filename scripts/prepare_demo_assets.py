"""Extract local demo regions from user-supplied design references, preserving source files.
These illustrative composites are fixture samples, never AI accuracy evidence.
"""
from pathlib import Path
import hashlib,json
from PIL import Image
root=Path(__file__).resolve().parents[1]
assets=root/'frontend/public/demo'; assets.mkdir(parents=True,exist_ok=True)
fixtures=root/'backend/fixtures'; fixtures.mkdir(parents=True,exist_ok=True)
a=Image.open(root/'KakaoTalk_Photo_2026-09-16-21-31-21 003.png').convert('RGB')
b=Image.open(root/'KakaoTalk_Photo_2026-09-16-21-31-20 001.png').convert('RGB')
photos=[(a,(1272,220,1502,406),['지수'],['바다']),
(a,(491,411,728,553),['지수','민지'],['카페']),
(b,(1049,146,1494,556),['지수','민지','서연','유진'],['바다']),
(a,(991,412,1226,554),['지수'],['여행']),
(a,(242,628,478,771),['지수','민지','서연','유진'],['음식','카페']),
(a,(491,628,728,786),['지수'],['바다']),
(a,(740,628,977,786),['지수'],['카페']),
(a,(991,628,1226,774),['지수'],['꽃','바다']),
(b,(773,716,987,884),['민지'],['야경']),
(b,(548,541,764,707),['지수'],['꽃','바다']),
(b,(550,754,764,884),['서연','유진'],['바다']),
(b,(774,539,987,707),['민지'],['카페'])]
manifest={'schema_version':1,'fixtures':{}}
for n,(im,box,names,tags) in enumerate(photos,1):
    path=assets/f'photo-{n:02}.jpg'; im.crop(box).save(path,quality=96)
    faces=[{'box':{'left':round(.06+i*.22,2),'top':.3,'width':.18,'height':.3},'person_name':name,'similarity':99.0} for i,name in enumerate(names)]
    manifest['fixtures'][hashlib.sha256(path.read_bytes()).hexdigest()]={'faces':faces,'tags':tags}
for i,(name,slug) in enumerate([('지수','jisu'),('민지','minji'),('서연','seoyeon'),('유진','yujin')]):
    boxes=[(556,151,642,238),(672,154,756,238),(783,154,867,238),(896,153,980,238)]
    path=assets/f'avatar-{slug}.jpg'; b.crop(boxes[i]).save(path,quality=96)
    manifest['fixtures'][hashlib.sha256(path.read_bytes()).hexdigest()]={'faces':[{'box':{'left':.1,'top':.1,'width':.8,'height':.8},'person_name':name,'similarity':99.0}],'tags':[],'reference_name':name}
# Deterministic no-face and unknown-face samples for exact-hash integration verification.
landscape=assets/'sample-no-face.jpg'; a.crop((244,813,480,909)).save(landscape,quality=96)
manifest['fixtures'][hashlib.sha256(landscape.read_bytes()).hexdigest()]={'faces':[],'tags':['노을']}
unknown=assets/'sample-unknown-face.jpg'; b.crop((550,381,764,532)).save(unknown,quality=96)
manifest['fixtures'][hashlib.sha256(unknown.read_bytes()).hexdigest()]={'faces':[{'box':{'left':.3,'top':.2,'width':.35,'height':.6},'person_name':None,'similarity':0}],'tags':['바다']}
(fixtures/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(f'Wrote {len(manifest["fixtures"])} exact-hash sample fixtures')
