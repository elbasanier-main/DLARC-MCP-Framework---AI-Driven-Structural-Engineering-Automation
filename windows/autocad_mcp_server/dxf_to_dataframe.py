# dxf_to_dataframe_fixed.py
"""
POLYFACE MESH extractor - creates filled 3D surfaces!
"""

import os, sys, argparse
import pandas as pd

def extract_polyface_meshes(filename):
    """Extract POLYFACE MESH structures with vertices and faces"""
    print(f"Reading {filename}...")
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    pairs = []
    i = 0
    while i < len(lines) - 1:
        try:
            code = int(lines[i].strip())
            value = lines[i+1].strip()
            pairs.append((code, value))
            i += 2
        except:
            i += 1
    
    # Extract layers
    print("\nExtracting layers...")
    layers = []
    layer_colors = {}
    in_layer_table = False
    current_layer = {}
    
    for i, (code, value) in enumerate(pairs):
        if code == 0 and value == 'TABLE':
            if i+1 < len(pairs) and pairs[i+1][1] == 'LAYER':
                in_layer_table = True
        
        if in_layer_table:
            if code == 0 and value == 'LAYER':
                if current_layer.get('name'):
                    layers.append(current_layer['name'])
                    if 'color' in current_layer:
                        layer_colors[current_layer['name']] = int(current_layer['color'])
                current_layer = {}
            elif code == 2:
                current_layer['name'] = value
            elif code == 62:
                current_layer['color'] = value
            elif code == 0 and value == 'ENDTAB':
                if current_layer.get('name'):
                    layers.append(current_layer['name'])
                    if 'color' in current_layer:
                        layer_colors[current_layer['name']] = int(current_layer['color'])
                in_layer_table = False
    
    print(f"Found {len(layers)} layers")
    
    # Extract POLYFACE MESHES
    print("\nExtracting POLYFACE MESHES...")
    
    meshes = []
    in_entities = False
    current_mesh = None
    current_vertex_data = {}
    
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        
        if code == 0 and value == 'SECTION':
            if i+1 < len(pairs) and pairs[i+1][1] == 'ENTITIES':
                in_entities = True
            i += 1
            continue
        
        if not in_entities:
            i += 1
            continue
        
        if code == 0:
            if value == 'POLYLINE':
                # Check if it's a polyface mesh
                # Look ahead for flag 70
                is_polyface = False
                layer = '0'
                color = 256
                
                for j in range(i+1, min(i+20, len(pairs))):
                    if pairs[j][0] == 70:
                        flags = int(pairs[j][1])
                        if flags & 64:  # Bit 6 = polygon mesh
                            is_polyface = True
                    elif pairs[j][0] == 8:
                        layer = pairs[j][1]
                    elif pairs[j][0] == 62:
                        color = int(pairs[j][1])
                    elif pairs[j][0] == 0:
                        break
                
                if is_polyface:
                    if current_mesh:
                        meshes.append(current_mesh)
                    current_mesh = {
                        'layer': layer,
                        'color': color,
                        'vertices': [],
                        'faces': []
                    }
            
            elif value == 'VERTEX' and current_mesh is not None:
                # Save previous vertex data
                if current_vertex_data:
                    flag = current_vertex_data.get('flag', 0)
                    
                    if flag == 192:  # Real vertex with coordinates
                        current_mesh['vertices'].append([
                            current_vertex_data.get('x', 0.0),
                            current_vertex_data.get('y', 0.0),
                            current_vertex_data.get('z', 0.0)
                        ])
                    
                    elif flag == 128:  # Face record
                        face = []
                        for code_num in [71, 72, 73, 74]:
                            if code_num in current_vertex_data:
                                face.append(current_vertex_data[code_num])
                        if face:
                            current_mesh['faces'].append(face)
                
                # Start new vertex
                current_vertex_data = {}
            
            elif value == 'SEQEND' and current_mesh is not None:
                # Save last vertex
                if current_vertex_data:
                    flag = current_vertex_data.get('flag', 0)
                    
                    if flag == 192:
                        current_mesh['vertices'].append([
                            current_vertex_data.get('x', 0.0),
                            current_vertex_data.get('y', 0.0),
                            current_vertex_data.get('z', 0.0)
                        ])
                    
                    elif flag == 128:
                        face = []
                        for code_num in [71, 72, 73, 74]:
                            if code_num in current_vertex_data:
                                face.append(current_vertex_data[code_num])
                        if face:
                            current_mesh['faces'].append(face)
                
                # Save mesh
                if current_mesh and current_mesh['vertices']:
                    meshes.append(current_mesh)
                current_mesh = None
                current_vertex_data = {}
            
            elif value == 'ENDSEC':
                if current_mesh:
                    meshes.append(current_mesh)
                break
        
        # Collect vertex data
        elif current_vertex_data is not None:
            if code == 10:
                current_vertex_data['x'] = float(value)
            elif code == 20:
                current_vertex_data['y'] = float(value)
            elif code == 30:
                current_vertex_data['z'] = float(value)
            elif code == 70:
                current_vertex_data['flag'] = int(value)
            elif code == 71:
                current_vertex_data[71] = int(value)
            elif code == 72:
                current_vertex_data[72] = int(value)
            elif code == 73:
                current_vertex_data[73] = int(value)
            elif code == 74:
                current_vertex_data[74] = int(value)
        
        i += 1
    
    print(f"Found {len(meshes)} POLYFACE MESHES")
    
    # Stats
    total_vertices = sum(len(m['vertices']) for m in meshes)
    total_faces = sum(len(m['faces']) for m in meshes)
    
    print(f"Total vertices: {total_vertices}")
    print(f"Total faces: {total_faces}")
    
    layer_counts = {}
    for m in meshes:
        layer_counts[m['layer']] = layer_counts.get(m['layer'], 0) + 1
    
    print("\nBy layer:")
    for layer, count in sorted(layer_counts.items()):
        print(f"  {layer}: {count}")
    
    return meshes, layers, layer_colors

