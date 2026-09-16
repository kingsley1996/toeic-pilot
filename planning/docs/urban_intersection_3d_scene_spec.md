# 3D Scene Specification: Urban Road & Intersection

**Target Feature:** Visual Vocabulary 3D Scene Generator  
**Topic:** Urban Traffic & Infrastructure (`urban-traffic-02`)  
**Context:** Complex Urban Intersection & Pedestrian Crossing  
**Target Vocabulary Count:** 15 TOEIC Terms  
**Engine & Tech Stack Target:** React Three Fiber (R3F), `@react-three/drei`, Three.js, JSON Scene Definition Schema

---

## 1. Scene Spatial Layout & Camera Configuration

### 1.1 Spatial Grid & Isometric Orientation
* **Perspective:** 3/4 Isometric-style View (Top-Down Angled Projection).
* **Origin $(0,0,0)$:** Center of the 4-way road intersection crosswalk.
* **Orientation:**
  * **Main Road Axis:** Runs along the Z-axis from South-West $(-X, +Z)$ to North-East $(+X, -Z)$ with a visible curve at the lower-left section.
  * **Crossing Road Axis:** Runs along the X-axis from South-East $(+X, +Z)$ to North-West $(-X, -Z)$.
  * **Sidewalks & Pavements:** Flank all 4 quadrants of the roadway elevated slightly at $Y = 0.15$.

### 1.2 Default Camera Configuration
* **Initial Position:** $[18.0, 16.0, 18.0]$
* **Initial Target/LookAt:** $[0.0, 0.5, 0.0]$
* **Field of View (FOV):** $40^\circ$ (Perspective Camera with isometric framing look)
* **Lighting:**
  * **Ambient Light:** Color `#ffffff`, Intensity: `0.6`
  * **Directional Light (Sun):** Position $[15, 25, 10]$, Intensity: `1.3`, Shadow Casting enabled.

---

## 2. Structural & Environment Components Description

1. **The Curved Main Avenue & Junction:**
   * Multi-lane asphalt road featuring white dashed line dividers (`lane`) and solid white outer boundary lines.
   * Sharp curvature at the lower-left foreground (`curve`) bounded by concrete borders (`curb`).
   * High-contrast white striped pedestrian crosswalk (`crosswalk`) traversing the main intersection node (`intersection`).

2. **Pedestrian Skywalk & Subways:**
   * A heavy-duty steel overhead pedestrian bridge (`pedestrian overpass`) spanning directly over the multi-lane road. Features dual staircases landing on opposite sidewalks.
   * Two small glass-and-steel subway entry structures (`underpass`) situated at the far left sidewalk with stairs leading underground.

3. **Sidewalk Infrastructure & Fixtures:**
   * Raised concrete pavement walkways (`sidewalk` / `pavement`) running alongside the road curves.
   * Vintage double-arm street lamps (`lamppost` / `streetlight`) aligned along the right sidewalk edge.
   * Circular metal traffic signs (`road sign`) mounted on poles (`signpost`) near the intersection corner.
   * A 3-aspect vertical traffic light fixture (`signal`) standing at the corner before the zebra crossing.
   * A large commercial advertising structure (`billboard`) positioned on the back-right sidewalk.

4. **Dynamic Entities:**
   * A stylized low-poly sedan vehicle (`car`) traveling along the right lane toward the intersection.
   * A walking human character model (`pedestrian`) captured mid-stride (`cross`) across the crosswalk.

---

## 3. Object-to-Vocabulary Mapping Table

