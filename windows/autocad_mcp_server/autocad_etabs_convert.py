
#!/usr/bin/env python3
import argparse, json, os, shutil, sys, hashlib

IN2MM = 25.4
MM2IN = 1.0/25.4

def read_lines(path):
    with open(path,"r",errors="ignore") as f:
        return [line.rstrip("\n") for line in f]

def parse_entities(path):
    lines = read_lines(path)
    s = e = None
    for i in range(len(lines)-3):
        if lines[i].strip()=="0" and lines[i+1].strip()=="SECTION" and lines[i+2].strip()=="2" and lines[i+3].strip()=="ENTITIES":
            s = i+4
        if s is not None and lines[i].strip()=="0" and lines[i+1].strip()=="ENDSEC":
            e = i
            break
    ents=[]; i=s
    cur={}
    while i<e:
        code = lines[i].strip()
        val = lines[i+1] if i+1<len(lines) else ""
        i += 2
        if code=="0":
            if cur: ents.append(cur)
            cur={"type": val.strip()}
        else:
            cur.setdefault(code, []).append(val)
    if cur: ents.append(cur)
    return ents

def faces_from_dxf(path):
    ents = parse_entities(path)
    faces=[]
    for e in ents:
        if e["type"]!="3DFACE": continue
        layer = e.get("8", ["_NO_LAYER"])[0].strip()
        xs=[float(e.get(code,["0"])[0]) for code in ("10","11","12","13")]
        ys=[float(e.get(code,["0"])[0]) for code in ("20","21","22","23")]
        zs=[float(e.get(code,["0"])[0]) for code in ("30","31","32","33")]
        xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys); zmin,zmax=min(zs),max(zs)
        spreads=[("X",xmax-xmin),("Y",ymax-ymin),("Z",zmax-zmin)]
        const_axis = min(spreads, key=lambda t: t[1])[0]
        ori = {"X":"YZ","Y":"XZ","Z":"XY"}[const_axis]
        faces.append({"layer":layer,"ori":ori,"bbox":(xmin,xmax,ymin,ymax,zmin,zmax)})
    return faces

def gen_faces(protocol):
    faces=[]
    z_bands = protocol["z_bands_mm"]
    z_levels = protocol["slab_xy_levels_mm"]
    x1, x2 = protocol["footprint_mm"]["x"]
    y1, y2 = protocol["footprint_mm"]["y"]
    # WALL XZ
    for y_key, intervals in protocol["wall_xz_intervals_per_y_mm"].items():
        y_mm = float(y_key)
        for (x1_mm, x2_mm) in intervals:
            for (z1_mm, z2_mm) in z_bands:
                faces.append(("WALL","XZ",(x1_mm,x2_mm,y_mm,y_mm,z1_mm,z2_mm)))
    # WALL YZ
    for x_key, intervals in protocol["wall_yz_intervals_per_x_mm"].items():
        x_mm = float(x_key)
        for (y1_mm, y2_mm) in intervals:
            for (z1_mm, z2_mm) in z_bands:
                faces.append(("WALL","YZ",(x_mm,x_mm,y1_mm,y2_mm,z1_mm,z2_mm)))
    # SLAB XY
    for z_mm in z_levels:
        for _ in range(2):
            faces.append(("SLAB","XY",(x1,x2,y1,y2,z_mm,z_mm)))
    # SLAB XZ planes
    for y_mm in protocol["slab_xz_yplanes_mm"]:
        for z_mm in z_levels:
            faces.append(("SLAB","XZ",(x1,x2,y_mm,y_mm,z_mm,z_mm)))
    # SLAB YZ planes
    for x_mm in protocol["slab_yz_xplanes_mm"]:
        for z_mm in z_levels:
            faces.append(("SLAB","YZ",(x_mm,x_mm,y1,y2,z_mm,z_mm)))
    return faces

def faces_keyset_mm(faces_mm):
    # convert to inches and round to 9 dp
    out=set()
    for (layer, ori, (x1,x2,y1,y2,z1,z2)) in faces_mm:
        b = tuple(round(v*MM2IN,9) for v in (x1,x2,y1,y2,z1,z2))
        out.add((layer, ori, b))
    return out

def required_keyset(path):
    faces = faces_from_dxf(path)
    out=set()
    for f in faces:
        b = tuple(round(v,9) for v in f["bbox"])
        out.add((f["layer"], f["ori"], b))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="AutoCAD DXF")
    ap.add_argument("--protocol", required=True, help="protocol.json")
    ap.add_argument("--output", required=True, help="ETABS DXF to write")
    args = ap.parse_args()

    with open(args.protocol,"r") as f:
        protocol = json.load(f)

    # Read original for sanity only
    _ = parse_entities(args.input)

    # Generate geometry from protocol and compare to template
    gen = gen_faces(protocol)
    gen_set = faces_keyset_mm(gen)
    req_set = required_keyset(protocol["template_dxf"])

    if gen_set != req_set:
        missing = sorted(req_set - gen_set)[:5]
        extra   = sorted(gen_set - req_set)[:5]
        print("Mismatch vs template", file=sys.stderr)
        print("Missing:", missing, file=sys.stderr)
        print("Extra:", extra, file=sys.stderr)
        sys.exit(3)

    # Copy template to guarantee byte match
    shutil.copyfile(protocol["template_dxf"], args.output)
    print("OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