def save_python_file(meshes, layers, layer_colors, output="building_dataframe_fixed.py"):
    """Save as executable Python file"""
    
    with open(output, 'w', encoding='utf-8') as f:
        f.write('''#!/usr/bin/env python3
import sys
import pandas as pd
import pythoncom
import win32com.client

MESHES = ''')
        f.write(repr(meshes))
        f.write('\n\nALL_LAYERS = ')
        f.write(repr(layers))
        f.write('\n\nLAYER_COLORS = ')
        f.write(repr(layer_colors))
        f.write('''

def recreate_in_autocad():
    """Recreate POLYFACE MESHES as 3DFACE entities"""
    pythoncom.CoInitialize()
    
    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        print("Connected to running AutoCAD")
    except:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        acad.Visible = True
        print("Started AutoCAD")
    
    if acad.Documents.Count == 0:
        doc = acad.Documents.Add()
    else:
        doc = acad.ActiveDocument
    
    modelspace = doc.ModelSpace
    
    # Create layers
    print(f"\\nCreating {len(ALL_LAYERS)} layers...")
    for layer_name in ALL_LAYERS:
        try:
            layer = doc.Layers.Item(layer_name)
        except:
            layer = doc.Layers.Add(layer_name)
            if layer_name in LAYER_COLORS:
                layer.Color = LAYER_COLORS[layer_name]
            print(f"  Created: {layer_name}")
    
    print(f"\\nCreating {len(MESHES)} POLYFACE MESHES as 3DFACE entities...")
    
    total_faces_created = 0
    mesh_count = 0
    
    for mesh in MESHES:
        try:
            vertices = mesh['vertices']
            faces = mesh['faces']
            layer = mesh['layer']
            color = mesh['color']
            
            # Create 3DFACE for each face
            for face_indices in faces:
                # Face indices are 1-based, convert to 0-based
                # Negative index means invisible edge
                pts = []
                for idx in face_indices:
                    abs_idx = abs(idx) - 1  # Convert to 0-based
                    if 0 <= abs_idx < len(vertices):
                        pts.append(vertices[abs_idx])
                
                # Need 3 or 4 points for 3DFACE
                if len(pts) == 3:
                    # Triangle - duplicate last point
                    pts.append(pts[2])
                elif len(pts) != 4:
                    continue
                
                # Create 3DFACE
                p1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, 
                                            [float(pts[0][0]), float(pts[0][1]), float(pts[0][2])])
                p2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                            [float(pts[1][0]), float(pts[1][1]), float(pts[1][2])])
                p3 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                            [float(pts[2][0]), float(pts[2][1]), float(pts[2][2])])
                p4 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                                            [float(pts[3][0]), float(pts[3][1]), float(pts[3][2])])
                
                face = modelspace.Add3DFace(p1, p2, p3, p4)
                face.Layer = layer
                if color != 256:
                    face.Color = color
                
                total_faces_created += 1
            
            mesh_count += 1
            if mesh_count % 100 == 0:
                print(f"  Processed {mesh_count}/{len(MESHES)} meshes...")
                
        except Exception as e:
            print(f"  Error creating mesh: {e}")
    
    print(f"\\n✅ Created {total_faces_created} 3DFACE entities from {mesh_count} meshes")
    
    # Zoom and regen
    try:
        acad.ZoomExtents()
    except:
        doc.SendCommand("_ZOOM _E ")
    
    doc.SendCommand("_REGEN ")
    
    # Set visual style for filled surfaces
    doc.SendCommand("VSCURRENT CONCEPTUAL ")
    
    print("\\n" + "="*70)
    print("✅ EXACT REPLICA COMPLETE WITH FILLED SURFACES!")
    print("   Set to CONCEPTUAL visual style for filled display")
    print("="*70)

if __name__ == "__main__":
    recreate_in_autocad()
''')
    
    print(f"\n{'='*70}")
    print(f"✅ Created {output}")
    print(f"   {len(meshes)} POLYFACE MESHES")
    print(f"   {sum(len(m['faces']) for m in meshes)} total faces")
    print(f"{'='*70}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dxf_file')
    parser.add_argument('--output', '-o', default='building_dataframe_fixed.py')
    args = parser.parse_args()
    
    if not os.path.exists(args.dxf_file):
        print(f"ERROR: {args.dxf_file} not found")
        sys.exit(1)
    
    meshes, layers, layer_colors = extract_polyface_meshes(args.dxf_file)
    save_python_file(meshes, layers, layer_colors, args.output)
    
    print(f"\nRun: python {args.output}")

if __name__ == "__main__":
    main()
