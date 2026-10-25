"""Crime UI: preserve native square minimap; grow upward to fit Speeding."""
import io,json,re,struct
from PIL import Image
from resources import ROOT,entries,unpack
HERE=ROOT/'native-plugin/ui';OUT=ROOT/'native-plugin/build'
GAUGE=(0x856ddbac,0x46a006b0,0xf5ee0070)
assets=dict(entries());resources=[];changes=[]
icon=(HERE/'speeding-gauge.png').read_bytes()
assert Image.open(io.BytesIO(icon)).size==(16,16)
resources.append((GAUGE,icon));(OUT/'speeding-gauge.png').write_bytes(icon)
# Separate opaque black-backed marker in the native bitmap-loader group.
marker=Image.open(io.BytesIO(icon)).convert('RGBA')
pixels=marker.load()
for y in range(marker.height):
 for x in range(marker.width):
  if pixels[x,y][:3] in {(65,75,104),(70,80,108),(71,79,101)}:pixels[x,y]=(0,0,0,255)
# Native minimap loader reads SHPI/FSH, not PNG. Use a power-of-two 16x16
# ARGB8888 image (FSH type 0x7d), with raw BGRA pixels and no mipmaps.
assert marker.size==(16,16) # Reference already has the intended full height.
raw=marker.tobytes('raw','BGRA')
entry=struct.pack('<I6H',0x7d,16,16,0,0,0,0)+raw
fsh=b'SHPI'+struct.pack('<II4s',24+len(entry),1,b'G264')+struct.pack('<4sI',b'gaug',24)+entry
(OUT/'speeding-marker.resource').write_bytes(fsh)
# New, isolated backings: stock textures and other mods' icons stay untouched.
for old,new in [(0x14015591,0xf5ee0073),(0x14015592,0xf5ee0071),(0x8bbea9d1,0xf5ee0074),(0xcbbeab61,0xf5ee0075)]:
 bg=Image.open(io.BytesIO(unpack(assets[(0x856ddbac,0x46a006b0,old)]))).convert('RGBA')
 width=bg.width
 # Insert above the entire rounded left junction, including its upper curve.
 # Splitting that curve at298 left a sideways protrusion above the ledge.
 ext=Image.new('RGBA',(width,448));ext.paste(bg.crop((0,0,width,280)),(0,0))
 for y in range(280,300):ext.paste(bg.crop((0,279,width,280)),(0,y))
 ext.paste(bg.crop((0,280,width,428)),(0,300))
 # Verify the entire left gutter, including its curved junction, is shifted
 # down20px. The lower panel continues at the exact previous coordinates.
 assert ext.crop((0,318,100,448)).tobytes()==bg.crop((0,298,100,428)).tobytes()
 # The real minimap remains 256px tall (source rows60..315). Fill the added
 # space beneath it with the key's light panel color, not the map placeholder.
 map_color=bg.getpixel((200,309));left=right=200
 while left>0 and bg.getpixel((left-1,309))==map_color:left-=1
 while right+1<width and bg.getpixel((right+1,309))==map_color:right+=1
 key_color=bg.getpixel((width-30,200))
 from PIL import ImageDraw
 # Keep the original one-pixel map outline at row316 instead of stretching
 # its sides and bottom around the extra blank row beneath the map.
 ImageDraw.Draw(ext).rectangle((left-1,316,right+1,336),fill=key_color)
 ext.paste(bg.crop((left-1,316,right+2,317)),(left-1,316))
 assert all(ext.getpixel((x,y))==key_color for x in range(left-1,right+2) for y in range(317,337))
 assert ext.crop((left-1,316,right+2,317)).tobytes()==bg.crop((left-1,316,right+2,317)).tobytes()
 buf=io.BytesIO();ext.save(buf,format='PNG');resources.append(((0x856ddbac,0x46a006b0,new),buf.getvalue()))
def rect(line,dy=0,grow=0):
 return re.sub(r'area=\(([-\d]+),([-\d]+),([-\d]+),([-\d]+)\)',lambda m:'area=(%d,%d,%d,%d)'%(int(m[1]),int(m[2])+dy,int(m[3]),int(m[4])+dy+grow),line,count=1)
