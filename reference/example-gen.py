"""
示例：户型图2.jpg（12340×11940，三室两卫）的户型描述生成脚本。
做法：用 analyze.py 得到比例 S 和外轮廓左上角像素 (OX, OY)，再对照 analysis.png 上的像素标尺
读出每条墙中线、每个门窗两端的像素坐标，用 H()/V() 写墙，脚本统一换算成 mm。
"""
import json, sys
S=17.654; OX,OY=250,76
X=lambda p: round((p-OX)*S/10)*10
Y=lambda p: round((p-OY)*S/10)*10
P=lambda x,y:[X(x),Y(y)]
# horizontal wall, openings in px
def H(y,x0,x1,t,bearing=False,ops=()):
    return dict(a=P(x0,y),b=P(x1,y),t=t,bearing=bearing,openings=[dict(o, **{'from':X(o.pop('f')),'to':X(o.pop('e'))}) for o in map(dict,ops)])
def V(x,y0,y1,t,bearing=False,ops=()):
    return dict(a=P(x,y0),b=P(x,y1),t=t,bearing=bearing,openings=[dict(o, **{'from':Y(o.pop('f')),'to':Y(o.pop('e'))}) for o in map(dict,ops)])
E,I,T=240,200,120
walls=[
 # 外圈
 H(84,614,942,E,True,[dict(type='double',f=625,e=695,entry=True,into=P(660,50))]),
 V(942,84,248,E,True),
 H(248,739,942,E,False,[dict(type='door',f=752,e=800,hinge='from',into=P(780,200)),dict(type='window',f=850,e=930)]),
 V(840,248,746,E,True),
 H(746,445,840,E,True,[dict(type='window',f=483,e=802)]),
 V(445,650,746,E,True),
 # 主卧南侧凸窗原图是 120 窗台墙 + 403 台 + 240 外窗，这里按窗台建在外墙（不拆成无名房间）
 H(684,257,445,E,True,[dict(type='window',f=295,e=393,sill=450)]),
 V(257,288,684,E,True,[dict(type='window',f=345,e=398,sill=1400)]),
 H(288,257,512,E,True,[dict(type='window',f=368,e=480,sill=1400)]),
 V(512,192,384,E,True,[dict(type='window',f=198,e=276)]),
 H(192,512,614,E),
 V(614,84,192,E),
 # 内部
 V(739,84,248,E),
 V(614,192,384,E,False,[dict(type='sliding',f=235,e=355)]),
 H(384,360,614,I,False,[dict(type='door',f=455,e=505,hinge='to',into=P(480,350))]),
 V(360,288,452,E,False,[dict(type='door',f=395,e=445,hinge='from',into=P(400,420))]),
 H(452,257,360,E),
 V(445,384,650,E,False,[dict(type='door',f=395,e=445,hinge='from',into=P(410,420))]),
 H(455,445,614,T,False,[dict(type='door',f=457,e=505,hinge='from',into=P(480,490))]),
 V(614,455,650,T),
 H(650,445,840,E,True,[dict(type='window',f=483,e=585,sill=450),dict(type='sliding',f=620,e=805)]),
]
for w in walls:
    if not w['openings']: del w['openings']
rooms=[(840,160,'次卧'),(566,280,'厨房'),(440,330,'卫生间'),(307,365,'主卫'),(700,395,'客餐厅'),(357,545,'主卧'),(533,545,'次卧'),(642,700,'阳台')]
F=lambda key,x,y,rot=0,**k: dict(key=key,at=[x,y],rot=rot,**k)
furniture=[
 # 主卧
 F('bed18',1290,8300,270),F('nightstand',450,7130,270),F('nightstand',450,9470,270),F('cabWardrobe',3095,8300,90,w=2400,d=450),F('rug',1900,8300,270,w=2400,d=2000),F('beanbag',2597,9966,90),
 # 次卧（南）
 F('bed15',5345,8600,90),F('nightstand',6160,7590,90),F('nightstand',6160,9610,90),F('wardrobe',5501,6975,0,w=1600,d=450),
 # 次卧（北）
 F('bed12',10700,1260,0),F('nightstand',11600,470,0),F('wardrobe',9160,1100,270,w=1500),
 # 客餐厅
 F('rug',8500,8300,90),F('sofa',9825,8300,90),F('coffeeTable',8600,8300,90),F('tvCabinet',6690,8300,270),F('armchair',8500,6900,0),
 F('diningTable',9500,4955,0),F('chair',9214,4242,0),F('chair',9850,4269,0),F('chair',9174,5597,180),F('chair',9815,5604,180),
 F('shoeCabinet',6725,1100,270),F('plant',10000,6400,0),
 # 厨房
 # L 形：北墙放灶台（油烟机挂实墙，不挂西墙玻璃窗），西墙放水槽；窗前不做吊柜
 F('lCounter',5500,3220,0,w=1500,d=2100,kit=dict(corner='left',wall=False,
   sink=dict(leg=1,at=1700,w=600),hob=dict(leg=0,at=1050,w=600))),F('fridge',5100,4950,270),
 # 主卫
 F('toilet',650,4210,0),F('shower',1370,4310,0),F('vanity',640,6270,180),
 # 卫生间
 # 洗手台从门口那面墙挪到北墙马桶旁边，给进出留通道；冷水 / 热水 / 排水由 autoElec 跟着重排
 F('shower',2510,4310,0),F('toilet',3300,4210,0),F('vanity',3950,4113,0),
 # 阳台
 F('washer',3900,11400,0),F('lounge',8000,11000,0),F('lounge',8800,11000,0),F('sideTable',8400,11050,0),F('plant',10000,11400,0),
]
structs=[dict(kind='sewer',at=[650,4170]),dict(kind='sewer',at=[3300,4170]),dict(kind='drain',at=[1400,4310]),dict(kind='drain',at=[2450,4310]),dict(kind='drain',at=[4300,11500])]
dims=[
 # 顶部：1560 / 2460 / 1560 / 1960 / 3360，壁厚 240
 {'name':'顶部尺寸链','line':'y=-636','at':[3000,4500,6000],'from':0,'segs':[240,1560,240,2460,240,1560,240,1960,240,3360,240]},
 # 底部：3060 / 6760，壁厚 240
 {'name':'底部尺寸链','line':'y=12605','at':[9000],'from':0,'segs':[240,3060,240,6760,240]},
 # 左侧：1460 / 2660 / 3337 / 403——飘窗按外墙处理，120 + 403 两段没有墙特征，不写这条链
 # 右侧：2660 / 6860 / 1460，壁厚 240
 {'name':'右侧尺寸链','line':'x=13170','at':[9000],'from':0,'segs':[240,2660,240,6860,240,1460,240]},
]
spec=dict(structs=structs,furniture=furniture,name='户型图2 · 三室两卫',height=2800,phase='renovate',walls=walls,
  rooms=[dict(at=P(x,y),name=n) for x,y,n in rooms],autoElec=True,dims=dims,
  expectDims=dict(top=[240,1560,240,1960,240,3360,240],bottom=[240,3060,240,6760,240],right=[240,2660,240,6860,240,1460,240]),
  underlay=dict(image='example-input.jpg',mmPerPx=S,x=round(-OX*S),y=round(-OY*S)))
json.dump(spec,open(sys.argv[1] if len(sys.argv)>1 else 'spec.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(len(walls))
