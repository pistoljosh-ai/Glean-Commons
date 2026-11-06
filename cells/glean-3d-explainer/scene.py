import bpy
import json
import math
import os
import sys
from pathlib import Path
from mathutils import Vector

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
S = bpy.context.scene
S.render.engine = 'BLENDER_WORKBENCH'
S.render.resolution_x, S.render.resolution_y = 960, 540
S.render.resolution_percentage = 100
S.render.fps = 16
S.render.image_settings.file_format = 'PNG'
storyboard, destination, mode = sys.argv[sys.argv.index('--') + 1:]
titles = json.loads(Path(storyboard).read_text())
S.render.filepath = str(Path(destination).resolve()) + os.sep
S.display.render_aa = '8'
sh = S.display.shading
sh.light = 'STUDIO'
sh.studiolight_rotate_z = .45
sh.color_type = 'MATERIAL'
sh.show_shadows = True
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_specular_highlight = True
sh.background_type = 'WORLD'
S.world.color = (.04,.065,.07)
S.view_settings.view_transform = 'Standard'

def mat(name, rgb):
    m=bpy.data.materials.new(name)
    m.diffuse_color=(*rgb,1)
    return m

dark=mat('Pine',(.033,.12,.105))
teal=mat('Jade',(.085,.42,.32))
mint=mat('Sprout',(.35,.92,.64))
cream=mat('Linen',(.92,.93,.81))
gold=mat('Marigold',(.99,.59,.18))
orange=mat('Terracotta',(.87,.29,.16))
navy=mat('Ink',(.055,.085,.15))
hair=mat('Espresso',(.09,.04,.035))
skin=mat('Warm clay',(.60,.32,.19))
skin2=mat('Honey clay',(.86,.54,.32))
white=mat('Paper',(.96,.98,.93))
table=mat('Walnut',(.28,.13,.065))
floor=mat('Studio floor',(.09,.19,.19))

def finish(o,m,parent=None):
    o.data.materials.append(m)
    if parent: o.parent=parent
    for p in getattr(o.data,'polygons',[]): p.use_smooth=True
    return o

def ball(loc, scale, m, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=loc)
    o=bpy.context.object
    o.scale=scale
    return finish(o,m,parent)

def cube(loc, scale, m, bevel=.08, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object
    o.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    b=o.modifiers.new('Soft edges','BEVEL'); b.width=bevel; b.segments=3
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return finish(o,m,parent)

def link(a,b,r,m,parent=None):
    delta=Vector(b)-Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=r,depth=delta.length,location=(Vector(a)+Vector(b))/2)
    o=bpy.context.object
    o.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
    return finish(o,m,parent)

def empty(loc,parent=None):
    bpy.ops.object.empty_add(location=loc)
    o=bpy.context.object
    if parent: o.parent=parent
    return o

def text(value,loc,size,m,parent=None,align='LEFT'):
    c=bpy.data.curves.new(value,'FONT'); c.body=value; c.size=size; c.align_x=align
    font='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
    if os.path.exists(font):
        c.font=bpy.data.fonts.get('Arial Bold') or bpy.data.fonts.load(font)
    o=bpy.data.objects.new(value,c)
    S.collection.objects.link(o); o.location=loc
    return finish(o,m,parent)

def person(x,y,turn,shirt,complexion,bun=False):
    root=empty((x,y,0)); root.rotation_euler.z=turn
    for side in (-1,1):
        ball((side*.17,0,.50),(.15,.17,.48),navy,root)
        ball((side*.17,-.10,.09),(.17,.25,.105),cream,root)
    ball((0,0,1.21),(.39,.24,.50),shirt,root)
    ball((0,0,1.65),(.14,.14,.20),complexion,root)
    head=empty((0,-.015,1.95),root)
    ball((0,0,0),(.30,.25,.34),complexion,head)
    ball((0,.09,.09),(.308,.21,.29),hair,head)
    ball((0,-.055,.22),(.28,.20,.15),hair,head)
    if bun: ball((0,.19,.29),(.17,.15,.16),hair,head)
    for side in (-1,1):
        ball((side*.278,-.008,-.03),(.055,.064,.085),complexion,head)
        ball((side*.105,-.23,.016),(.036,.020,.045),white,head)
        ball((side*.105,-.248,.015),(.016,.010,.026),navy,head)
        ball((side*.104,-.22,.089),(.047,.015,.011),hair,head)
    ball((0,-.255,-.048),(.044,.050,.038),complexion,head)
    ball((0,-.222,-.127),(.064,.017,.013),hair,head)
    arms=[]
    for side in (-1,1):
        arm=empty((side*.31,0,1.47),root)
        ball((0,0,-.155),(.12,.13,.22),shirt,arm)
        ball((0,-.025,-.36),(.092,.103,.17),complexion,arm)
        ball((0,-.03,-.49),(.098,.084,.104),complexion,arm)
        arm.rotation_euler.y=side*.12
        arms.append(arm)
    return root,head,arms