# Transparent parent retains the native title/label children. Its two child
# bitmaps select stock/expanded frames without hiding those labels.
blank=Image.new('RGBA',(1,1));blankbuf=io.BytesIO();blank.save(blankbuf,format='PNG')
resources.append(((0x856ddbac,0x46a006b0,0xf5ee0076),blankbuf.getvalue()))
for t,b in assets.items():
 if t[0]!=0:continue
 s=unpack(b).decode('latin1')
 if 'caption="Bank Robbery"' not in s:continue
 lines=s.splitlines(keepends=True)
 # Cover both standard and compact/native layout backings. The compact
 # panel uses 8bbea9d1 (516px wide), not the standard 14015591 (546px).
 # Preserve 0.15 positions; only expand artwork and its bitmap controls.
 for i in reversed(range(len(lines))):
  l=lines[i]
  if 'id=0x6a2871bc ' not in l:continue
  for source,replacement in [('14015591','f5ee0073'),('14015592','f5ee0071'),('8bbea9d1','f5ee0074'),('cbbeab61','f5ee0075')]:
   if 'image={46a006b0,'+source+'}' not in l:continue
   l=rect(l,grow=20).replace(source,replacement)
   l=re.sub(r'imagerect=\(([^)]*)\)',lambda m:'imagerect=('+','.join(m[1].split(',')[:3])+',448)',l)
   # Keep the stock control unchanged; only our overlay is taller.
   cover=l.replace('id=0x6a2871bc','id=0xf5ee0180')
   cover=cover.replace('winflag_visible=yes','winflag_visible=no')
   lines.insert(i+1,cover)
   break
 start=next(i for i,l in enumerate(lines) if 'id=0x8a2871c3 ' in l)
 legend=next(i for i,l in enumerate(lines) if 'id=0x8a2871c4 ' in l)
 # The anonymous frame inside the data panel was still stock-height. Give
 # its parent a unique ID, preserving its title children and source geometry.
 frame=next(i for i in range(start,legend) if 'image={46a006b0,14015592}' in lines[i])
 original_frame=lines[frame]
 bounds=re.search(r'area=\(([-\d]+),([-\d]+),([-\d]+),([-\d]+)\)',original_frame)
 fw=int(bounds[3])-int(bounds[1]);fh=int(bounds[4])-int(bounds[2])
 assert (fw,fh)==(396,288)
 parent_frame=original_frame.replace('iid=IGZWinBMP ','iid=IGZWinBMP id=0xf5ee0183 ',1)
 parent_frame=parent_frame.replace('image={46a006b0,14015592}','image={46a006b0,f5ee0076}')
 parent_frame=re.sub(r'imagerect=\([^)]+\)','imagerect=(0,0,1,1)',parent_frame)
 lines[frame]=parent_frame
 normal=re.sub(r'area=\([^)]+\)',f'area=(0,0,{fw},{fh})',original_frame, count=1)
 normal=normal.replace('iid=IGZWinBMP ','iid=IGZWinBMP id=0x6a2871bc ',1)
 expanded=normal.replace('id=0x6a2871bc','id=0xf5ee0180').replace('image={46a006b0,14015592}','image={46a006b0,f5ee0071}')
 expanded=expanded.replace(f'area=(0,0,{fw},{fh})',f'area=(0,0,{fw},{fh+20})').replace(',546,428)',',546,448)').replace('winflag_visible=yes','winflag_visible=no')
 # Insert before the existing title children so labels stay above the frame.
 lines.insert(frame+2,normal+expanded)
 legend=next(i for i,l in enumerate(lines) if 'id=0x8a2871c4 ' in l)
 lines[legend]=rect(lines[legend],grow=20)
 lines[legend+2]=lines[legend+2].replace('area=(0,0,134,260)','area=(0,0,134,276)')
 idx=next(i for i in range(legend,len(lines)) if 'caption="Bank Robbery"' in lines[i])
 label=re.sub(r' captionres=\{[^}]+\}','',lines[idx].replace('id=0x4aafe1ac','id=0xf5ee0170').replace('area=(27,240,134,260)','area=(27,260,134,276)').replace('caption="Bank Robbery"','caption="Speeding"'))
 lines.insert(idx,label)
 idx=next(i for i in range(legend,len(lines)) if 'image={46a006b0,14015593}' in lines[i])
 sym=lines[idx].replace('area=(5,0,21,256)','id=0xf5ee0171 area=(5,260,21,276)').replace('image={46a006b0,14015593}','image={46a006b0,f5ee0070}').replace('imagerect=(0,0,16,256)','imagerect=(0,0,16,16)')
 lines.insert(idx+1,sym)
 patched=''.join(lines)
 assert next(l for l in patched.splitlines() if 'id=0x00004203 ' in l)==next(l for l in s.splitlines() if 'id=0x00004203 ' in l)
 assert patched.count('<CHILDREN>')==patched.count('</CHILDREN>')
 assert patched.count('caption="Speeding"')==1
 # Shared stock backgrounds must remain byte-identical.
 assert [l for l in patched.splitlines() if 'id=0x6a2871bc ' in l][:-1]==[l for l in s.splitlines() if 'id=0x6a2871bc ' in l]
 assert 'id=0xf5ee0183 ' in patched
 assert all('winflag_visible=no' in l for l in patched.splitlines() if 'id=0xf5ee0180 ' in l)
 resources.append((t,patched.encode('latin1')));changes.append('%08x-%08x-%08x'%t)
assert len(changes)==3
payload=bytearray(96);index=[]
for t,b in resources:index.append((*t,len(payload),len(b)));payload+=b
pos=len(payload)
for e in index:payload+=struct.pack('<5I',*e)
struct.pack_into('<4sII',payload,0,b'DBPF',1,0);struct.pack_into('<4I',payload,32,7,len(index),pos,len(index)*20)
(OUT/'SC4Speeding-CrimeUI.dat').write_bytes(payload)
(OUT/'crime-ui-validation.json').write_text(json.dumps({'layouts':changes,'static_root_height_increase':0,'runtime_root_height_increase':20,'independent_full_height_backing':True,'compact_background_supported':True,'upper_panel_shift_y':-20,'radio_screen_shift_y':0,'native_map_size':[256,256],'key_row':[260,276],'icon_tgi':GAUGE,'resources':len(index),'in_game_verified':False},indent=2))
(OUT/'speeding-gauge.resource').write_bytes(icon)
print('Validated three layouts: upper panel -20px; radios unchanged; native square map preserved.')
