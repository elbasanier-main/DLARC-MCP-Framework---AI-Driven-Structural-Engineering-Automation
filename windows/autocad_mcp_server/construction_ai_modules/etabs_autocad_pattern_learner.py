#!/usr/bin/env python3
import argparse, json, os
from pathlib import Path
from collections import defaultdict

IN2MM = 25.4

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
            e = i; break
    ents=[]; i=s; cur={}
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

def extract_protocol(etabs_dxf, autocad_dxf):
    faces = faces_from_dxf(etabs_dxf)
    xy = [f for f in faces if f["layer"]=="SLAB" and f["ori"]=="XY"]
    if not xy: return None
    
    x_min = min(f["bbox"][0] for f in xy) * IN2MM
    x_max = max(f["bbox"][1] for f in xy) * IN2MM
    y_min = min(f["bbox"][2] for f in xy) * IN2MM
    y_max = max(f["bbox"][3] for f in xy) * IN2MM
    footprint_mm = {"x":[int(round(x_min)), int(round(x_max))], "y":[int(round(y_min)), int(round(y_max))]}
    
    slab_levels_in = sorted({ (f["bbox"][4]+f["bbox"][5])/2 for f in xy })
    slab_levels_mm = [int(round(z*IN2MM)) for z in slab_levels_in]
    
    xz_wall = [f for f in faces if f["layer"]=="WALL" and f["ori"]=="XZ"]
    bands_mm = sorted({ (int(round(f["bbox"][4]*IN2MM)), int(round(f["bbox"][5]*IN2MM))) for f in xz_wall })
    
    xz_slab_planes_mm = sorted(set(int(round(((f["bbox"][2]+f["bbox"][3])/2)*IN2MM)) for f in faces if f["layer"]=="SLAB" and f["ori"]=="XZ"))
    yz_slab_planes_mm = sorted(set(int(round(((f["bbox"][0]+f["bbox"][1])/2)*IN2MM)) for f in faces if f["layer"]=="SLAB" and f["ori"]=="YZ"))
    
    wxz = defaultdict(set)
    for f in xz_wall:
        y_mm = int(round(((f["bbox"][2]+f["bbox"][3])/2)*IN2MM))
        x1_mm = int(round(f["bbox"][0]*IN2MM)); x2_mm = int(round(f["bbox"][1]*IN2MM))
        if x2_mm>x1_mm: wxz[y_mm].add((x1_mm,x2_mm))
    wall_xz = {str(k): sorted(list(v)) for k,v in sorted(wxz.items())}
    
    wyz = defaultdict(set)
    for f in faces:
        if f["layer"]!="WALL" or f["ori"]!="YZ": continue
        x_mm = int(round(((f["bbox"][0]+f["bbox"][1])/2)*IN2MM))
        y1_mm = int(round(f["bbox"][2]*IN2MM)); y2_mm = int(round(f["bbox"][3]*IN2MM))
        if y2_mm>y1_mm: wyz[x_mm].add((y1_mm,y2_mm))
    wall_yz = {str(k): sorted(list(v)) for k,v in sorted(wyz.items())}
    
    return {
        "template_dxf": autocad_dxf,
        "footprint_mm": footprint_mm,
        "z_bands_mm": bands_mm,
        "slab_xy_levels_mm": slab_levels_mm,
        "slab_xz_yplanes_mm": xz_slab_planes_mm,
        "slab_yz_xplanes_mm": yz_slab_planes_mm,
        "wall_xz_intervals_per_y_mm": wall_xz,
        "wall_yz_intervals_per_x_mm": wall_yz
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max", type=int)
    args = ap.parse_args()
    
    folder = Path(args.folder)
    etabs_files = list(folder.glob("*_etabs.dxf")) or list(folder.glob("etabs_*.dxf"))
    
    if args.max:
        etabs_files = etabs_files[:args.max]
    
    print(f"Processing {len(etabs_files)} pairs")
    
    protocols = []
    for i, etabs_file in enumerate(etabs_files):
        base = str(etabs_file.stem).replace("_etabs", "").replace("etabs_", "")
        autocad_file = etabs_file.parent / f"{base}_autocad.dxf"
        if not autocad_file.exists():
            autocad_file = etabs_file.parent / f"autocad_{base}.dxf"
        if not autocad_file.exists():
            continue
        
        proto = extract_protocol(str(etabs_file), str(autocad_file))
        if proto:
            protocols.append(proto)
        
        if (i+1) % 1000 == 0:
            print(f"  {i+1} processed")
    
    with open(args.output, "w") as f:
        json.dump({"protocols": protocols}, f, indent=2)
    
    print(f"OK: {len(protocols)} protocols saved")

if __name__ == "__main__":
    main()
