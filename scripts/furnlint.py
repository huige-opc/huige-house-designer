"""家具使用性 lint：查“人能进去、能用”的三类规则，build.py 会自动跑。

用法：python scripts/furnlint.py spec.json
输出：[warn] 行 + JSON；有 warn 不能交付（和 check.mjs 的 warn 同级）。

规则（来源 reference/furnishing.md）：
1. 灶台 / 油烟机背后必须是实墙，不能贴在窗、玻璃隔断、门上；
2. 卫生间洁具之间、门口到洁具的净距 >= 600（淋浴房门口不能被洗手台堵住）；
3. 衣柜（含定制衣柜）正面到床 >= 500。

做法：用 spec 里的墙 / 门窗 / 家具坐标做平面几何判断；不依赖渲染。
"""
import json
import math
import os
import sys

WINDOW_GLASS = {
    'window', 'slideWindow', 'floorWindow', 'highWindow', 'bay', 'bayInner',
    'glassWall', 'door', 'double', 'unequal', 'sliding', 'folding', 'pocket',
    'garage', 'hole',
}
DOOR_TYPES = {'door', 'double', 'unequal', 'sliding', 'folding', 'pocket'}
BATH_FIXTURES = {'toilet', 'smartToilet', 'vanity', 'shower', 'bathTub', 'freeTub'}
WARDROBE_KEYS = {'wardrobe', 'cabWardrobe'}
HOOD_KEYS = {'counter', 'lCounter', 'uCounter', 'hood'}
MIN_BATH_GAP = 600
MIN_DOOR_GAP = 600
MIN_BED_GAP = 500

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, '..', 'reference', 'catalog-sizes.json')