owner=person(-2.20,.08,.35,orange,skin,True)
builder=person(2.18,.27,-.36,teal,skin2)
cube((0,0,-.17),(200,200,.30),floor)
cube((0,.4,-.02),(8.7,5.5,.22),dark,.11)
cube((0,-.01,.79),(2.96,1.15,.16),table)
for x in (-1.25,1.25):
    cube((x,.0,.43),(.15,.72,.73),table,.07)
for x in (-3.62,3.6):
    cube((x,.72,.26),(.48,.48,.38),orange,.06)
    for i in range(6):
        a=i*2.4
        p=(x+.18*math.cos(a),.72+.17*math.sin(a),.70+.10*(i%3))
        link((x,.72,.40),p,.014,mint)
        leaf=ball(p,(.095,.052,.17),mint)
        leaf.rotation_euler.y=(i%3-1)*.66

laptop=cube((0,-.18,.89),(.70,.46,.05),navy,.03)
screen=cube((0,.04,1.12),(.70,.06,.47),navy,.035)
cube((0,.002,1.13),(.60,.014,.37),teal,.018)

props=[]
def prop_card(x,z,word,color):
    group=empty((x,.05,z))
    cube((0,0,0),(1.45,.14,.55),color,.07,group)
    lettering=text(word,(0,-.085,-.077),.205,navy,group,'CENTER')
    lettering.rotation_euler.x=math.pi/2
    props.append(group)
    return group

ask=prop_card(0,2.42,'REMIND ME',gold)
search=prop_card(0,2.42,'FIND A CELL',mint)
invoice=prop_card(-.78,2.70,'INVOICE',cream)
reminder=prop_card(.78,2.70,'REMINDER',mint)
combo=prop_card(0,1.93,'WORKFLOW',gold)
tree=empty((0,0,0)); props.append(tree)
link((-.60,.17,2.55),(0,.17,2.02),.025,mint,tree)
link((.60,.17,2.55),(0,.17,2.02),.025,mint,tree)
measure=prop_card(0,2.43,'PROOF OF USE',mint)
dots=empty((0,0,0)); props.append(dots)
for i in range(5):
    ball((-.55+i*.275,.03,1.91),(.077,.077,.077),gold,dots)

bpy.ops.object.camera_add()
cam=bpy.context.object
cam.data.type='ORTHO'; cam.data.ortho_scale=9.3
S.camera=cam

# Screen-space type follows the camera. A dark backing keeps captions readable.
cube((0,-2.13,-3.05),(9.45,1.05,.035),navy,.0,cam)
top=text('GLEAN COMMONS  /  A FIELD GUIDE',(-4.18,2.18,-3),.19,mint,cam)
visible=[[],[ask],[search],[invoice,reminder,combo],[invoice,reminder,combo,tree],[measure,dots]]

def show(o,state,frame):
    o.hide_render=not state
    o.keyframe_insert('hide_render',frame=frame)
    for c in o.children: show(c,state,frame)

def shot_camera(frame,point,target):
    cam.location=point
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.keyframe_insert('location',frame=frame)
    cam.keyframe_insert('rotation_euler',frame=frame)

def pose(actor,frame,gesture,nod):
    _,head,arms=actor
    head.rotation_euler.x=nod
    head.keyframe_insert('rotation_euler',frame=frame)
    for i,arm in enumerate(arms):
        arm.rotation_euler.x=-gesture if i==1 else -.25*gesture
        arm.keyframe_insert('rotation_euler',frame=frame)

for i,(title,caption) in enumerate(titles):
    start=i*96+1; end=start+95
    shot_camera(start,(-.65+i*.23,-10.2,4.25),(0,0,1.29))
    shot_camera(end,(.35+i*.20,-9.8,3.92),(0,0,1.30))
    for o in props:
        show(o, o in visible[i], start)
        if o in visible[i] and (i == 0 or o not in visible[i - 1]) and o not in (tree, dots):
            base_z = o.location.z
            o.location.z = base_z - .26
            o.keyframe_insert('location', frame=start)
            o.location.z = base_z
            o.keyframe_insert('location', frame=start + 14)
    t=text(title,(-4.16,-2.015,-2.99),.33,white,cam)
    c=text(caption,(-4.15,-2.345,-2.99),.197,cream,cam)
    for o in (t,c):
        show(o,False,1); show(o,True,start); show(o,False,end+1)
    for k,f in enumerate([start,start+27,start+53,start+77,end]):
        wave=[0,.85,.34,.63,0][k]
        pose(owner,f,wave*(1 if i in (0,1,4) else .4),.10*math.sin(k))
        pose(builder,f,wave*(1 if i in (2,3,5) else .35),-.10*math.sin(k))

S.frame_start=1; S.frame_end=576
if mode == 'preview':
    S.frame_set(125)
    S.render.filepath += 'preview.png'
    bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
