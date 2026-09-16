# 3D Scene Specification: Construction Site (건축현장)

**Target Feature:** Visual Vocabulary 3D Scene Generator  
**Topic:** Construction & Building Works (`construction-01`)  
**Context:** Active Wooden House Framing & Scaffolding Site  
**Target Vocabulary Count:** 14 TOEIC Terms  
**Engine & Tech Stack Target:** React Three Fiber (R3F), `@react-three/drei`, Three.js, JSON Scene Schema  

---

## 1. Scene Layout & Environment Description

### 1.1 Spatial Grid & Isometric Perspective
* **Perspective:** 3/4 Isometric-style View (Angled Top-Down Projection).
* **Origin $(0,0,0)$:** Ground level at the center of the wooden house frame base.
* **Orientation:**
  * **Main Wooden House Frame:** Positioned at the center-left along the X/Z axis, featuring exposed timber posts, gabled roof framing, and structural supports.
  * **Scaffolding Tower:** Positioned at the right side of the house frame, elevated for workers.
  * **Material Staging Area:** Positioned at the foreground (lower-right quadrant) on ground level, containing stacked lumber, raw logs, plywood sheets, and bricks.

### 1.2 Environment & Lighting Configuration
* **Initial Camera Position:** $[12.0, 10.0, 14.0]$
* **Camera Focus Target:** $[0.0, 2.5, 0.0]$
* **Field of View (FOV):** $40^\circ$
* **Lighting:**
  * **Ambient Light:** Intensity `0.65`, Color `#ffffff`
  * **Directional Light (Sunlight):** Position $[12, 20, 10]$, Intensity `1.2`, Soft Shadows enabled.

---

## 2. Detailed Object & Vocabulary Mapping

| Object Key | Vocabulary ID | Term / Word | IPA | Category | Description & Scene Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `obj-construction-site` | `vocab_construction_site` | construction site | `/kənˈstrʌkʃn saɪt/` | Context | Overall active building area featuring structure under construction. |
| `obj-ridge` | `vocab_ridge` | ridge | `/rɪdʒ/` | Structural | High horizontal beam at the intersection of the roof slopes. |
| `obj-beam` | `vocab_beam` | beam | `/biːm/` | Structural | Heavy horizontal structural timber supporting roof rafters and frame. |
| `obj-framework` | `vocab_framework` | framework | `/ˈfreɪmwɜːrk/` | Structural | The complete skeleton structure of timber posts and rafters. |
| `obj-prop` | `vocab_prop` | prop | `/prɑːp/` | Structural | Vertical post/support timber propping up the main frame. |
| `obj-scaffold` | `vocab_scaffold` | scaffold | `/ˈskæfəld/` | Equipment | Temporary steel lattice platform structure allowing workers to reach heights. |
| `obj-ladder` | `vocab_ladder` | ladder / stepladder | `/ˈlædər/` | Equipment | Wooden ladder leaning against the side frame for climbing access. |
| `obj-foreman` | `vocab_foreman` | foreman | `/ˈfɔːrmən/` | Entity | Construction supervisor on ground carrying blueprints and pointing upward. |
| `obj-worker-1` | `vocab_worker_hammer` | worker (hammering) | `/ˈwɜːrkər/` | Entity | Worker standing on frame structure hammering nails into timber. |
| `obj-worker-2` | `vocab_worker_saw` | worker (sawing) | `/ˈwɜːrkər/` | Entity | Worker standing on scaffolding sawing wood beams. |
| `obj-log` | `vocab_log` | log | `/lɔːɡ/` | Material | Raw un-sawn round wooden log lying on ground staging area. |
| `obj-board` | `vocab_board` | board / plank / plywood | `/bɔːrd/` | Material | Flat rectangular sawn lumber and stacked plywood sheets. |
| `obj-brick` | `vocab_brick` | brick | `/brɪk/` | Material | Stacked red/grey masonry building blocks on the ground. |
| `obj-plaster` | `vocab_plaster` | plaster | `/ˈplæstər/` | Material | Bag/container of building plaster material in staging area. |

---

## 3. AI Agent Detailed Scene Prompt

```text
Create a stylized isometric 3D low-poly scene representing an active residential wooden building construction site.

Core Structural Elements:
- A multi-beam wooden house skeleton framework with exposed gabled roof rafters, vertical prop posts, horizontal ridge beam, and side wall studs.
- Leaning against the left side of the house frame is a vertical wooden ladder.
- Next to the right side of the wooden house frame is a multi-tier metal frame scaffold with a top wooden walk plank.

Entities & Workers:
- Two construction workers wearing safety hard hats are active on top: one worker on the frame hammering a joint, and another worker standing on top of the scaffold using a hand saw on a wooden beam.
- On the ground to the right of the scaffold stands a foreman wearing a hard hat, carrying folded architectural blueprints and gesturing upwards toward the structure.

Material Staging Area (Foreground Right):
- A pile of construction raw materials organized neatly on the ground:
  1. A long cylindrical raw tree log.
  2. A stack of sawn rectangular wooden beams and planks.
  3. Two flat plywood sheets stacked slightly offset.
  4. A small stack of rectangular masonry bricks.

Visual Style & Lighting:
- Low-poly aesthetic with clean bevels, warm natural timber wood tones, steel metallic scaffold, orange/yellow hard hats, bright daylight setting with soft directional shadows casting to the left.
```

---

## 4. JSON Scene Schema Configuration (`construction_site.json`)