def load_catalog():
    try:
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def num(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def pos(f):
    if 'at' in f and isinstance(f['at'], (list, tuple)):
        return num(f['at'][0]), num(f['at'][1])
    return num(f.get('x')), num(f.get('y'))


def size(f, cat):
    key = f.get('key') or f.get('type') or ''
    base = cat.get(key) or [num(f.get('w'), 1000), num(f.get('d'), 600), num(f.get('h'), 800)]
    return num(f.get('w'), base[0]), num(f.get('d'), base[1])


def rect(f, cat):
    x, y = pos(f)
    w, d = size(f, cat)
    rot = int(num(f.get('rot'))) % 360
    if rot in (90, 270):
        w, d = d, w
    return (x - w / 2, y - d / 2, x + w / 2, y + d / 2)


def front_vec(f):
    rot = int(num(f.get('rot'))) % 360
    return {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}.get(rot, (0, 1))


def back_vec(f):
    fx, fy = front_vec(f)
    return (-fx, -fy)


def span(v0, v1):
    return (min(v0, v1), max(v0, v1))


def overlap(a, b, margin=0.0):
    return min(a[1], b[1]) - max(a[0], b[0]) + margin


def rect_gap(a, b):
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return math.hypot(dx, dy) if dx > 0 and dy > 0 else max(dx, dy)


def point_rect_dist(x, y, r):
    dx = max(r[0] - x, 0, x - r[2])
    dy = max(r[1] - y, 0, y - r[3])
    return math.hypot(dx, dy)


def seg_rect_dist(a, b, r):
    """线段 ab 到矩形 r 的最短距离（采样即可，门洞长度 <= 2m）"""
    n = 60
    return min(point_rect_dist(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, r)
               for i in range(n + 1))


def front_gap(front, ra, rb):
    """rb 在 ra 正面时返回正面净距；不在正面返回 None。"""
    fx, fy = front
    if fx == 0:
        ov = overlap((ra[0], ra[2]), (rb[0], rb[2]))
        if ov <= 50:
            return None
        if fy > 0:
            gap = rb[1] - ra[3]
        else:
            gap = ra[1] - rb[3]
        return gap if gap >= -10 else 0.0
    ov = overlap((ra[1], ra[3]), (rb[1], rb[3]))
    if ov <= 50:
        return None
    gap = (rb[0] - ra[2]) if fx > 0 else (ra[0] - rb[2])
    return gap if gap >= -10 else 0.0


def wall_line(w):
    ax, ay = num(w['a'][0]), num(w['a'][1])
    bx, by = num(w['b'][0]), num(w['b'][1])
    if abs(ay - by) < 1:
        return 'h', ay, (ax, bx)
    if abs(ax - bx) < 1:
        return 'v', ax, (ay, by)
    return None, None, None


def opening_seg(w, op):
    orient, c, _ = wall_line(w)
    if orient is None:
        return None
    f, t = num(op.get('from')), num(op.get('to'))
    if f == 0 and t == 0:
        return None
    if orient == 'h':
        return ((f, c), (t, c)), span(f, t)
    return ((c, f), (c, t)), span(f, t)


def nearest_wall_for_edge(walls, orient, edge, span_, max_gap=400):
    """在 edge 一侧找最近的平行墙：返回 (wall, distance) 或 (None, None)"""
    best = (None, 1e9)
    for w in walls:
        o, c, s = wall_line(w)
        if o != orient:
            continue
        if overlap(span_, s) <= 100:
            continue
        d = abs(c - edge)
        if d <= max_gap + num(w.get('t'), 0) / 2 and d < best[1]:
            best = (w, d)
    return best


def room_of(labels, x, y):
    if not labels:
        return None
    return min(labels, key=lambda r: math.hypot(r['at'][0] - x, r['at'][1] - y))


def lint_spec(spec, cat=None):
    cat = cat or load_catalog()
    walls = spec.get('walls') or []
    furn = spec.get('furniture') or []
    labels = [r for r in (spec.get('rooms') or []) if r.get('at') and r.get('name')]
    out = []
    seen = set()

    def add(code, msg, room=None):
        k = (code, room, msg)
        if k in seen:
            return
        seen.add(k)
        out.append({'level': 'warn', 'code': code, 'room': room, 'msg': msg})

    # 1. 灶台 / 油烟机贴窗、贴玻璃、贴门
    for f in furn:
        key = f.get('key') or f.get('type') or ''
        if key not in HOOD_KEYS:
            continue
        if key in ('counter', 'lCounter', 'uCounter'):
            kit = f.get('kit') or {}
            if kit.get('hob') is False:
                continue
        r = rect(f, cat)
        bv = back_vec(f)
        if bv == (0, -1):
            orient, edge, span_ = 'h', r[1], (r[0], r[2])
        elif bv == (0, 1):
            orient, edge, span_ = 'h', r[3], (r[0], r[2])
        elif bv == (-1, 0):
            orient, edge, span_ = 'v', r[0], (r[1], r[3])
        else:
            orient, edge, span_ = 'v', r[2], (r[1], r[3])
        w, d = nearest_wall_for_edge(walls, orient, edge, span_)
        name = '油烟机' if key == 'hood' else '灶台/油烟机'
        room = (room_of(labels, *pos(f)) or {}).get('name')
        if not w:
            add('hood-no-wall', f'{name}背后没有实墙，应贴墙安装', room)
            continue
        for op in w.get('openings') or []:
            typ = op.get('type')
            if typ not in WINDOW_GLASS:
                continue
            seg = opening_seg(w, op)
            if not seg:
                continue
            _, osp = seg
            if overlap(osp, span_) > 50:
                sill = num(op.get('sill'), 0)
                head = num(op.get('head'), 2100)
                if head > 1300 and sill < 2100:
                    add('hood-on-window', f'{name}背后是{typ}，不能挂在窗/玻璃/门洞上，改贴实墙', room)
                    break

    # 2. 卫生间：洁具之间、门口到洁具的净距
    bath_labels = [r for r in labels if any(k in r['name'] for k in ('卫', '浴'))]
    for room in bath_labels:
        fx = [f for f in furn if (f.get('key') or f.get('type')) in BATH_FIXTURES
              and room_of(labels, *pos(f)) is room]
        if not fx:
            continue
        rects = {id(f): rect(f, cat) for f in fx}
        # 洁具正面互相挡
        for i, a in enumerate(fx):
            for b in fx[i + 1:]:
                g1 = front_gap(front_vec(a), rects[id(a)], rects[id(b)])
                g2 = front_gap(front_vec(b), rects[id(b)], rects[id(a)])
                g = min(v for v in (g1, g2) if v is not None) if any(v is not None for v in (g1, g2)) else None
                if g is not None and g < MIN_BATH_GAP:
                    ka = a.get('key') or a.get('type')
                    kb = b.get('key') or b.get('type')
                    add('bath-block', f'{room["name"]}：{ka} 和 {kb} 正面只有 {round(g)}mm，人进不去（要 ≥{MIN_BATH_GAP}）', room['name'])
        # 门口到洁具
        doors = []
        for w in walls:
            for op in w.get('openings') or []:
                if op.get('type') not in DOOR_TYPES:
                    continue
                seg = opening_seg(w, op)
                if not seg:
                    continue
                (a, b), _ = seg
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                dist = math.hypot(mid[0] - room['at'][0], mid[1] - room['at'][1])
                if dist < 3000:
                    doors.append((dist, a, b))
        if doors:
            _, da, db = min(doors, key=lambda t: t[0])
            for f in fx:
                d = seg_rect_dist(da, db, rects[id(f)])
                if d < MIN_DOOR_GAP:
                    kn = f.get('key') or f.get('type')
                    add('door-block', f'{room["name"]}：门口到 {kn} 只有 {round(d)}mm，进门/开门会撞（要 ≥{MIN_DOOR_GAP}）', room['name'])

    # 3. 衣柜正面到床
    for f in furn:
        if (f.get('key') or '') not in WARDROBE_KEYS:
            continue
        wr = rect(f, cat)
        room = room_of(labels, *pos(f))
        if not room:
            continue
        for b in furn:
            if not (b.get('key') or '').startswith('bed'):
                continue
            if room_of(labels, *pos(b)) is not room:
                continue
            g = front_gap(front_vec(f), wr, rect(b, cat))
            if g is not None and g < MIN_BED_GAP:
                add('wardrobe-bed', f'{room["name"]}：衣柜正面到床只有 {round(g)}mm，柜门/走道不够（要 ≥{MIN_BED_GAP}）', room['name'])

    return out


def main():
    if len(sys.argv) < 2:
        print('用法: python furnlint.py spec.json', file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding='utf-8') as f:
        spec = json.load(f)
    issues = lint_spec(spec)
    for it in issues:
        print(f'[{it["level"]}] {it["msg"]}')
    print(json.dumps({'count': len(issues), 'issues': issues}, ensure_ascii=False, indent=1))
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