| Object Key | Vocabulary ID | Term / Word | IPA | Part of Speech | Scene Coordinate $[X, Y, Z]$ | Offset Hotspot $[X, Y, Z]$ | Camera Focus Position $[X, Y, Z]$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `obj-overpass` | `vocab_overpass` | (pedestrian) overpass | `/ˈoʊvərpæs/` | Noun | `[0.0, 2.8, -1.5]` | `[0.0, 1.2, 0.0]` | `[4.0, 5.0, 3.0]` |
| `obj-underpass` | `vocab_underpass` | underpass | `/ˈʌndərpæs/` | Noun | `[-6.5, 0.15, -4.0]` | `[0.0, 1.0, 0.0]` | `[-3.5, 2.5, -1.0]` |
| `obj-intersection`| `vocab_intersection`| intersection | `/ˌɪntərˈsekʃn/` | Noun | `[0.0, 0.01, 0.0]` | `[0.0, 0.5, 0.0]` | `[3.0, 3.5, 4.0]` |
| `obj-crosswalk` | `vocab_crosswalk` | crosswalk | `/ˈkrɔːswɔːk/` | Noun | `[0.5, 0.02, 2.0]` | `[0.0, 0.3, 0.0]` | `[3.0, 2.5, 4.5]` |
| `obj-sidewalk` | `vocab_sidewalk` | sidewalk | `/ˈsaɪdwɔːk/` | Noun | `[4.5, 0.15, 2.5]` | `[0.0, 0.3, 0.0]` | `[6.5, 2.0, 4.5]` |
| `obj-pavement` | `vocab_pavement` | pavement | `/ˈpeɪvmənt/` | Noun | `[5.5, 0.15, -1.5]` | `[0.0, 0.3, 0.0]` | `[7.5, 2.0, 1.0]` |
| `obj-curb` | `vocab_curb` | curb | `/kɜːrb/` | Noun | `[-3.2, 0.18, 4.2]` | `[0.0, 0.4, 0.0]` | `[-1.2, 1.5, 5.5]` |
| `obj-curve` | `vocab_curve` | curve | `/kɜːrv/` | Noun | `[-5.5, 0.01, 5.5]` | `[0.0, 0.4, 0.0]` | `[-3.0, 2.0, 7.0]` |
| `obj-lane` | `vocab_lane` | lane | `/leɪn/` | Noun | `[-2.0, 0.01, 2.5]` | `[0.0, 0.3, 0.0]` | `[0.5, 2.0, 4.5]` |
| `obj-billboard` | `vocab_billboard` | billboard | `/ˈbɪlbɔːrd/` | Noun | `[4.8, 1.5, -4.2]` | `[0.0, 2.0, 0.0]` | `[6.8, 3.0, -1.5]` |
| `obj-signal` | `vocab_signal` | signal | `/ˈsɪɡnəl/` | Noun | `[2.2, 0.15, 0.8]` | `[0.0, 2.2, 0.0]` | `[4.0, 2.2, 2.5]` |
| `obj-road-sign` | `vocab_road_sign` | road sign | `/roʊd saɪn/` | Noun | `[-1.5, 0.15, 3.8]` | `[0.0, 1.5, 0.0]` | `[0.5, 1.8, 5.2]` |
| `obj-lamppost` | `vocab_lamppost` | lamppost / streetlight | `/ˈlæmppoʊst/`| Noun | `[3.8, 0.15, 4.5]` | `[0.0, 2.0, 0.0]` | `[5.5, 2.0, 6.0]` |
| `obj-pedestrian` | `vocab_pedestrian` | pedestrian | `/pəˈdestriən/` | Noun | `[0.8, 0.15, 2.2]` | `[0.0, 1.6, 0.0]` | `[2.5, 1.8, 3.8]` |
| `obj-cross` | `vocab_cross` | cross | `/krɔːs/` | Verb | `[0.2, 0.15, 2.2]` | `[0.0, 1.0, 0.0]` | `[2.0, 1.8, 3.8]` |

---

## 4. JSON Scene Definition Output (`urban_intersection.json`)