```json
{
  "id": "scene-construction-site-01",
  "title": "Construction Site",
  "category": "Architecture & Building",
  "theme": "construction",
  "difficulty": "B1-B2",
  "version": "1.0",
  "environment": {
    "backgroundColor": "#f4f6f9",
    "ambientLightIntensity": 0.65,
    "directionalLight": {
      "position": [12, 20, 10],
      "intensity": 1.2,
      "castShadow": true
    },
    "camera": {
      "initialPosition": [12.0, 10.0, 14.0],
      "target": [0.0, 2.5, 0.0],
      "fov": 40
    }
  },
  "assets": {
    "baseEnvironment": "/assets/3d/scenes/construction_ground_base.glb"
  },
  "objects": [
    {
      "id": "obj-framework-01",
      "vocabularyId": "vocab_framework",
      "modelPath": "/assets/3d/objects/house_framework.glb",
      "transform": {
        "position": [-1.5, 0.0, -1.0],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 3.2, 0.0],
        "label": "framework"
      },
      "cameraFocus": {
        "position": [3.5, 4.0, 4.0],
        "target": [-1.5, 2.5, -1.0]
      }
    },
    {
      "id": "obj-ridge-01",
      "vocabularyId": "vocab_ridge",
      "modelPath": "/assets/3d/objects/roof_ridge.glb",
      "transform": {
        "position": [-1.5, 4.5, -1.0],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.6, 0.0],
        "label": "ridge"
      },
      "cameraFocus": {
        "position": [2.0, 5.5, 3.0],
        "target": [-1.5, 4.5, -1.0]
      }
    },
    {
      "id": "obj-beam-01",
      "vocabularyId": "vocab_beam",
      "modelPath": "/assets/3d/objects/wooden_beam.glb",
      "transform": {
        "position": [-0.5, 3.8, -0.5],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.4, 0.0],
        "label": "beam"
      },
      "cameraFocus": {
        "position": [2.5, 4.5, 2.5],
        "target": [-0.5, 3.8, -0.5]
      }
    },
    {
      "id": "obj-prop-01",
      "vocabularyId": "vocab_prop",
      "modelPath": "/assets/3d/objects/vertical_prop.glb",
      "transform": {
        "position": [-3.0, 1.8, 0.5],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 1.0, 0.0],
        "label": "prop"
      },
      "cameraFocus": {
        "position": [-0.5, 2.5, 3.5],
        "target": [-3.0, 1.8, 0.5]
      }
    },
    {
      "id": "obj-scaffold-01",
      "vocabularyId": "vocab_scaffold",
      "modelPath": "/assets/3d/objects/scaffold_structure.glb",
      "transform": {
        "position": [1.8, 0.0, 0.2],
        "rotation": [0, 0, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 2.8, 0.0],
        "label": "scaffold"
      },
      "cameraFocus": {
        "position": [5.0, 3.5, 3.5],
        "target": [1.8, 2.0, 0.2]
      }
    },
    {
      "id": "obj-ladder-01",
      "vocabularyId": "vocab_ladder",
      "modelPath": "/assets/3d/objects/wooden_ladder.glb",
      "transform": {
        "position": [-4.2, 0.0, 0.8],
        "rotation": [0.25, 0, -0.2],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 1.8, 0.0],
        "label": "ladder / stepladder"
      },
      "cameraFocus": {
        "position": [-2.0, 2.2, 3.8],
        "target": [-4.2, 1.8, 0.8]
      }
    },
    {
      "id": "obj-foreman-01",
      "vocabularyId": "vocab_foreman",
      "modelPath": "/assets/3d/objects/foreman_character.glb",
      "transform": {
        "position": [3.8, 0.0, 1.5],
        "rotation": [0, -2.1, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 1.8, 0.0],
        "label": "foreman"
      },
      "cameraFocus": {
        "position": [5.5, 1.8, 3.5],
        "target": [3.8, 1.0, 1.5]
      }
    },
    {
      "id": "obj-log-01",
      "vocabularyId": "vocab_log",
      "modelPath": "/assets/3d/objects/timber_log.glb",
      "transform": {
        "position": [2.0, 0.1, 3.5],
        "rotation": [0, 0.4, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.4, 0.0],
        "label": "log"
      },
      "cameraFocus": {
        "position": [3.8, 1.5, 5.5],
        "target": [2.0, 0.2, 3.5]
      }
    },
    {
      "id": "obj-board-stack-01",
      "vocabularyId": "vocab_board",
      "modelPath": "/assets/3d/objects/plank_board_stack.glb",
      "transform": {
        "position": [1.5, 0.0, 4.8],
        "rotation": [0, -0.2, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.5, 0.0],
        "label": "board / plank / plywood"
      },
      "cameraFocus": {
        "position": [3.5, 1.5, 6.5],
        "target": [1.5, 0.3, 4.8]
      }
    },
    {
      "id": "obj-brick-stack-01",
      "vocabularyId": "vocab_brick",
      "modelPath": "/assets/3d/objects/brick_stack.glb",
      "transform": {
        "position": [3.5, 0.0, 4.5],
        "rotation": [0, 0.1, 0],
        "scale": [1.0, 1.0, 1.0]
      },
      "hotspot": {
        "offset": [0.0, 0.5, 0.0],
        "label": "brick"
      },
      "cameraFocus": {
        "position": [5.2, 1.5, 6.2],
        "target": [3.5, 0.3, 4.5]
      }
    }
  ]
}
```