```json
{
  "id": "scene-urban-intersection-02",
  "title": "Urban Road & Intersection",
  "category": "City Infrastructure & Transportation",
  "difficulty": "B1-B2",
  "version": "1.0",
  "environment": {
    "backgroundColor": "#e6edf5",
    "ambientLightIntensity": 0.6,
    "directionalLight": {
      "position": [15, 25, 10],
      "intensity": 1.3,
      "castShadow": true
    },
    "camera": {
      "initialPosition": [18.0, 16.0, 18.0],
      "target": [0.0, 0.5, 0.0],
      "fov": 40
    }
  },
  "assets": {
    "baseEnvironment": "/assets/3d/scenes/urban_intersection_base.glb"
  },
  "objects": [
    {
      "id": "obj-overpass",
      "vocabularyId": "vocab_overpass",
      "modelPath": "/assets/3d/objects/pedestrian_overpass.glb",
      "transform": {
        "position": [0.0, 0.0, -1.5],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 3.5, 0.0],
        "label": "(pedestrian) overpass"
      },
      "cameraFocus": {
        "position": [4.0, 5.0, 3.0],
        "target": [0.0, 2.8, -1.5]
      }
    },
    {
      "id": "obj-underpass",
      "vocabularyId": "vocab_underpass",
      "modelPath": "/assets/3d/objects/underpass_entry.glb",
      "transform": {
        "position": [-6.5, 0.15, -4.0],
        "rotation": [0, 1.57, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 1.8, 0.0],
        "label": "underpass"
      },
      "cameraFocus": {
        "position": [-3.5, 2.5, -1.0],
        "target": [-6.5, 0.5, -4.0]
      }
    },
    {
      "id": "obj-billboard",
      "vocabularyId": "vocab_billboard",
      "modelPath": "/assets/3d/objects/billboard.glb",
      "transform": {
        "position": [4.8, 0.15, -4.2],
        "rotation": [0, -0.45, 0],
        "scale": [1.2, 1.2, 1.2]
      },
      "hotspot": {
        "offset": [0.0, 3.2, 0.0],
        "label": "billboard"
      },
      "cameraFocus": {
        "position": [6.8, 3.0, -1.5],
        "target": [4.8, 1.8, -4.2]
      }
    },
    {
      "id": "obj-signal",
      "vocabularyId": "vocab_signal",
      "modelPath": "/assets/3d/objects/traffic_signal.glb",
      "transform": {
        "position": [2.2, 0.15, 0.8],
        "rotation": [0, 3.14, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 2.5, 0.0],
        "label": "signal"
      },
      "cameraFocus": {
        "position": [4.0, 2.2, 2.5],
        "target": [2.2, 1.5, 0.8]
      }
    },
    {
      "id": "obj-crosswalk",
      "vocabularyId": "vocab_crosswalk",
      "modelPath": "/assets/3d/objects/crosswalk_decal.glb",
      "transform": {
        "position": [0.5, 0.02, 2.0],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.3, 0.0],
        "label": "crosswalk"
      },
      "cameraFocus": {
        "position": [3.0, 2.5, 4.5],
        "target": [0.5, 0.02, 2.0]
      }
    },
    {
      "id": "obj-pedestrian",
      "vocabularyId": "vocab_pedestrian",
      "modelPath": "/assets/3d/objects/pedestrian_man.glb",
      "transform": {
        "position": [0.8, 0.15, 2.2],
        "rotation": [0, -1.57, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 1.8, 0.0],
        "label": "pedestrian"
      },
      "cameraFocus": {
        "position": [2.5, 1.8, 3.8],
        "target": [0.8, 0.8, 2.2]
      }
    }
  ]
}
```

---

## 5. R3F Component Implementation Guidance for AI Agents

When constructing this scene dynamically with React Three Fiber, the AI Agent should enforce the following patterns:

```tsx
import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html, useGLTF, Outlines } from '@react-three/drei';
import Vector3 from 'three';

// Hotspot Marker Component
function VocabularyHotspot({ position, label, onClick, isSelected }) {
  return (
    <group position={position}>
      <mesh onClick={onClick}>
        <sphereGeometry args={[0.2, 16, 16]} />
        <meshBasicMaterial color={isSelected ? "#3b82f6" : "#ef4444"} />
        {isSelected && <Outlines thickness={0.05} color="white" />}
      </mesh>
      <Html distanceFactor={12} position={[0, 0.4, 0]} center>
        <div className="bg-white/90 backdrop-blur-md px-2 py-1 rounded shadow-md border border-slate-200 text-xs font-semibold text-slate-800 pointer-events-none select-none">
          {label}
        </div>
      </Html>
    </group>
  );
}
```